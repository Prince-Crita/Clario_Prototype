from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from clario.config import Settings
from clario.zoho.models import Expense, Invoice


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        zoho_client_id="test-client-id",
        zoho_client_secret="test-client-secret",
        zoho_redirect_uri="http://localhost:8000/oauth/zoho/callback",
        zoho_accounts_url="https://accounts.zoho.in",
        zoho_api_base_url="https://www.zohoapis.in/books/v3",
        zoho_organization_id="org-1",
        zoho_refresh_token="refresh-token",
        google_api_key="test-google-key",
        gemini_model="gemini-2.5-flash",
        clario_data_dir=tmp_path,
    )


@pytest.fixture
def sample_invoices() -> list[Invoice]:
    return [
        Invoice(
            invoice_id="1",
            invoice_number="INV-001",
            customer_id="c1",
            customer="Acme",
            invoice_date=date(2026, 9, 2),
            due_date=date(2026, 9, 10),
            status="paid",
            total=Decimal("1000"),
            balance=Decimal("0"),
            currency="INR",
        ),
        Invoice(
            invoice_id="2",
            invoice_number="INV-002",
            customer_id="c2",
            customer="Globex",
            invoice_date=date(2026, 9, 5),
            due_date=date(2026, 9, 12),
            status="overdue",
            total=Decimal("400"),
            balance=Decimal("400"),
            currency="INR",
        ),
        Invoice(
            invoice_id="3",
            invoice_number="INV-003",
            customer_id="c1",
            customer="Acme",
            invoice_date=date(2026, 8, 10),
            due_date=date(2026, 8, 20),
            status="sent",
            total=Decimal("700"),
            balance=Decimal("200"),
            currency="INR",
        ),
        Invoice(
            invoice_id="4",
            invoice_number="INV-004",
            customer_id="c3",
            customer="Initech",
            invoice_date=date(2026, 9, 8),
            due_date=date(2026, 9, 30),
            status="draft",
            total=Decimal("9999"),
            balance=Decimal("9999"),
            currency="INR",
        ),
    ]


@pytest.fixture
def sample_expenses() -> list[Expense]:
    return [
        Expense(
            expense_id="e1",
            expense_date=date(2026, 9, 3),
            account_name="Travel",
            category="Travel",
            total=Decimal("120"),
            currency="INR",
        ),
        Expense(
            expense_id="e2",
            expense_date=date(2026, 9, 4),
            account_name="Software",
            category="Software",
            total=Decimal("80"),
            currency="INR",
        ),
        Expense(
            expense_id="e3",
            expense_date=date(2026, 8, 15),
            account_name="Software",
            category="Software",
            total=Decimal("50"),
            currency="INR",
        ),
    ]
