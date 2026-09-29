# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27", "tzdata"]
# ///
"""Phase 0 Zoho Books spike — READ-ONLY discovery against a real organisation.

What it does
  1. Runs the server-based OAuth flow once (opens your browser, catches the redirect on the
     localhost ZOHO_REDIRECT_URI), exchanging the code for tokens in memory only.
  2. Calls only GET endpoints of Zoho Books to learn response shapes, record counts,
     report structure, scope coverage and rate-limit headers.
  3. Revokes the refresh token at the end (nothing long-lived is left behind).

Outputs
  .spike/raw/*.json                  full responses (REAL business data; git-ignored; local only)
  docs/phase0/zoho-spike-report.md   sanitised: field names/types, counts, statuses — no amounts

Run from the repo root:  python -m uv run scripts/phase0/zoho_spike.py
Optional env: ZOHO_SPIKE_SCOPES (comma list), ZOHO_SPIKE_ORG_ID, ZOHO_SPIKE_REGION.
"""

from __future__ import annotations

import http.server
import json
import re
import secrets
import threading
import time
import webbrowser
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

import httpx

from _env import REPO_ROOT, load_env, require

DATA_CENTERS: dict[str, tuple[str, str]] = {
    "in": ("https://accounts.zoho.in", "https://www.zohoapis.in"),
    "com": ("https://accounts.zoho.com", "https://www.zohoapis.com"),
    "eu": ("https://accounts.zoho.eu", "https://www.zohoapis.eu"),
    "au": ("https://accounts.zoho.com.au", "https://www.zohoapis.com.au"),
    "jp": ("https://accounts.zoho.jp", "https://www.zohoapis.jp"),
    "ca": ("https://accounts.zohocloud.ca", "https://www.zohoapis.ca"),
}
ALLOWED_ACCOUNTS_SERVERS = {accounts for accounts, _ in DATA_CENTERS.values()}
EXTRA_SPIKE_SCOPES = ("ZohoBooks.banking.READ", "ZohoBooks.bills.READ", "ZohoBooks.vendorpayments.READ")
EXPLORATORY_REPORTS = ("trialbalance", "generalledger", "accounttransactions", "taxsummary")
TAX_NAME = re.compile(r"\b(gst|cgst|sgst|igst|utgst|cess|tax)\b", re.IGNORECASE)
SAFE_ENUM_KEYS = {"status", "account_type", "contact_type", "payment_mode", "report_name"}
MAX_PAGES = 50
RAW_DIR = REPO_ROOT / ".spike" / "raw"
REPORT_PATH = REPO_ROOT / "docs" / "phase0" / "zoho-spike-report.md"


# --------------------------------------------------------------------------- OAuth


@dataclass
class CallbackResult:
    params: dict[str, str] = field(default_factory=dict)
    received: threading.Event = field(default_factory=threading.Event)


