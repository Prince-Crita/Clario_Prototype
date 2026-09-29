# Zoho Books Integration Plan

## Goal
Create a reusable read-only Zoho Books integration layer for Clario.

Zoho Books uses OAuth 2.0. Access tokens are temporary and refresh tokens are used to obtain new access tokens. Never expose tokens in frontend code or source control.

Official OAuth documentation:
https://www.zoho.com/books/api/v3/oauth/

## Environment

```env
ZOHO_CLIENT_ID=
ZOHO_CLIENT_SECRET=
ZOHO_REDIRECT_URI=
ZOHO_ACCOUNTS_URL=
ZOHO_API_BASE_URL=
ZOHO_ORGANIZATION_ID=
ZOHO_REFRESH_TOKEN=
GOOGLE_API_KEY=
GEMINI_MODEL=
```

For an India organization, the `.in` Zoho data center is commonly applicable, but make the domain configurable.

## OAuth Flow
1. Register the application in Zoho Developer Console.
2. Configure redirect URI.
3. Request minimum read-only scopes.
4. Authorize the Zoho Books organization.
5. Receive authorization code.
6. Exchange it for access and refresh tokens.
7. Store the refresh token securely for local development.
8. Refresh access tokens when required.
9. Send access tokens in the Authorization header.

Zoho documents access tokens as valid for one hour and refresh tokens as remaining usable until revoked.

## Initial Scopes
Start with the minimum read-only scopes required, such as:

```text
ZohoBooks.invoices.READ
ZohoBooks.contacts.READ
ZohoBooks.settings.READ
ZohoBooks.expenses.READ
ZohoBooks.customerpayments.READ
```

Do not request CREATE/UPDATE/DELETE scopes for this MVP.

## Organization
Zoho Books treats each business as an organization with its own organization ID. Include `organization_id` on APIs that require it.

Official API introduction:
https://www.zoho.com/books/api/v3/introduction/

## Client Structure

```text
zoho_books/
  client.py
  oauth.py
  models.py
  errors.py
```

The client should handle authentication, token refresh, organization ID, safe GET retries, pagination, response validation and error handling.

## First APIs
Start with:
1. Organizations
2. Invoices
3. Contacts/customers
4. Customer payments
5. Expenses
6. Items/settings
7. Relevant reports

Zoho Books provides reports including Profit and Loss, Cash Flow Statement, Balance Sheet, Inventory Summary, Inventory Valuation, Sales by Customer, Sales by Item, Receivables Aging and Invoice Details.

Reports reference:
https://www.zoho.com/in/books/help/reports/

## Normalization
Do not send raw Zoho responses directly to the LLM. Convert them into small business models.

Example:

```text
Invoice
- invoice_id
- invoice_number
- customer
- invoice_date
- due_date
- status
- total
- balance
- currency
```
