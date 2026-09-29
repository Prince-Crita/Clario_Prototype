"""Zoho Books connector manifest (plan §16). `reads` is shown to clients before they connect."""

from __future__ import annotations

from clario.integrations.zoho_books.regions import REGIONS
from clario.platform.integrations.contract import Availability, IntegrationManifest

MANIFEST = IntegrationManifest(
    key="zoho-books",
    name="Zoho Books",
    vendor="Zoho",
    domain="finance",
    summary="Revenue, costs, cash, receivables and GST from your Zoho Books organisation.",
    availability=Availability.AVAILABLE,
    sort_order=10,
    reads=(
        "Invoices, customers and customer payments",
        "Expenses, bills and vendor payments",
        "Chart of accounts and financial reports (profit & loss, balance sheet, tax summary)",
        "Bank and cash account balances",
    ),
    read_only=True,
    regions=REGIONS,
    account_noun="organisation",
)