def wait_for_callback(redirect_uri: str, result: CallbackResult) -> http.server.HTTPServer:
    parts = urlsplit(redirect_uri)
    if parts.hostname not in {"localhost", "127.0.0.1"} or not parts.port:
        raise SystemExit("ZOHO_REDIRECT_URI must be a localhost URI with an explicit port for the spike.")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            url = urlsplit(self.path)
            if url.path != parts.path:
                self.send_response(404)
                self.end_headers()
                return
            result.params = {k: v[0] for k, v in parse_qs(url.query).items()}
            body = b"Clario Phase 0 spike: authorization received. You can close this tab."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            result.received.set()

        def log_message(self, *_: Any) -> None:  # keep the console quiet (query holds the code)
            return

    server = http.server.HTTPServer((parts.hostname, parts.port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def authorize(env: dict[str, str], region: str, scopes: list[str]) -> dict[str, Any]:
    accounts, _ = DATA_CENTERS[region]
    state = secrets.token_urlsafe(24)
    query = urlencode(
        {
            "scope": ",".join(scopes),
            "client_id": env["ZOHO_CLIENT_ID"],
            "response_type": "code",
            "redirect_uri": env["ZOHO_REDIRECT_URI"],
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    auth_url = f"{accounts}/oauth/v2/auth?{query}"
    result = CallbackResult()
    server = wait_for_callback(env["ZOHO_REDIRECT_URI"], result)
    print("Opening Zoho consent in your browser. If it does not open, visit:\n" + auth_url)
    webbrowser.open(auth_url)
    try:
        if not result.received.wait(timeout=300):
            raise SystemExit("Timed out waiting for the Zoho redirect (5 min).")
    finally:
        server.shutdown()

    params = result.params
    if params.get("state") != state:
        raise SystemExit("State mismatch — aborting.")
    if "error" in params:
        raise SystemExit(f"Zoho returned error: {params['error']}")
    accounts_server = params.get("accounts-server") or accounts
    if accounts_server.rstrip("/") not in ALLOWED_ACCOUNTS_SERVERS:
        raise SystemExit(f"Unexpected accounts-server {accounts_server!r} — not in allow-list.")

    resp = httpx.post(
        f"{accounts_server.rstrip('/')}/oauth/v2/token",
        params={
            "grant_type": "authorization_code",
            "client_id": env["ZOHO_CLIENT_ID"],
            "client_secret": env["ZOHO_CLIENT_SECRET"],
            "redirect_uri": env["ZOHO_REDIRECT_URI"],
            "code": params.get("code", ""),
        },
        timeout=30,
    )
    token = resp.json()
    if resp.status_code >= 400 or "error" in token or "access_token" not in token:
        raise SystemExit(f"Token exchange failed: HTTP {resp.status_code} {token.get('error', '')}")
    return {
        "callback_param_names": sorted(params),
        "callback_location": params.get("location", ""),
        "callback_accounts_server": params.get("accounts-server", ""),
        "accounts_server": accounts_server.rstrip("/"),
        "token_response_keys": sorted(token),
        "api_domain": token.get("api_domain", ""),
        "expires_in": token.get("expires_in"),
        "granted_scope": token.get("scope", ""),
        "has_refresh_token": bool(token.get("refresh_token")),
        "_access_token": token["access_token"],
        "_refresh_token": token.get("refresh_token", ""),
    }


def revoke(accounts_server: str, refresh_token: str) -> str:
    if not refresh_token:
        return "no refresh token issued"
    resp = httpx.post(f"{accounts_server}/oauth/v2/token/revoke", params={"token": refresh_token}, timeout=30)
    return f"HTTP {resp.status_code}"


# --------------------------------------------------------------------------- Books API


@dataclass
class Probe:
    name: str
    path: str
    status: int
    ms: int
    calls: int
    code: Any = None
    message: str = ""
    records: int | None = None
    shape: Any = None
    note: str = ""


class Books:
    def __init__(self, api_domain: str, access_token: str, org_id: str | None = None) -> None:
        self.base = f"{api_domain.rstrip('/')}/books/v3"
        self.http = httpx.Client(timeout=45, headers={"Authorization": f"Zoho-oauthtoken {access_token}"})
        self.org_id = org_id
        self.calls = 0
        self.rate_headers: dict[str, str] = {}

    def get(self, path: str, params: dict[str, Any] | None = None) -> tuple[int, dict[str, Any], int]:
        query = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        if self.org_id:
            query["organization_id"] = self.org_id
        started = time.perf_counter()
        for attempt in range(1, 4):  # transient network errors (e.g. server disconnect) are retried
            try:
                resp = self.http.get(f"{self.base}/{path}", params=query)
                break
            except httpx.TransportError:
                if attempt == 3:
                    raise
                time.sleep(2 * attempt)
        self.calls += 1
        for key, value in resp.headers.items():
            if any(token in key.lower() for token in ("limit", "rate", "retry")):
                self.rate_headers[key] = value
        try:
            payload = resp.json()
        except ValueError:
            payload = {"_non_json": resp.text[:200]}
        if resp.status_code == 429:
            time.sleep(float(resp.headers.get("Retry-After") or 5))
        return resp.status_code, payload if isinstance(payload, dict) else {"_list": payload}, int(
            (time.perf_counter() - started) * 1000
        )


def shape_of(value: Any, key: str = "", depth: int = 0) -> Any:
    """Type skeleton of a JSON value. Scalars become type names; enums under safe keys are kept."""
    if depth > 8:
        return "…"
    if isinstance(value, dict):
        return {k: shape_of(v, k, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [shape_of(value[0], key, depth + 1), f"({len(value)} items)"] if value else ["(empty)"]
    if key in SAFE_ENUM_KEYS and isinstance(value, str):
        return f"str:{value!r}"
    return type(value).__name__


def save_raw(name: str, payload: Any) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def probe(books: Books, probes: list[Probe], name: str, path: str, params: dict | None = None,
          list_key: str | None = None) -> dict[str, Any]:
    status, payload, ms = books.get(path, params)
    save_raw(name, payload)
    rows = payload.get(list_key) if list_key else None
    probes.append(
        Probe(
            name=name, path=path, status=status, ms=ms, calls=1,
            code=payload.get("code"), message=str(payload.get("message", ""))[:120],
            records=len(rows) if isinstance(rows, list) else None,
            shape=shape_of(rows[0]) if isinstance(rows, list) and rows else shape_of(payload),
        )
    )
    return payload


def paginate(books: Books, probes: list[Probe], name: str, path: str, list_key: str,
             params: dict | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    calls, total_ms, status, code, message, note = 0, 0, 0, None, "", ""
    for page in range(1, MAX_PAGES + 1):
        status, payload, ms = books.get(path, {**(params or {}), "page": page, "per_page": 200})
        calls, total_ms = calls + 1, total_ms + ms
        code, message = payload.get("code"), str(payload.get("message", ""))[:120]
        batch = payload.get(list_key)
        if status != 200 or not isinstance(batch, list):
            break
        rows.extend(batch)
        page_context = payload.get("page_context") or {}
        if not page_context.get("has_more_page"):
            break
    else:
        note = f"stopped at {MAX_PAGES} pages"
    save_raw(name, rows)
    probes.append(
        Probe(name=name, path=path, status=status, ms=total_ms, calls=calls, code=code, message=message,
              records=len(rows), shape=shape_of(rows[0]) if rows else None, note=note)
    )
    return rows


# --------------------------------------------------------------------------- main


def fiscal_year_start(today: date, start_month: int) -> date:
    year = today.year if today.month >= start_month else today.year - 1
    return date(year, start_month, 1)


def mask(value: str) -> str:
    return f"…{value[-4:]}" if value else ""


def main() -> None:
    env = load_env()
    require(env, "ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REDIRECT_URI")
    region = env.get("ZOHO_SPIKE_REGION") or env.get("ZOHO_DEFAULT_REGION") or "in"
    if region not in DATA_CENTERS:
        raise SystemExit(f"Unknown region {region!r}")
    scopes = [s.strip() for s in (env.get("ZOHO_SPIKE_SCOPES") or env.get("ZOHO_SCOPES", "")).split(",") if s.strip()]
    if not env.get("ZOHO_SPIKE_SCOPES"):
        scopes += [s for s in EXTRA_SPIKE_SCOPES if s not in scopes]

    auth = authorize(env, region, scopes)
    api_domain = auth["api_domain"] or DATA_CENTERS[region][1]
    books = Books(api_domain, auth["_access_token"])
    probes: list[Probe] = []
    findings: dict[str, Any] = {}

    try:
        orgs = probe(books, probes, "organizations", "organizations", list_key="organizations").get("organizations") or []
        if not orgs:
            raise SystemExit(
                "Zoho returned success with ZERO organisations: the Zoho account that gave consent has no "
                "Zoho Books organisation in this data center (wrong account, or not a Books user there).\n"
                f"  api_domain={api_domain}  accounts_server={auth['accounts_server']}  "
                f"callback location={auth['callback_location'] or '-'}  "
                f"callback accounts-server={auth['callback_accounts_server'] or '-'}"
            )
        org_id = env.get("ZOHO_SPIKE_ORG_ID") or ""
        returned_ids = [str(o.get("organization_id")) for o in orgs]
        if org_id and org_id not in returned_ids:
            raise SystemExit(
                f"Organisation {org_id} is not available to this Zoho account. Zoho returned: "
                + ", ".join(f"{o.get('name')} ({o.get('organization_id')})" for o in orgs)
            )
        if not org_id:
            if len(orgs) == 1:
                org_id = str(orgs[0]["organization_id"])
            else:
                for i, org in enumerate(orgs):
                    print(f"  [{i}] {org.get('name')} ({org.get('organization_id')})")
                org_id = str(orgs[int(input("Choose organisation index: "))]["organization_id"])
        books.org_id = org_id
        findings["organization_count"] = len(orgs)

        org = probe(books, probes, "organization_detail", f"organizations/{org_id}").get("organization") or {}
        tz = ZoneInfo(org.get("time_zone") or "Asia/Kolkata")
        today = datetime.now(tz).date()
        # Whether Zoho's fiscal_year_start_month is 0- or 1-based is unverified: record the raw value
        # (April would be 3 if 0-based, 4 if 1-based) and probe with the Indian April–March year.
        raw_fy = org.get("fiscal_year_start_month")
        fy_start = fiscal_year_start(today, 4)
        prev_fy_start = date(fy_start.year - 1, fy_start.month, 1)
        month_start = today.replace(day=1)
        last_month_end = month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        findings["org"] = {
            "name": org.get("name"),
            "organization_id": mask(org_id),
            "currency_code": org.get("currency_code"),
            "time_zone": org.get("time_zone"),
            "fiscal_year_start_month_raw": raw_fy,
            "country": org.get("country") or org.get("country_code"),
            "is_default_org": org.get("is_default_org"),
            "today_in_org_tz": today.isoformat(),
            "fy_start_used": fy_start.isoformat(),
        }

        contacts = paginate(books, probes, "contacts_customers", "contacts", "contacts", {"contact_type": "customer"})
        invoices = paginate(books, probes, "invoices", "invoices", "invoices")
        if invoices:
            probe(books, probes, "invoice_detail", f"invoices/{invoices[0]['invoice_id']}")
        payments = paginate(books, probes, "customerpayments", "customerpayments", "customerpayments")
        expenses = paginate(books, probes, "expenses", "expenses", "expenses")
        if expenses:
            probe(books, probes, "expense_detail", f"expenses/{expenses[0]['expense_id']}")
        accounts = paginate(books, probes, "chartofaccounts", "chartofaccounts", "chartofaccounts")
        probe(books, probes, "bankaccounts", "bankaccounts", list_key="bankaccounts")

        date_range = {"from_date": fy_start.isoformat(), "to_date": today.isoformat()}
        probe(books, probes, "report_pnl_fytd", "reports/profitandloss", date_range)
        probe(books, probes, "report_pnl_last_month", "reports/profitandloss",
              {"from_date": last_month_start.isoformat(), "to_date": last_month_end.isoformat()})
        probe(books, probes, "report_pnl_prev_fy", "reports/profitandloss",
              {"from_date": prev_fy_start.isoformat(), "to_date": (fy_start - timedelta(days=1)).isoformat()})
        probe(books, probes, "report_balancesheet", "reports/balancesheet", date_range)
        # Monthly P&L (one call per month) — the planned source for accrual trends.
        month = date(prev_fy_start.year + 1, 3, 1)  # March of the previous FY (FY-boundary test)
        while month <= today:
            next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
            probe(books, probes, f"report_pnl_{month:%Y_%m}", "reports/profitandloss",
                  {"from_date": month.isoformat(), "to_date": (next_month - timedelta(days=1)).isoformat()})
            month = next_month
        probe(books, probes, "report_pnl_fytd_cash", "reports/profitandloss", {**date_range, "cash_based": "true"})
        probe(books, probes, "report_pnl_fytd_groupby_month", "reports/profitandloss",
              {**date_range, "group_by": "month"})
        for report in EXPLORATORY_REPORTS:
            probe(books, probes, f"report_{report}", f"reports/{report}", date_range)

        tax_accounts = [a for a in accounts if TAX_NAME.search(str(a.get("account_name", "")))
                        or "tax" in str(a.get("account_type", "")).lower()]
        for account in tax_accounts[:3]:
            probe(books, probes, f"account_txn_{account.get('account_id')}", "chartofaccounts/transactions",
                  {"account_id": account.get("account_id"), "date.start": fy_start.isoformat(),
                   "date.end": today.isoformat()}, list_key="transactions")

        vendor_payments = probe(books, probes, "vendorpayments", "vendorpayments",
                                list_key="vendorpayments").get("vendorpayments") or []
        bills = probe(books, probes, "bills", "bills", list_key="bills").get("bills") or []
        for name, rows, id_key, path in (("customerpayment_detail", payments, "payment_id", "customerpayments"),
                                         ("bill_detail", bills, "bill_id", "bills"),
                                         ("vendorpayment_detail", vendor_payments, "payment_id", "vendorpayments")):
            record_id = rows[0].get(id_key) if rows else None
            if record_id:
                probe(books, probes, name, f"{path}/{record_id}")

        findings["invoice_status_counts"] = dict(Counter(str(i.get("status")) for i in invoices))
        findings["invoice_currency_codes"] = dict(Counter(str(i.get("currency_code")) for i in invoices))
        findings["invoice_date_span"] = [min((i.get("date") for i in invoices), default=None),
                                         max((i.get("date") for i in invoices), default=None)]
        findings["account_type_counts"] = dict(Counter(str(a.get("account_type")) for a in accounts))
        findings["tax_like_accounts"] = [
            {"name": a.get("account_name"), "account_type": a.get("account_type")} for a in tax_accounts
        ]
        findings["record_counts"] = {"customers": len(contacts), "invoices": len(invoices),
                                     "customer_payments": len(payments), "expenses": len(expenses),
                                     "accounts": len(accounts)}
    finally:
        findings["revoke_refresh_token"] = revoke(auth["accounts_server"], auth["_refresh_token"])
        print(f"Refresh token revoke: {findings['revoke_refresh_token']}")
        books.http.close()

    write_report(auth, region, scopes, api_domain, books, probes, findings)
    print(f"\nDone. {books.calls} Books API calls.\n  Sanitised report: {REPORT_PATH.relative_to(REPO_ROOT)}"
          f"\n  Raw responses (local only, real data): {RAW_DIR.relative_to(REPO_ROOT)}")


def write_report(auth: dict, region: str, scopes: list[str], api_domain: str, books: Books,
                 probes: list[Probe], findings: dict[str, Any]) -> None:
    lines = [
        "# Phase 0 — Zoho Books spike report (sanitised)",
        "",
        f"Generated {datetime.now().isoformat(timespec='seconds')} by `scripts/phase0/zoho_spike.py`. "
        "Contains field names, types, counts and enum values only — **no amounts**. "
        "Raw responses are in `.spike/raw/` (git-ignored).",
        "",
        "## OAuth / data center",
        "",
        f"- Region requested: `{region}` · accounts server used: `{auth['accounts_server']}`",
        f"- Callback query params received: `{', '.join(auth['callback_param_names'])}`",
        f"- Callback `location`: `{auth['callback_location'] or '—'}` · `accounts-server`: "
        f"`{auth['callback_accounts_server'] or '—'}`",
        f"- Token response keys: `{', '.join(auth['token_response_keys'])}` · api_domain: `{api_domain}` · "
        f"expires_in: `{auth['expires_in']}` · refresh token issued: `{auth['has_refresh_token']}`",
        f"- Scopes requested: `{', '.join(scopes)}`",
        f"- Scopes granted (if reported): `{auth['granted_scope'] or 'not reported'}`",
        f"- Refresh token revoked at end: {findings.get('revoke_refresh_token')}",
        "",
        "## Probes",
        "",
        "| Probe | Path | HTTP | Zoho code | Calls | ms | Records | Note / message |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in probes:
        detail = p.note or (p.message if p.status != 200 else "")
        lines.append(f"| {p.name} | `{p.path}` | {p.status} | {p.code} | {p.calls} | {p.ms} | "
                     f"{'' if p.records is None else p.records} | {detail} |")
    lines += [
        "",
        f"**Total Books API calls:** {books.calls}",
        "",
        "## Rate-limit related response headers (last seen)",
        "",
        "```json",
        json.dumps(books.rate_headers, indent=2) if books.rate_headers else "{}  (none returned)",
        "```",
        "",
        "## Findings",
        "",
        "```json",
        json.dumps(findings, indent=2, default=str),
        "```",
        "",
        "## Response shapes",
        "",
    ]
    for p in probes:
        if p.shape is None or p.status != 200:
            continue
        lines += [f"### {p.name}", "", "```json", json.dumps(p.shape, indent=2)[:6000], "```", ""]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
