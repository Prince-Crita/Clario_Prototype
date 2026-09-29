"""Zoho Books JSON → canonical finance records (plan §16.4, §23.3). Pure functions, no I/O.

Rules verified in Phase 0:
  * amounts arrive as JSON numbers already parsed to `Decimal` by the client;
  * the invoice LIST has no base-currency total: base = amount × exchange_rate (1 for INR);
  * status labels are not trusted ("overdue" hides partly paid): status comes from the amounts,
    except draft and void, which keep a balance in Zoho and must never count as receivable;
  * the expense list has account NAMES only (the ingest resolves them to accounts);
  * P&L and balance-sheet lines nest: a parent's total includes its children, so each account's
    OWN amount is its total minus its children's totals, and every section must add up.
Anything the mapping does not understand raises `ZohoMappingError`: a dataset fails loudly instead
of silently dropping data.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from clario.core.errors import UpstreamError
from clario.core.text import normalise_typography
from clario.domains.finance.schemas import (
    Account,
    AccountCategory,
    BalanceAmount,
    Expense,
    Invoice,
    InvoiceStatus,
    LedgerAmount,
    Party,
    PartyType,
    PaymentMade,
    PaymentReceived,
    PnlSection,
    TaxRole,
)

Json = Mapping[str, Any]
CENT = Decimal("0.0001")
ZERO = Decimal(0)


class ZohoMappingError(UpstreamError):
    default_code = "zoho.unexpected_data"


# ---------------------------------------------------------------- primitives


def _text(value: Any) -> str:
    return normalise_typography(str(value if value is not None else "")).strip()


def _opt(value: Any) -> str | None:
    return _text(value) or None


def _dec(value: Any, field: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, str) and value.strip():
        try:
            return Decimal(value.strip())
        except ArithmeticError:
            pass
    if value in (None, ""):
        return ZERO
    raise ZohoMappingError(f"Unexpected amount in {field}.")  # floats never reach here


def _base(amount: Decimal, rate: Decimal) -> Decimal:
    return (amount * rate).quantize(CENT, rounding=ROUND_HALF_UP)


def _date(value: Any, field: str) -> date:
    try:
        return date.fromisoformat(_text(value))
    except ValueError:
        raise ZohoMappingError(f"Unexpected date in {field}.") from None


def _opt_date(value: Any) -> date | None:
    text = _text(value)
    return date.fromisoformat(text) if text else None


def _stamp(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None  # informational only; never fail a dataset over it


def _id(record: Json, key: str) -> str:
    value = _text(record.get(key))
    if not value:
        raise ZohoMappingError(f"Record without {key}.")
    return value


# ---------------------------------------------------------------- lists


def to_party(record: Json, party_type: PartyType) -> Party:
    return Party(
        source_id=_id(record, "contact_id"),
        party_type=party_type,
        display_name=_text(record.get("contact_name")) or _text(record.get("company_name")),
        company_name=_opt(record.get("company_name")),
        gstin=_opt(record.get("gst_no")),
        currency=_opt(record.get("currency_code")),
        source_updated_at=_stamp(record.get("last_modified_time")),
    )


def invoice_status(source_status: str, total: Decimal, balance: Decimal) -> InvoiceStatus:
    label = source_status.lower()
    if label == "draft":
        return InvoiceStatus.DRAFT
    if label == "void":
        return InvoiceStatus.VOID
    if balance <= ZERO:
        return InvoiceStatus.PAID
    if balance < total:
        return InvoiceStatus.PARTIALLY_PAID
    if balance == total:
        return InvoiceStatus.OPEN
    return InvoiceStatus.UNKNOWN  # balance above total: surface it, never guess


def to_invoice(record: Json) -> Invoice:
    total = _dec(record.get("total"), "invoice.total")
    balance = _dec(record.get("balance"), "invoice.balance")
    rate = _dec(record.get("exchange_rate"), "invoice.exchange_rate") or Decimal(1)
    source_status = _text(record.get("status")) or "unknown"
    subtotal = record.get("sub_total")
    tax_total = record.get("tax_total")
    return Invoice(
        source_id=_id(record, "invoice_id"),
        invoice_number=_text(record.get("invoice_number")),
        party_source_id=_opt(record.get("customer_id")),
        party_name=_text(record.get("customer_name")),
        invoice_date=_date(record.get("date"), "invoice.date"),
        due_date=_opt_date(record.get("due_date")),
        source_status=source_status[:32],
        status=invoice_status(source_status, total, balance),
        currency=_text(record.get("currency_code")) or "INR",
        exchange_rate=rate,
        subtotal=_dec(subtotal, "invoice.sub_total") if subtotal is not None else None,
        tax_total=_dec(tax_total, "invoice.tax_total") if tax_total is not None else None,
        total=total,
        balance=balance,
        total_base=_base(total, rate),
        balance_base=_base(balance, rate),
        source_updated_at=_stamp(record.get("last_modified_time")),
    )


def to_payment_received(record: Json) -> PaymentReceived:
    return PaymentReceived(
        source_id=_id(record, "payment_id"),
        party_source_id=_opt(record.get("customer_id")),
        party_name=_text(record.get("customer_name")),
        payment_date=_date(record.get("date"), "customerpayment.date"),
        amount=_dec(record.get("amount"), "customerpayment.amount"),
        amount_base=_dec(record.get("bcy_amount"), "customerpayment.bcy_amount"),
        currency=_text(record.get("currency_code")) or "INR",
        payment_mode=_opt(record.get("payment_mode")),
        reference=_opt(record.get("reference_number")),
        source_updated_at=_stamp(record.get("last_modified_time")),
    )


def to_expense(record: Json) -> Expense:
    total_base = _dec(record.get("bcy_total"), "expense.bcy_total")
    net_base = _dec(record.get("bcy_total_without_tax"), "expense.bcy_total_without_tax")
    return Expense(
        source_id=_id(record, "expense_id"),
        expense_date=_date(record.get("date"), "expense.date"),
        account_name=_text(record.get("account_name")),
        vendor_name=_opt(record.get("vendor_name")),
        amount_net=net_base,
        tax_amount=total_base - net_base,
        total=_dec(record.get("total"), "expense.total"),
        total_base=total_base,
        currency=_text(record.get("currency_code")) or "INR",
        paid_through=_opt(record.get("paid_through_account_name")),
        source_updated_at=_stamp(record.get("last_modified_time")),
    )


def to_payment_made(record: Json) -> PaymentMade:
    return PaymentMade(
        source_id=_id(record, "payment_id"),
        party_source_id=_opt(record.get("vendor_id")),
        party_name=_text(record.get("vendor_name")),
        payment_date=_date(record.get("date"), "vendorpayment.date"),
        amount=_dec(record.get("amount"), "vendorpayment.amount"),
        amount_base=_dec(record.get("bcy_amount"), "vendorpayment.bcy_amount"),
        currency=_text(record.get("currency_code")) or "INR",
        paid_through=_opt(record.get("paid_through_account_name")),
        source_updated_at=_stamp(record.get("last_modified_time")),
    )


# Zoho `account_type` → canonical category (and the tax role, for GST accounts).
ACCOUNT_TYPES: dict[str, tuple[AccountCategory, TaxRole | None]] = {
    "income": (AccountCategory.INCOME, None),
    "other_income": (AccountCategory.OTHER_INCOME, None),
    "cost_of_goods_sold": (AccountCategory.COST_OF_GOODS_SOLD, None),
    "expense": (AccountCategory.EXPENSE, None),
    "other_expense": (AccountCategory.OTHER_EXPENSE, None),
    "cash": (AccountCategory.CASH, None),
    "bank": (AccountCategory.BANK, None),
    "accounts_receivable": (AccountCategory.ACCOUNTS_RECEIVABLE, None),
    "other_current_asset": (AccountCategory.OTHER_CURRENT_ASSET, None),
    "stock": (AccountCategory.OTHER_CURRENT_ASSET, None),
    "payment_clearing": (AccountCategory.OTHER_CURRENT_ASSET, None),
    "input_tax": (AccountCategory.OTHER_CURRENT_ASSET, TaxRole.INPUT_TAX),
    "fixed_asset": (AccountCategory.FIXED_ASSET, None),
    "accounts_payable": (AccountCategory.ACCOUNTS_PAYABLE, None),
    "output_tax": (AccountCategory.TAX_LIABILITY, TaxRole.OUTPUT_TAX),
    "overseas_tax_payable": (AccountCategory.TAX_LIABILITY, TaxRole.OUTPUT_TAX),
    "other_current_liability": (AccountCategory.OTHER_LIABILITY, None),
    "long_term_liability": (AccountCategory.OTHER_LIABILITY, None),
    "non_current_liability": (AccountCategory.OTHER_LIABILITY, None),
    "other_liability": (AccountCategory.OTHER_LIABILITY, None),
    "credit_card": (AccountCategory.OTHER_LIABILITY, None),
    "equity": (AccountCategory.EQUITY, None),
}


def to_account(record: Json) -> Account:
    source_type = _text(record.get("account_type")).lower()
    category, tax_role = ACCOUNT_TYPES.get(source_type, (AccountCategory.OTHER, None))
    return Account(
        source_id=_id(record, "account_id"),
        name=_text(record.get("account_name")),
        code=_opt(record.get("account_code")),
        source_account_type=source_type or "unknown",
        category=category,
        tax_role=tax_role,
        is_active=record.get("is_active") is not False,
        source_updated_at=_stamp(record.get("last_modified_time")),
    )


# ---------------------------------------------------------------- reports

PNL_SECTIONS = {
    "operating income": PnlSection.OPERATING_INCOME,
    "cost of goods sold": PnlSection.COST_OF_GOODS_SOLD,
    "operating expense": PnlSection.OPERATING_EXPENSE,
    "non operating income": PnlSection.NON_OPERATING_INCOME,
    "non operating expense": PnlSection.NON_OPERATING_EXPENSE,
}
PNL_TOTALS = {"gross profit", "operating profit", "net profit/loss"}


def _children(node: Json) -> list[Json]:
    rows = node.get("account_transactions") or []
    return [r for r in rows if isinstance(r, Mapping)]


def _own_amounts(node: Json) -> Iterator[tuple[str, str, Decimal]]:
    """(account id, name, own amount) for an account line and its sub-accounts."""
    children = _children(node)
    own = _dec(node.get("total"), "report.total") - sum(
        (_dec(c.get("total"), "report.total") for c in children), ZERO
    )
    account_id = _text(node.get("account_id"))
    if account_id and own != ZERO:
        yield account_id, _text(node.get("name")), own
    elif not account_id and own != ZERO:
        raise ZohoMappingError("Report line with an amount but no account.")
    for child in children:
        yield from _own_amounts(child)


def ledger_month(report: Json, month: date) -> list[LedgerAmount]:
    """One monthly P&L report → own amounts per account and section. Checks every section total."""
    context = report.get("page_context") or {}
    if _text(context.get("report_basis")).lower() not in ("", "accrual"):
        raise ZohoMappingError("Expected an accrual profit and loss report.")
    lines: list[LedgerAmount] = []
    for block in report.get("profit_and_loss") or []:
        if _text(block.get("name")).lower() not in PNL_TOTALS:
            raise ZohoMappingError(f"Unknown profit and loss block {block.get('name')!r}.")
        for section_node in _children(block):
            section = PNL_SECTIONS.get(_text(section_node.get("name")).lower())
            if section is None:
                raise ZohoMappingError(
                    f"Unknown profit and loss section {section_node.get('name')!r}."
                )
            section_lines = [
                LedgerAmount(account_id, name, section, month, amount)
                for child in _children(section_node)
                for account_id, name, amount in _own_amounts(child)
            ]
            expected = _dec(section_node.get("total"), "report.total")
            if sum((line.amount for line in section_lines), ZERO) != expected:
                raise ZohoMappingError(f"{section.value} lines do not add up to the section total.")
            lines.extend(section_lines)
    return lines


def balance_lines(report: Json, as_of: date) -> list[BalanceAmount]:
    """Balance sheet → one line per account (own balance), plus computed lines such as
    current-year earnings. Each line records the group it sits in ("Cash", "Bank", ...)."""
    lines: list[BalanceAmount] = []

    def walk(node: Json, group: str) -> None:
        children = _children(node)
        name = _text(node.get("name"))
        account_id = _text(node.get("account_id")) or None
        own = _dec(node.get("total"), "report.total") - sum(
            (_dec(c.get("total"), "report.total") for c in children), ZERO
        )
        if account_id:  # an account (its sub-accounts stay in the same group)
            if own != ZERO:
                lines.append(BalanceAmount(account_id, name, group[:64], as_of, own))
            for child in children:
                walk(child, group)
        elif children:  # a grouping line: must be exactly the sum of what it groups
            if own != ZERO:
                raise ZohoMappingError(f"Balance sheet group {name!r} does not add up.")
            for child in children:
                walk(child, name)
        elif own != ZERO:  # a computed line, e.g. current-year earnings
            lines.append(BalanceAmount(None, name, group[:64], as_of, own))

    for top in report.get("balance_sheet") or []:
        walk(top, _text(top.get("name")))
    return lines
