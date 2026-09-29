# Phase 0 — Verify (status & runbook)

Phase 0 verified the environment and the external unknowns before the design is frozen
(see `docs/FINAL_ARCHITECTURE_PLAN.md` §34). **No application code was written in this phase.**

**Outcome (2026-09-26):** Phase 0 is complete for everything that can be verified without the live organisation. The results are folded into `FINAL_ARCHITECTURE_PLAN.md` v1.1. Open items are carried forward as plan risks R2, R3, R11 and R12.

## Status

| # | Item | Status |
|---|---|---|
| 0.1 | Python 3.12 available | ✅ 3.12.14 via `uv` (user-level; run as `python -m uv …`) |
| 0.2 | Existing Postgres databases listed (read-only) | ✅ `postgres`, `smc_final_check` found; untouched |
| 0.3 | `clario_dev` and `clario_test` created (PostgreSQL 16.15, UTF8) | ✅ empty, no tables |
| 0.4 | Git repository initialised (`main`), `.gitignore` for secrets, director PDFs, spike output; brand: only `reference/brand/logo/LOGO.svg` versioned, other design files kept local | ✅ nothing committed yet |
| 0.5 | Reference material moved to `reference/` (demo, director PDFs, brand) | ✅ all 84 demo files verified |
| 0.6 | Local `.env` created (git-ignored): DB URLs, generated secrets, Zoho and Groq keys | ✅ |
| 0.7 | Environment check | ✅ all checks pass |
| 0.8 | Zoho API Console: server-based app registered (India data center) | ✅ |
| 0.9 | Zoho spike | ✅ against the **trial** organisation `60089553909` with a TEST dataset; see [`zoho-spike-report.md`](zoho-spike-report.md) |
| 0.9a | TEST dataset and hand-calculated figure verification | ✅ **53/53 checks pass**; see [`test-data-verification.md`](test-data-verification.md) |
| 0.10 | Groq model evaluation | ✅ `openai/gpt-oss-120b` chosen; see [`groq-eval-report.md`](groq-eval-report.md) |
| 0.11 | Director questions sent | ⏳ **needs you**: send [`director-questions.md`](director-questions.md) |
| 0.12 | Findings folded into the plan | ✅ `FINAL_ARCHITECTURE_PLAN.md` v1.1 (§16.3, §16.4, §17, §20, §21, §23.2, §24.2, §34, §36, §39) |

### Carried forward (not verified in Phase 0)

| Item | Why not | Where it is tracked |
|---|---|---|
| GST / tax-summary source | The trial organisation has GST disabled, so the tax summary is empty | Plan R2; before Phase 6 |
| Live-organisation data shapes and paid-plan API limits | The live organisation `60069959305` was deliberately not accessed | Plan R11; needs explicit approval to run the read-only spike there |
| Non-India data centers | Only the India flow was tested | Plan R3 |
| Production Groq tier | The evaluation key spent long periods on 429 rate limits | Plan R12 |

## Key findings

1. **Reports need `ZohoBooks.reports.READ`.** `accountants.READ` alone gets 401, code 57 on every `reports/*` call. The demo lacked this scope.
2. **The P&L report maps cleanly onto the director's definitions.** The director's "Net P&L" is Zoho's **Operating Profit**; Zoho's *Net Profit/Loss* also includes non-operating items (director Q4).
3. **Monthly P&L takes one call per month**, because `group_by=month` is ignored. `cash_based=true` works.
4. **Data rules for the connector:**
   - Amounts are JSON floats, so parse them to `Decimal`.
   - Draft and void invoices still carry a balance.
   - Zoho's `status` labels a partly-paid invoice as `overdue`, so status is derived.
   - The invoice list has no base-currency total, and the expense list has no account IDs.
5. **Rate limit:** 1,000 calls a day on the trial. A full 2-year refresh is estimated at about 35–45 calls.
6. **AI:** every Groq model was 100% grounded and 100% correct on refusals. `gpt-oss-120b` was chosen: its failures are recoverable malformed tool calls, while `gpt-oss-20b` repeatedly failed the follow-up question.

## TEST dataset (trial organisation `60089553909` only)

Created by `scripts/phase0/seed_test_data.py`. It is hard-wired to the trial organisation, refuses any other, used a separate one-off write consent whose token was revoked, and records every ID in `.spike/seed-manifest.json`, which is local and git-ignored. Every record is named or referenced **TEST**, and GST was not enabled.

| Records | Details |
|---|---|
| Bank account | `TEST Bank Current` |
| Customers / vendor | `TEST Customer Alpha`, `TEST Customer Beta`, `TEST Customer Gamma` · `TEST Vendor One` |
| Invoices (7) | INV-000001 (20 Mar, 10,000, paid) · INV-000002 (10 Jul, 50,000, paid) · INV-000003 (05 Aug, 30,000, part-paid 15,000, overdue) · INV-000004 (28 Aug, 20,000, overdue) · INV-000005 (15 Sep, 8,000, open) · INV-000006 (draft, 5,000) · INV-000007 (void, 3,000) |
| Customer payments (3) | 05 Apr 10,000 · 25 Aug 15,000 · 10 Sep 50,000, all to TEST Bank Current |
| Expenses (4) | 15 Jul Salaries 40,000 · 10 Aug Rent 12,000 · 05 Sep COGS 9,000 · 18 Sep IT 2,500 (Petty Cash) |
| Bill + vendor payment | TEST-BILL-001, 01 Aug, Office Supplies 6,000 · paid 02 Sep |

**These are test figures only.** They validate the API, the mapping and the calculation rules, not the director's real numbers.

## Commands (run from the repo root)

```powershell
python -m uv run scripts/phase0/verify_env.py          # environment check; prints no secrets
python -m uv run scripts/phase0/zoho_spike.py          # read-only; opens a browser for Zoho consent
python -m uv run scripts/phase0/verify_test_figures.py # compares .spike/raw against hand-calculated TEST figures
python -m uv run scripts/phase0/groq_eval.py --repeat 2
# One-off, already done; refuses to run twice:
python -m uv run scripts/phase0/seed_test_data.py
```

Useful overrides for the spike (environment variables):
- `ZOHO_SPIKE_ORG_ID=60089553909` pins the organisation, and the spike verifies Zoho returns it.
- `ZOHO_SPIKE_SCOPES=…` sets the scope list.

## Zoho API Console settings (development)

| Field | Value |
|---|---|
| Console | <https://api-console.zoho.in> (India data center) |
| Client type | Server-based Application |
| Homepage URL | `http://localhost:5173` |
| Authorized Redirect URI | `http://localhost:5173/api/v1/oauth/zoho-books/callback` (exact, no trailing slash) |

Production will need a second redirect URI, `https://<production-host>/api/v1/oauth/zoho-books/callback`, once the host is decided.

## Notes for the team
- `uv` was installed with `pip install --user uv` and is invoked as `python -m uv`. Running `python -m uv python update-shell` once puts uv-managed Python on your PATH.
- `psql` is not on PATH. PostgreSQL 16 is installed at `D:\Program Files\PostgreSQL\16\bin\`.
- Never commit `.env`, `.spike/` or `reference/director-pdfs/`; `.gitignore` already covers them.
- The generated report files (`zoho-spike-report.md`, `groq-eval-report.md`, `test-data-verification.md`) are overwritten when their script is re-run. The hand-written "Interpretation" sections at the end of the first two would need re-adding.
