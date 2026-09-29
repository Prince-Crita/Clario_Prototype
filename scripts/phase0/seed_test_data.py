# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27", "tzdata"]
# ///
"""Phase 0 ONE-OFF: create a minimal, clearly-labelled TEST dataset in the Zoho Books TRIAL org.

Safety
  * Hard-wired to the trial organisation 60089553909; refuses anything else (never the live org).
  * Separate OAuth consent with CREATE/UPDATE scopes, used only by this script; token revoked at end.
  * Every record is named/referenced "TEST". No GST (GST stays disabled in the org).
  * Every created id is written to .spike/seed-manifest.json; a re-run resumes, never duplicates.
  * Refuses to start if TEST contacts exist but no manifest does (unknown prior state).

Dataset (amounts in INR, no tax) — see docs/phase0/README.md "TEST dataset":
  bank account 1 · customers 3 · vendor 1 · invoices 7 (1 draft, 1 void) · customer payments 3
  expenses 4 · bill 1 · vendor payment 1

Run from the repo root:  python -m uv run scripts/phase0/seed_test_data.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from _env import REPO_ROOT, load_env, require
from zoho_spike import authorize, revoke

TARGET_ORG = "60089553909"
FORBIDDEN_ORGS = {"60069959305"}  # the director's live organisation — never touched
MANIFEST = REPO_ROOT / ".spike" / "seed-manifest.json"
SCOPES = [
    "ZohoBooks.settings.READ", "ZohoBooks.accountants.READ",
    "ZohoBooks.contacts.CREATE", "ZohoBooks.contacts.READ",
    "ZohoBooks.banking.CREATE", "ZohoBooks.banking.READ",
    "ZohoBooks.invoices.CREATE", "ZohoBooks.invoices.UPDATE", "ZohoBooks.invoices.READ",
    "ZohoBooks.customerpayments.CREATE", "ZohoBooks.expenses.CREATE",
    "ZohoBooks.bills.CREATE", "ZohoBooks.bills.READ", "ZohoBooks.vendorpayments.CREATE",
]
NOTE = "TEST data - Clario Phase 0 API validation. Not real business data."

CUSTOMERS = {"alpha": "TEST Customer Alpha", "beta": "TEST Customer Beta", "gamma": "TEST Customer Gamma"}
VENDOR = "TEST Vendor One"
BANK = "TEST Bank Current"
# key: (customer, date, due_date, rate, final_state)
INVOICES = {
    "inv1": ("alpha", "2026-03-20", "2026-03-30", 10000, "sent"),   # prior FY billing, paid in current FY
    "inv2": ("alpha", "2026-07-10", "2026-07-25", 50000, "sent"),   # fully paid
    "inv3": ("beta", "2026-08-05", "2026-08-20", 30000, "sent"),    # partially paid -> overdue
    "inv4": ("gamma", "2026-08-28", "2026-09-12", 20000, "sent"),   # unpaid -> overdue
    "inv5": ("beta", "2026-09-15", "2026-10-15", 8000, "sent"),     # open, not yet due
    "inv6": ("gamma", "2026-09-20", "2026-10-05", 5000, "draft"),   # excluded from billed
    "inv7": ("alpha", "2026-09-01", "2026-09-15", 3000, "void"),    # excluded from billed
}
# key: (customer, invoice, date, amount)
PAYMENTS = {
    "pay1": ("alpha", "inv1", "2026-04-05", 10000),
    "pay2": ("alpha", "inv2", "2026-09-10", 50000),
    "pay3": ("beta", "inv3", "2026-08-25", 15000),
}
# key: (date, expense account name, amount, paid-through, with vendor?)
EXPENSES = {
    "exp1": ("2026-07-15", "Salaries and Employee Wages", 40000, "bank", False),
    "exp2": ("2026-08-10", "Rent Expense", 12000, "bank", True),
    "exp3": ("2026-09-05", "Cost of Goods Sold", 9000, "bank", False),
    "exp4": ("2026-09-18", "IT and Internet Expenses", 2500, "petty", False),
}
BILL = ("TEST-BILL-001", "2026-08-01", "2026-08-31", "Office Supplies", 6000)
VENDOR_PAYMENT = ("2026-09-02", 6000)


class Zoho:
    def __init__(self, api_domain: str, token: str) -> None:
        self.base = f"{api_domain.rstrip('/')}/books/v3"
        self.http = httpx.Client(timeout=45, headers={"Authorization": f"Zoho-oauthtoken {token}"})
        self.org: str | None = None

    def call(self, method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict:
        query = {**(params or {}), **({"organization_id": self.org} if self.org else {})}
        for attempt in range(1, 4):
            try:
                resp = self.http.request(method, f"{self.base}/{path}", params=query, json=body)
                break
            except httpx.TransportError:
                if attempt == 3:
                    raise
                time.sleep(2 * attempt)
        payload = resp.json()
        if resp.status_code >= 400 or payload.get("code") not in (0, None):
            raise SystemExit(f"Zoho {method} {path} failed: HTTP {resp.status_code} "
                             f"code={payload.get('code')} {payload.get('message')}")
        return payload


def load_manifest() -> dict[str, Any]:
    if MANIFEST.exists():
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if data.get("organization_id") != TARGET_ORG:
            raise SystemExit("Manifest belongs to a different organisation — aborting.")
        return data
    return {"organization_id": TARGET_ORG, "created": {}, "complete": False}


def save_manifest(manifest: dict[str, Any]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    env = load_env()
    require(env, "ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REDIRECT_URI")
    manifest = load_manifest()
    if manifest.get("complete"):
        raise SystemExit("TEST dataset already complete (see .spike/seed-manifest.json). Nothing to do.")
    created: dict[str, Any] = manifest["created"]

    auth = authorize(env, "in", SCOPES)
    zoho = Zoho(auth["api_domain"] or "https://www.zohoapis.in", auth["_access_token"])
    try:
        orgs = zoho.call("GET", "organizations").get("organizations") or []
        ids = {str(o["organization_id"]) for o in orgs}
        if TARGET_ORG not in ids:
            raise SystemExit(f"Trial organisation {TARGET_ORG} not available to this login (sees {sorted(ids)}).")
        assert TARGET_ORG not in FORBIDDEN_ORGS
        zoho.org = TARGET_ORG
        org = zoho.call("GET", f"organizations/{TARGET_ORG}")["organization"]
        if org.get("is_registered_for_gst"):
            raise SystemExit("GST is enabled in the trial org; this dataset assumes GST disabled. Aborting.")

        # Guard: unknown prior TEST state without a manifest -> stop rather than duplicate.
        existing = zoho.call("GET", "contacts", params={"contact_name_contains": "TEST "}).get("contacts") or []
        if existing and not created:
            raise SystemExit("TEST contacts already exist but no manifest was found — aborting to avoid duplicates.")

        accounts = zoho.call("GET", "chartofaccounts", params={"per_page": 200}).get("chartofaccounts") or []
        account_id = {a["account_name"]: a["account_id"] for a in accounts}
        for name in ["Sales", "Petty Cash", "Office Supplies", *{e[1] for e in EXPENSES.values()}]:
            if name not in account_id:
                raise SystemExit(f"Expected default account '{name}' not found in chart of accounts.")

        def remember(key: str, kind: str, record_id: str, label: str) -> None:
            created[key] = {"type": kind, "id": record_id, "label": label}
            save_manifest(manifest)
            print(f"  created {kind:16} {label}")

        # 1. Bank account
        if "bank" not in created:
            bank = zoho.call("POST", "bankaccounts", body={
                "account_name": BANK, "account_type": "bank", "currency_id": org.get("currency_id"),
                "description": NOTE})["bankaccount"]
            remember("bank", "bankaccount", bank["account_id"], BANK)
        bank_id = created["bank"]["id"]

        # 2. Contacts
        for key, name in CUSTOMERS.items():
            if key not in created:
                contact = zoho.call("POST", "contacts", body={
                    "contact_name": name, "company_name": name, "contact_type": "customer", "notes": NOTE})["contact"]
                remember(key, "customer", contact["contact_id"], name)
        if "vendor" not in created:
            contact = zoho.call("POST", "contacts", body={
                "contact_name": VENDOR, "company_name": VENDOR, "contact_type": "vendor", "notes": NOTE})["contact"]
            remember("vendor", "vendor", contact["contact_id"], VENDOR)

        # 3. Invoices (created as draft, then marked sent / voided as specified)
        for key, (customer, date, due, rate, final_state) in INVOICES.items():
            if key not in created:
                invoice = zoho.call("POST", "invoices", body={
                    "customer_id": created[customer]["id"], "date": date, "due_date": due,
                    "reference_number": "TEST", "notes": NOTE,
                    "line_items": [{"name": "TEST service", "description": f"TEST service ({key})",
                                    "rate": rate, "quantity": 1, "account_id": account_id["Sales"]}],
                })["invoice"]
                remember(key, "invoice", invoice["invoice_id"], f"{invoice['invoice_number']} ({key}, {final_state})")
                created[key]["state_applied"] = "draft"
                save_manifest(manifest)
            entry = created[key]
            if final_state in {"sent", "void"} and entry.get("state_applied") == "draft":
                zoho.call("POST", f"invoices/{entry['id']}/status/sent")
                entry["state_applied"] = "sent"
                save_manifest(manifest)
            if final_state == "void" and entry.get("state_applied") == "sent":
                zoho.call("POST", f"invoices/{entry['id']}/status/void")
                entry["state_applied"] = "void"
                save_manifest(manifest)

        # 4. Customer payments, deposited to the TEST bank account
        for key, (customer, invoice_key, date, amount) in PAYMENTS.items():
            if key not in created:
                payment = zoho.call("POST", "customerpayments", body={
                    "customer_id": created[customer]["id"], "payment_mode": "banktransfer", "amount": amount,
                    "date": date, "reference_number": "TEST", "description": NOTE, "account_id": bank_id,
                    "invoices": [{"invoice_id": created[invoice_key]["id"], "amount_applied": amount}],
                })["payment"]
                remember(key, "customerpayment", payment["payment_id"], f"{key} {amount} on {date}")

        # 5. Expenses
        for key, (date, account_name, amount, paid_through, with_vendor) in EXPENSES.items():
            if key not in created:
                body = {"account_id": account_id[account_name], "date": date, "amount": amount,
                        "paid_through_account_id": bank_id if paid_through == "bank" else account_id["Petty Cash"],
                        "reference_number": "TEST", "description": f"TEST expense - {account_name}"}
                if with_vendor:
                    body["vendor_id"] = created["vendor"]["id"]
                expense = zoho.call("POST", "expenses", body=body)["expense"]
                remember(key, "expense", expense["expense_id"], f"{key} {account_name} {amount}")

        # 6. Bill + vendor payment
        bill_number, bill_date, bill_due, bill_account, bill_amount = BILL
        if "bill" not in created:
            bill = zoho.call("POST", "bills", body={
                "vendor_id": created["vendor"]["id"], "bill_number": bill_number, "date": bill_date,
                "due_date": bill_due, "reference_number": "TEST", "notes": NOTE,
                "line_items": [{"account_id": account_id[bill_account], "description": "TEST office supplies",
                                "rate": bill_amount, "quantity": 1}],
            })["bill"]
            remember("bill", "bill", bill["bill_id"], bill_number)
        if "vendorpayment" not in created:
            vp_date, vp_amount = VENDOR_PAYMENT
            vp = zoho.call("POST", "vendorpayments", body={
                "vendor_id": created["vendor"]["id"], "payment_mode": "banktransfer", "amount": vp_amount,
                "date": vp_date, "paid_through_account_id": bank_id, "reference_number": "TEST",
                "description": NOTE, "bills": [{"bill_id": created["bill"]["id"], "amount_applied": vp_amount}],
            })["vendorpayment"]
            remember("vendorpayment", "vendorpayment", vp["payment_id"], f"vendor payment {vp_amount} on {vp_date}")

        manifest["complete"] = True
        save_manifest(manifest)
        print(f"\nTEST dataset complete: {len(created)} records. Manifest: {MANIFEST.relative_to(REPO_ROOT)}")
    finally:
        print(f"Refresh token revoke: {revoke(auth['accounts_server'], auth['_refresh_token'])}")
        zoho.http.close()


if __name__ == "__main__":
    main()
