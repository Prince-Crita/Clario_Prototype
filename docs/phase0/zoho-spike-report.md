# Phase 0 — Zoho Books spike report (sanitised)

Generated 2026-09-26T18:19:37 by `scripts/phase0/zoho_spike.py`. Contains field names, types, counts and enum values only — **no amounts**. Raw responses are in `.spike/raw/` (git-ignored).

## OAuth / data center

- Region requested: `in` · accounts server used: `https://accounts.zoho.in`
- Callback query params received: `accounts-server, code, location, state`
- Callback `location`: `in` · `accounts-server`: `https://accounts.zoho.in`
- Token response keys: `access_token, api_domain, expires_in, refresh_token, scope, token_type` · api_domain: `https://www.zohoapis.in` · expires_in: `3600` · refresh token issued: `True`
- Scopes requested: `ZohoBooks.settings.READ, ZohoBooks.invoices.READ, ZohoBooks.contacts.READ, ZohoBooks.customerpayments.READ, ZohoBooks.expenses.READ, ZohoBooks.accountants.READ, ZohoBooks.reports.READ, ZohoBooks.banking.READ, ZohoBooks.bills.READ, ZohoBooks.vendorpayments.READ`
- Scopes granted (if reported): `ZohoBooks.settings.READ ZohoBooks.invoices.READ ZohoBooks.contacts.READ ZohoBooks.customerpayments.READ ZohoBooks.expenses.READ ZohoBooks.accountants.READ ZohoBooks.reports.READ ZohoBooks.banking.READ ZohoBooks.bills.READ ZohoBooks.vendorpayments.READ`
- Refresh token revoked at end: HTTP 200

## Probes

| Probe | Path | HTTP | Zoho code | Calls | ms | Records | Note / message |
|---|---|---|---|---|---|---|---|
| organizations | `organizations` | 200 | 0 | 1 | 360 | 1 |  |
| organization_detail | `organizations/60089553909` | 200 | 0 | 1 | 142 |  |  |
| contacts_customers | `contacts` | 200 | 0 | 1 | 189 | 3 |  |
| invoices | `invoices` | 200 | 0 | 1 | 276 | 7 |  |
| invoice_detail | `invoices/4235431000000042121` | 200 | 0 | 1 | 324 |  |  |
| customerpayments | `customerpayments` | 200 | 0 | 1 | 134 | 3 |  |
| expenses | `expenses` | 200 | 0 | 1 | 185 | 4 |  |
| expense_detail | `expenses/4235431000000042228` | 200 | 0 | 1 | 271 |  |  |
| chartofaccounts | `chartofaccounts` | 200 | 0 | 1 | 149 | 67 |  |
| bankaccounts | `bankaccounts` | 200 | 0 | 1 | 163 | 3 |  |
| report_pnl_fytd | `reports/profitandloss` | 200 | 0 | 1 | 130 |  |  |
| report_pnl_last_month | `reports/profitandloss` | 200 | 0 | 1 | 126 |  |  |
| report_pnl_prev_fy | `reports/profitandloss` | 200 | 0 | 1 | 124 |  |  |
| report_balancesheet | `reports/balancesheet` | 200 | 0 | 1 | 137 |  |  |
| report_pnl_2026_03 | `reports/profitandloss` | 200 | 0 | 1 | 154 |  |  |
| report_pnl_2026_04 | `reports/profitandloss` | 200 | 0 | 1 | 117 |  |  |
| report_pnl_2026_05 | `reports/profitandloss` | 200 | 0 | 1 | 116 |  |  |
| report_pnl_2026_06 | `reports/profitandloss` | 200 | 0 | 1 | 121 |  |  |
| report_pnl_2026_07 | `reports/profitandloss` | 200 | 0 | 1 | 122 |  |  |
| report_pnl_2026_08 | `reports/profitandloss` | 200 | 0 | 1 | 123 |  |  |
| report_pnl_2026_09 | `reports/profitandloss` | 200 | 0 | 1 | 153 |  |  |
| report_pnl_fytd_cash | `reports/profitandloss` | 200 | 0 | 1 | 120 |  |  |
| report_pnl_fytd_groupby_month | `reports/profitandloss` | 200 | 0 | 1 | 169 |  |  |
| report_trialbalance | `reports/trialbalance` | 200 | 0 | 1 | 135 |  |  |
| report_generalledger | `reports/generalledger` | 200 | 0 | 1 | 159 |  |  |
| report_accounttransactions | `reports/accounttransactions` | 404 | 5 | 1 | 52 |  | We couldnt find any resource for the given ID. Please verify the ID and try again. |
| report_taxsummary | `reports/taxsummary` | 200 | 0 | 1 | 151 |  |  |
| account_txn_4235431000000000468 | `chartofaccounts/transactions` | 200 | 0 | 1 | 277 | 0 |  |
| account_txn_4235431000000000474 | `chartofaccounts/transactions` | 200 | 0 | 1 | 274 | 0 |  |
| vendorpayments | `vendorpayments` | 200 | 0 | 1 | 114 | 1 |  |
| bills | `bills` | 200 | 0 | 1 | 144 | 1 |  |
| customerpayment_detail | `customerpayments/4235431000000042164` | 200 | 0 | 1 | 194 |  |  |
| bill_detail | `bills/4235431000000042239` | 200 | 0 | 1 | 323 |  |  |
| vendorpayment_detail | `vendorpayments/4235431000000042249` | 200 | 0 | 1 | 191 |  |  |

**Total Books API calls:** 34

## Rate-limit related response headers (last seen)

```json
{
  "x-rate-limit-limit": "1000",
  "x-rate-limit-reset": "20421",
  "x-rate-limit-remaining": "879"
}
```

## Findings

```json
{
  "organization_count": 1,
  "org": {
    "name": "Crita Creative LLP",
    "organization_id": "\u20263909",
    "currency_code": "INR",
    "time_zone": "Asia/Calcutta",
    "fiscal_year_start_month_raw": "april",
    "country": null,
    "is_default_org": false,
    "today_in_org_tz": "2026-09-26",
    "fy_start_used": "2026-04-01"
  },
  "invoice_status_counts": {
    "void": 1,
    "draft": 1,
    "sent": 1,
    "overdue": 2,
    "paid": 2
  },
  "invoice_currency_codes": {
    "INR": 7
  },
  "invoice_date_span": [
    "2026-03-20",
    "2026-09-20"
  ],
  "account_type_counts": {
    "other_current_asset": 4,
    "cash": 2,
    "bank": 1,
    "accounts_receivable": 1,
    "fixed_asset": 1,
    "other_current_liability": 5,
    "accounts_payable": 1,
    "long_term_liability": 2,
    "other_liability": 1,
    "equity": 8,
    "income": 7,
    "expense": 27,
    "cost_of_goods_sold": 5,
    "other_expense": 1,
    "stock": 1
  },
  "tax_like_accounts": [
    {
      "name": "Advance Tax",
      "account_type": "other_current_asset"
    },
    {
      "name": "Tax Payable",
      "account_type": "other_current_liability"
    }
  ],
  "record_counts": {
    "customers": 3,
    "invoices": 7,
    "customer_payments": 3,
    "expenses": 4,
    "accounts": 67
  },
  "revoke_refresh_token": "HTTP 200"
}
```

## Response shapes

### organizations

```json
{
  "isOrgNotSupported": "bool",
  "organization_id": "str",
  "name": "str",
  "org_alias_name": "str",
  "contact_name": "str",
  "email": "str",
  "source": "int",
  "country": "str",
  "country_code": "str",
  "org_settings": "bool",
  "is_ziedition": "bool",
  "custom_field_type": "int",
  "custom_fields": [
    {
      "index": "int",
      "label": "str",
      "value": "str"
    },
    "(5 items)"
  ],
  "is_sku_enabled": "bool",
  "phone": "str",
  "org_type": "str",
  "state_code": "str",
  "state": "str",
  "zoho_one_org": "str",
  "zi_zb_edition": "int",
  "org_created_app_source": "int",
  "zi_zb_client": "int",
  "is_solo_org": "bool",
  "partners_domain": "str",
  "version": "str",
  "version_formatted": "str",
  "is_search360_enabled": "str",
  "is_sales_inclusive_tax_enabled": "bool",
  "sales_tax_type": "str",
  "tax_group_enabled": "bool",
  "language_code": "str",
  "fiscal_year_start_month": "int",
  "time_zone": "str",
  "field_separator": "str",
  "time_zone_formatted": "str",
  "can_change_timezone": "bool",
  "digital_signature_mode": "str",
  "is_dsign_required": "bool",
  "can_sign_invoice": "bool",
  "is_user_dsign_mandatory": "bool",
  "currency_id": "str",
  "currency_code": "str",
  "currency_symbol": "str",
  "currency_format": "str",
  "price_precision": "int",
  "org_joined_app_list": [
    "str",
    "(1 items)"
  ],
  "is_designated_zone": "bool",
  "is_free_zone": "bool",
  "is_registered_for_composite_scheme": "bool",
  "is_sales_reverse_charge_enabled": "bool",
  "is_export_with_payment_enabled": "bool",
  "is_registered_for_tax": "bool",
  "is_tax_registered": "bool",
  "is_international_trade_enabled": "bool",
  "is_gst_india_version": "bool",
  "is_registered_for_gst": "bool",
  "is_multientity_org": "bool",
  "is_multientity_enabled": "bool",
  "isOrgActive": "bool",
  "plan_type": "int",
  "plan_name": "str",
  "plan_period": "str",
  "account_created_date": "str",
  "account_created_date_formatted": "str",
  "is_org_active": "bool",
  "is_quick_setup_completed": "bool",
  "is_trial_period_extended": "bool",
  "is_trial_expired": "bool",
  "is_invoice_pmt_tds_allowed": "bool",
  "is_hsn_or_sac_enabled": "bool",
  "mode": "str",
  "other_active_services": [
    "(empty)"
  ],
  "is_last_active_service": "bool",
  "support_email": "str",
  "can_show_document_tab": "bool",
  "is_scan_preference_enabled": "bool",
  "is_user_accountant": "bool",
  "is_user_last_admin": "bool",
  "is_user_super_admin": "bool",
  "user_status": "int",
  "user_status_formatted": "str",
  "org_action": "str",
  "AppList": [
    "str",
    "(1 items)"
  ],
  "is_zpayroll_grid": "bool",
  "is_default_org": "bool",
  "is_subscription_paused": "bool"
}
```

### organization_detail

```json
{
  "code": "int",
  "message": "str",
  "organization": {
    "organization_id": "str",
    "name": "str",
    "first_name": "str",
    "last_name": "str",
    "logo_url": "str",
    "store_logo_url": "str",
    "is_default_org": "bool",
    "user_role": "str",
    "role_id": "str",
    "account_created_date": "str",
    "time_zone": "str",
    "language_code": "str",
    "customer_languages": [
      "str",
      "(1 items)"
    ],
    "date_format": "str",
    "field_separator": "str",
    "fiscal_year_start_month": "str",
    "primary_domain_name": "str",
    "is_public_domain": "bool",
    "can_show_authentication_warning": "bool",
    "fiscal_year_start_date": "int",
    "contact_name": "str",
    "industry_type": "str",
    "industry_size": "str",
    "previous_invoicing_option": "str",
    "previous_product_option": "str",
    "company_id_label": "str",
    "custom_field_type": "int",
    "is_trial_period_extended": "bool",
    "is_sez": "bool",
    "is_designated_zone": "bool",
    "is_free_zone": "bool",
    "store_url": "str",
    "company_id_value": "str",
    "label_for_company_id": "str",
    "tax_id_label": "str",
    "tax_id_value": "str",
    "currency_id": "str",
    "currency_code": "str",
    "currency_symbol": "str",
    "currency_format": "str",
    "price_precision": "int",
    "status": "str:'1'",
    "address": {
      "street_address1": "str",
      "street_address2": "str",
      "city": "str",
      "state": "str",
      "state_code": "str",
      "country": "str",
      "zip": "str",
      "latitude": "str",
      "longitude": "str",
      "attention": "str"
    },
    "tax_settings": {
      "is_tax_registered": "bool",
      "tax_reg_no": "str"
    },
    "is_registered_for_gst": "bool",
    "is_composition_scheme_enabled": "bool",
    "org_address": "str",
    "remit_to_address": "str",
    "phone": "str",
    "fax": "str",
    "website": "str",
    "version": "str",
    "weight_unit": "str",
    "dimension_unit": "str",
    "business_type": "str",
    "email": "str",
    "unverified_emails_count": "int",
    "tax_basis": "str",
    "custom_fields": [
      {
        "index": "int",
        "label": "str",
        "value": "str"
      },
      "(5 items)"
    ],
    "custom_field_hash": {
      "cf_1_unformatted": "str",
      "cf_1": "str",
      "cf_2_unformatted": "str",
      "cf_2": "str",
      "cf_3_unformatted": "str",
      "cf_3": "str",
      "cf_4_unformatted": "str",
      "cf_4": "str",
      "cf_5_unformatted": "str",
      "cf_5": "str"
    },
    "is_org_active": "bool",
    "is_new_customer_custom_fields": "bool",
    "is_late_fee_disabled": "bool",
    "is_portal_enabled": "bool",
    "org_joined_app_list": [
      "str",
      "(1 items)"
    ],
    "company_identification_labels_list": [
      "(empty)"
    ],
    "portal_name": "str",
    "is_estimate_enabled": "bool",
    "is_project_enabled": "bool",
    "is_purchaseorder_enabled": "bool",
    "is_salesorder_enabled": "bool",
    "is_retainerinvoice_enabled": "bool",
    "mode": "str",
    "payments_url": "str"
  }
}
```

### contacts_customers

```json
{
  "contact_id": "str",
  "contact_name": "str",
  "customer_name": "str",
  "vendor_name": "str",
  "company_name": "str",
  "website": "str",
  "language_code": "str",
  "language_code_formatted": "str",
  "contact_type": "str:'customer'",
  "contact_type_formatted": "str",
  "status": "str:'active'",
  "customer_sub_type": "str",
  "source": "str",
  "is_linked_with_zohocrm": "bool",
  "payment_terms": "int",
  "payment_terms_id": "str",
  "payment_terms_label": "str",
  "currency_id": "str",
  "twitter": "str",
  "facebook": "str",
  "currency_code": "str",
  "outstanding_receivable_amount": "float",
  "outstanding_receivable_amount_bcy": "float",
  "outstanding_payable_amount": "float",
  "outstanding_payable_amount_bcy": "float",
  "unused_credits_receivable_amount": "float",
  "unused_credits_receivable_amount_bcy": "float",
  "unused_credits_payable_amount": "float",
  "unused_credits_payable_amount_bcy": "float",
  "first_name": "str",
  "last_name": "str",
  "email": "str",
  "phone": "str",
  "mobile": "str",
  "portal_status": "str",
  "portal_status_formatted": "str",
  "created_time": "str",
  "created_time_formatted": "str",
  "last_modified_time": "str",
  "last_modified_time_formatted": "str",
  "custom_fields": [
    "(empty)"
  ],
  "custom_field_hash": {},
  "contactperson_custom_fields": [
    "(empty)"
  ],
  "tags": [
    "(empty)"
  ],
  "ach_supported": "bool",
  "has_attachment": "bool",
  "pan_no": "str",
  "registration_details": {}
}
```

### invoices

```json
{
  "ach_payment_initiated": "bool",
  "invoice_id": "str",
  "zcrm_potential_id": "str",
  "customer_id": "str",
  "zcrm_potential_name": "str",
  "customer_name": "str",
  "company_name": "str",
  "registration_details": {},
  "status": "str:'void'",
  "invoice_number": "str",
  "reference_number": "str",
  "date": "str",
  "due_date": "str",
  "issued_date": "str",
  "due_days": "str",
  "email": "str",
  "type": "str",
  "project_name": "str",
  "billing_address": {
    "address": "str",
    "street2": "str",
    "city": "str",
    "state": "str",
    "zipcode": "str",
    "country": "str",
    "phone": "str",
    "fax": "str",
    "attention": "str"
  },
  "shipping_address": {
    "address": "str",
    "street2": "str",
    "city": "str",
    "state": "str",
    "zipcode": "str",
    "country": "str",
    "phone": "str",
    "fax": "str",
    "attention": "str"
  },
  "country": "str",
  "phone": "str",
  "created_by": "str",
  "total": "float",
  "balance": "float",
  "payment_expected_date": "str",
  "custom_fields": [
    "(empty)"
  ],
  "custom_field_hash": {},
  "tags": [
    "(empty)"
  ],
  "salesperson_name": "str",
  "shipping_charge": "float",
  "adjustment": "float",
  "created_time": "str",
  "last_modified_time": "str",
  "updated_time": "str",
  "is_viewed_by_client": "bool",
  "has_attachment": "bool",
  "client_viewed_time": "str",
  "is_emailed": "bool",
  "color_code": "str",
  "current_sub_status_id": "str",
  "current_sub_status": "str",
  "currency_id": "str",
  "schedule_time": "str",
  "currency_code": "str",
  "currency_symbol": "str",
  "is_pre_gst": "bool",
  "template_type": "str",
  "no_of_copies": "int",
  "show_no_of_copies": "bool",
  "invoice_source": "str",
  "sales_channel": "str",
  "transaction_type": "str",
  "reminders_sent": "int",
  "last_reminder_sent_date": "str",
  "last_payment_date": "str",
  "template_id": "str",
  "documents": "str",
  "salesperson_id": "str",
  "write_off_amount": "float",
  "exchange_rate": "float",
  "unprocessed_payment_amount": "float"
}
```

### invoice_detail

```json
{
  "code": "int",
  "message": "str",
  "invoice": {
    "invoice_id": "str",
    "channel_invoice_id": "str",
    "account_identifier": "str",
    "invoice_number": "str",
    "date": "str",
    "due_date": "str",
    "issued_date": "str",
    "offline_created_date_with_time": "str",
    "customer_id": "str",
    "customer_name": "str",
    "customer_custom_fields": [
      "(empty)"
    ],
    "customer_custom_field_hash": {},
    "email": "str",
    "currency_id": "str",
    "currency_formatter": {
      "decimal_separator": "str",
      "number_separator": "str",
      "secondary_grouping_size": "int"
    },
    "invoice_source": "str",
    "currency_code": "str",
    "currency_symbol": "str",
    "currency_name_formatted": "str",
    "status": "str:'void'",
    "unprocessed_payment_amount": "float",
    "custom_fields": [
      "(empty)"
    ],
    "custom_field_hash": {},
    "recurring_invoice_id": "str",
    "is_last_child_invoice": "bool",
    "payment_terms": "int",
    "payment_terms_label": "str",
    "payment_terms_id": "str",
    "invoice_installments": [
      "(empty)"
    ],
    "payment_reminder_enabled": "bool",
    "payment_made": "float",
    "zcrm_potential_id": "str",
    "zcrm_potential_name": "str",
    "reference_number": "str",
    "discount_code": "str",
    "lock_details": {
      "can_lock": "bool"
    },
    "locked_actions": [
      "(empty)"
    ],
    "lock_detail": {
      "can_lock": "bool",
      "custom_locks": [
        "(empty)"
      ],
      "system_locks": [
        "(empty)"
      ]
    },
    "is_progress_invoice": "bool",
    "can_show_kit_return": "bool",
    "is_kit_partial_return": "bool",
    "show_convert_to_package": "bool",
    "show_convert_to_shipment": "bool",
    "line_items": [
      {
        "line_item_id": "str",
        "item_id": "str",
        "item_order": "int",
        "name": "str",
        "internal_name": "str",
        "description": "str",
        "discount_account_id": "str",
        "discount_account_name": "str",
        "unit": "str",
        "quantity": "float",
        "discount_amount": "float",
        "discount": "float",
        "discounts": [
          "(empty)"
        ],
        "bcy_rate": "float",
        "rate": "float",
        "account_id": "str",
        "account_name": "str",
        "header_id": "str",
        "header_name": "str",
        "pricebook_id": "str",
        "tax_id": "str",
        "tax_name": "str",
        "tax_type": "str",
        "tax_percentage": "int",
        "item_total": "float",
        "item_custom_fields": [
          "(empty)"
        ],
        "pricing_scheme": "str",
        "tags": [
          "(empty)"
        ],
        "documents": [
          "(empty)"
        ],
        "image_document_id": "str",
        "tds_tax_id": "str",
        "tds_tax_name": "str",
        "tds_tax_percentage": "str",
        "tds_tax_amount": "float",
        "line_item_taxes": [
          "(empty)"
        ],
        "line_item_tds": [
          "(empty)"
        ],
        "bill_id": "str",
        "bill_item_id": "str",
        "project_id": "str",
        "time_entry_ids": [
          "(empty)"
        ],
        "expense_id": "str",
        "item_type": "str",
        "expense_receipt_name": "str",
        "sales_rate": "str",
        "purchase_rate": "str",
        "salesorder_item_id": "str",
        "cost_amount": "int",
        "markup_percent": "int",
        "item_code": {},
        "mapped_items": [
          "(empty)"
        ],
        "is_modifier_item": "bool",
        "line_item_category": "str"
      },
      "(1 items)"
    ],
    "total_retention_amount": "float",
    "retention_items": [
      "(empty)"
    ],
    "retention_override_preference": "str",
    "credits_associated": [
      "(empty)"
    ],
    "exchange_rate": "float",
    "is_autobill_enabled": "bool",
    "inprocess_transaction_present": "bool",
    "allow_partial_payments": "bool",
    "price_precision": "int",
    "sub_total": "float",
    "tax_total": "float",
    "total_taxable_amount": "float",
    "discount_total": "float",
    "discount_percent": "float",
    "discount": "float",
    "discount_applied_on_amount": "float",
    "discount_type": "str",
    "discount_account_id": "str",
    "discount_account_name": "str",
    "account_id": "str",
    "account_name": "str",
    "adjustment_account_id": "str",
    "adjustment_account_name": "str",
    "tds_override_preference": "str",
    "is_discount_before_tax": "bool",
    "adjustment": "float",
    "adjustment_description": "str",
    "shipping_charge_tax_id": "str",
    "shipping_charge_tax_name": "str",
    "shipping_charge_tax_type": "str",
    "shipping_charge_tax_percentage": "str",
    "shipping_charge_tax_exemption_id": "str",
    "shipping_charge_tax_exemption_code": "str",
    "shipping_charge_tax": "str",
    "bcy_shipping_charge_tax": "str",
    "shipping_charge_exclusive_of_tax": "float",
    "shipping_charge_inclusive_of_tax": "float",
    "shipping_charge_tax_formatted": "str",
    "shipping_charge_exclusive_of_tax_formatted": "str",
    "shipping_charge_inclusive_of_tax_formatted": "str",
    "shipping_charge_account_id": "str",
    "shipping_charge_account_name": "str",
    "shipping_charge": "float",
    "bcy_shipping_charge": "float",
    "bcy_adjustment": "float",
    "bcy_sub_total": "float",
    "bcy_discount_total": "float",
    "bcy_tax_total": "float",
    "bcy_total": "float",
    "total": "float",
    "balance": "float",
    "write_off_amount": "float",
    "roundoff_value": "float",
    "transaction_rounding_type": "str",
    "rounding_mode": "str",
    "bcy_rounding_mode": "str",
    "is_inclusive_tax": "bool",
    "sub_total_inclusive_of_tax": "float",
    "contact_category": "str",
    "tax_rounding": "str",
    "taxes": [
      "(empty)"
    ],
    "shipping_charge_taxes": [
      "(empty)"
    ],
    "exceptions": [
      "(empty)"
    ],
    "tds_calculation_type": "str",
    "can_send_invoice_sms": "bool",
   
```

### customerpayments

```json
{
  "payment_id": "str",
  "payment_number": "str",
  "invoice_numbers": "str",
  "date": "str",
  "payment_mode": "str:'banktransfer'",
  "payment_mode_formatted": "str",
  "amount": "float",
  "bcy_amount": "float",
  "unused_amount": "float",
  "bcy_unused_amount": "float",
  "account_id": "str",
  "account_name": "str",
  "description": "str",
  "product_description": "str",
  "reference_number": "str",
  "is_paid_via_check": "bool",
  "check_details": {
    "check_id": "str",
    "check_status": "str",
    "check_number": "str",
    "memo": "str",
    "expiry_date": "str",
    "clearance_account_id": "str"
  },
  "customer_id": "str",
  "customer_name": "str",
  "created_time": "str",
  "last_modified_time": "str",
  "last_four_digits": "str",
  "gateway_transaction_id": "str",
  "payment_gateway": "str",
  "bcy_refunded_amount": "float",
  "applied_invoices": [
    "(empty)"
  ],
  "has_attachment": "bool",
  "tags": [
    "(empty)"
  ],
  "documents": "str",
  "custom_fields_list": "str",
  "tax_account_id": "str",
  "tax_account_name": "str",
  "tax_amount_withheld": "float",
  "payment_type": "str",
  "payment_status": "str",
  "settlement_status": "str",
  "registration_details": {},
  "sales_channel": "str"
}
```

### expenses

```json
{
  "expense_id": "str",
  "date": "str",
  "user_name": "str",
  "paid_through_account_name": "str",
  "account_name": "str",
  "description": "str",
  "currency_id": "str",
  "currency_code": "str",
  "bcy_total": "float",
  "bcy_total_without_tax": "float",
  "total": "float",
  "total_without_tax": "float",
  "is_billable": "bool",
  "reference_number": "str",
  "customer_id": "str",
  "is_personal": "bool",
  "customer_name": "str",
  "vendor_id": "str",
  "vendor_name": "str",
  "status": "str:'nonbillable'",
  "created_time": "str",
  "last_modified_time": "str",
  "expense_receipt_name": "str",
  "exchange_rate": "float",
  "distance": "float",
  "mileage_rate": "float",
  "mileage_unit": "str",
  "mileage_type": "str",
  "expense_type": "str",
  "report_id": "str",
  "start_reading": "str",
  "end_reading": "str",
  "report_name": "str:''",
  "report_number": "str",
  "has_attachment": "bool",
  "custom_fields_list": "str",
  "tags": [
    "(empty)"
  ],
  "registration_details": {}
}
```

### expense_detail

```json
{
  "code": "int",
  "message": "str",
  "expense": {
    "expense_id": "str",
    "transaction_type": "str",
    "transaction_type_formatted": "str",
    "expense_item_id": "str",
    "account_id": "str",
    "account_name": "str",
    "invoice_conversion_type": "str",
    "paid_through_account_id": "str",
    "paid_through_account_name": "str",
    "vendor_id": "str",
    "vendor_name": "str",
    "documents": [
      "(empty)"
    ],
    "date": "str",
    "markup_percent": "float",
    "tax_id": "str",
    "tax_name": "str",
    "tax_percentage": "int",
    "taxes": [
      "(empty)"
    ],
    "tax_override_preference": "str",
    "currency_id": "str",
    "currency_code": "str",
    "exchange_rate": "float",
    "tax_amount": "float",
    "sub_total": "float",
    "total": "float",
    "bcy_total": "float",
    "amount": "float",
    "is_inclusive_tax": "bool",
    "reference_number": "str",
    "description": "str",
    "is_billable": "bool",
    "is_personal": "bool",
    "customer_id": "str",
    "customer_name": "str",
    "expense_receipt_name": "str",
    "expense_receipt_type": "str",
    "created_time": "str",
    "created_by_id": "str",
    "last_modified_by_id": "str",
    "last_modified_time": "str",
    "employee_id": "str",
    "employee_name": "str",
    "employee_email": "str",
    "vehicle_id": "str",
    "vehicle_name": "str",
    "mileage_rate": "float",
    "mileage_unit": "str",
    "mileage_type": "str",
    "expense_type": "str",
    "start_reading": "str",
    "end_reading": "str",
    "is_pre_gst": "bool",
    "status": "str:'nonbillable'",
    "invoice_id": "str",
    "invoice_number": "str",
    "report_id": "str",
    "report_name": "str:''",
    "report_number": "str",
    "user_id": "str",
    "user_name": "str",
    "user_email": "str",
    "approver_id": "str",
    "approver_name": "str",
    "approver_email": "str",
    "report_status": "str",
    "is_reimbursable": "bool",
    "trip_id": "str",
    "trip_number": "str",
    "location": "str",
    "merchant_id": "str",
    "merchant_name": "str",
    "payment_mode": "str:'Cash'",
    "project_id": "str",
    "template_id": "str",
    "template_name": "str",
    "template_type": "str",
    "page_width": "str",
    "page_height": "str",
    "orientation": "str",
    "project_name": "str",
    "tags": [
      "(empty)"
    ],
    "custom_fields": [
      "(empty)"
    ],
    "custom_field_hash": {},
    "is_recurring_applicable": "bool",
    "line_items": [
      {
        "line_item_id": "str",
        "account_id": "str",
        "account_name": "str",
        "description": "str",
        "tax_amount": "float",
        "tax_id": "str",
        "tax_name": "str",
        "tax_type": "str",
        "tax_percentage": "int",
        "item_total": "float",
        "amount": "float",
        "item_order": "int",
        "line_item_taxes": [
          "(empty)"
        ],
        "tags": [
          "(empty)"
        ]
      },
      "(1 items)"
    ],
    "is_surcharge_applicable": "bool",
    "fcy_surcharge_amount": "float",
    "bcy_surcharge_amount": "float",
    "zcrm_potential_id": "str",
    "zcrm_potential_name": "str",
    "registration_details": {},
    "imported_transactions": [
      "(empty)"
    ]
  }
}
```

### chartofaccounts

```json
{
  "account_id": "str",
  "account_name": "str",
  "account_code": "str",
  "account_type": "str:'other_current_asset'",
  "description": "str",
  "currency_id": "str",
  "currency_code": "str",
  "show_on_dashboard": "bool",
  "show_on_dashboard_formatted": "str",
  "placeholder": "str",
  "is_register_supported_account": "bool",
  "is_user_created": "bool",
  "is_system_account": "bool",
  "is_active": "bool",
  "is_active_formatted": "str",
  "can_show_in_ze": "bool",
  "can_show_in_ze_formatted": "str",
  "parent_account_id": "str",
  "parent_account_name": "str",
  "depth": "int",
  "has_attachment": "bool",
  "is_child_present": "bool",
  "child_count": "str",
  "documents": [
    "(empty)"
  ],
  "created_time": "str",
  "is_standalone_account": "bool",
  "last_modified_time": "str"
}
```

### bankaccounts

```json
{
  "account_id": "str",
  "account_name": "str",
  "account_code": "str",
  "currency_id": "str",
  "currency_code": "str",
  "account_type": "str:'cash'",
  "account_sub_type": "str",
  "uncategorized_transactions": "int",
  "total_unprinted_checks": "int",
  "is_active": "bool",
  "balance": "float",
  "current_balance": "float",
  "bank_balance": "float",
  "bcy_balance": "float",
  "bank_name": "str",
  "feeds_last_refresh_date": "str",
  "feeds_last_refresh_time": "str",
  "is_direct_paypal": "bool",
  "mfa_required": "bool"
}
```

### report_pnl_fytd

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total_sub_account": "float",
              "total": "float",
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "account_code": "str",
              "is_collapsed_view": "bool",
              "previous_total": [
                "(empty)"
              ]
            },
            "(1 items)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_last_month

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total_sub_account": "float",
              "total": "float",
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "account_code": "str",
              "is_collapsed_view": "bool",
              "previous_total": [
                "(empty)"
              ]
            },
            "(1 items)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_prev_fy

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total_sub_account": "float",
              "total": "float",
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "account_code": "str",
              "is_collapsed_view": "bool",
              "previous_total": [
                "(empty)"
              ]
            },
            "(1 items)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_balancesheet

```json
{
  "code": "int",
  "message": "str",
  "balance_sheet": [
    {
      "total": "float",
      "total_label": "str",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total": "float",
              "previous_values": [
                "(empty)"
              ],
              "account_transactions": [
                {
                  "total_sub_account": "\u2026",
                  "total": "\u2026",
                  "account_id": "\u2026",
                  "depth": "\u2026",
                  "previous_values": "\u2026",
                  "is_child_present": "\u2026",
                  "name": "\u2026",
                  "previous_total_sub_account": "\u2026",
                  "account_code": "\u2026",
                  "is_collapsed_view": "\u2026",
                  "previous_total": "\u2026"
                },
                "(1 items)"
              ],
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "previous_total": [
                "(empty)"
              ]
            },
            "(5 items)"
          ],
          "name": "str",
          "previous_total_sub_account": [
            "(empty)"
          ],
          "previous_total": [
            "(empty)"
          ]
        },
        "(4 items)"
      ],
      "name": "str",
      "previous_total_sub_account": [
        "(empty)"
      ],
      "previous_total": [
        "(empty)"
      ]
    },
    "(2 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "as_of_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_2026_03

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total_sub_account": "float",
              "total": "float",
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "account_code": "str",
              "is_collapsed_view": "bool",
              "previous_total": [
                "(empty)"
              ]
            },
            "(1 items)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_2026_04

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            "(empty)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_2026_05

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            "(empty)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_2026_06

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            "(empty)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_2026_07

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total_sub_account": "float",
              "total": "float",
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "account_code": "str",
              "is_collapsed_view": "bool",
              "previous_total": [
                "(empty)"
              ]
            },
            "(1 items)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_2026_08

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total_sub_account": "float",
              "total": "float",
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "account_code": "str",
              "is_collapsed_view": "bool",
              "previous_total": [
                "(empty)"
              ]
            },
            "(1 items)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_2026_09

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total_sub_account": "float",
              "total": "float",
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "account_code": "str",
              "is_collapsed_view": "bool",
              "previous_total": [
                "(empty)"
              ]
            },
            "(1 items)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_fytd_cash

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total_sub_account": "float",
              "total": "float",
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "account_code": "str",
              "is_collapsed_view": "bool",
              "previous_total": [
                "(empty)"
              ]
            },
            "(1 items)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "cash_based": "str",
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_pnl_fytd_groupby_month

```json
{
  "code": "int",
  "message": "str",
  "profit_and_loss": [
    {
      "total": "float",
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "total": "float",
          "total_label": "str",
          "previous_values": [
            "(empty)"
          ],
          "account_transactions": [
            {
              "total_sub_account": "float",
              "total": "float",
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "name": "str",
              "previous_total_sub_account": [
                "(empty)"
              ],
              "account_code": "str",
              "is_collapsed_view": "bool",
              "previous_total": [
                "(empty)"
              ]
            },
            "(1 items)"
          ],
          "name": "str",
          "previous_total": [
            "(empty)"
          ]
        },
        "(2 items)"
      ],
      "name": "str",
      "previous_total": [
        "(empty)"
      ]
    },
    "(3 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_trialbalance

```json
{
  "code": "int",
  "message": "str",
  "trialbalance": [
    {
      "previous_values": [
        "(empty)"
      ],
      "account_transactions": [
        {
          "account_type": "str:'asset'",
          "account_transactions": [
            {
              "account_id": "str",
              "depth": "int",
              "previous_values": [
                "(empty)"
              ],
              "is_child_present": "bool",
              "values": [
                {
                  "net_debit_total": "\u2026",
                  "net_debit_total_sub_account": "\u2026",
                  "net_credit_total": "\u2026",
                  "net_credit_total_sub_account": "\u2026"
                },
                "(1 items)"
              ],
              "name": "str",
              "account_code": "str",
              "net_debit_total": "float",
              "is_collapsed_view": "bool",
              "net_debit_total_sub_account": "str",
              "net_credit_total": "str",
              "net_credit_total_sub_account": "float"
            },
            "(3 items)"
          ],
          "name": "str",
          "account_type_col_span": "int"
        },
        "(5 items)"
      ],
      "values": [
        {
          "net_debit_total": "float",
          "net_debit_total_sub_account": "float",
          "net_credit_total": "float",
          "net_credit_total_sub_account": "float"
        },
        "(1 items)"
      ],
      "name": "str",
      "net_debit_total": "float",
      "is_collapsed_view": "bool",
      "net_debit_total_sub_account": "float",
      "account_type_col_span_list": [
        "int",
        "(1 items)"
      ],
      "net_credit_total": "float",
      "net_credit_total_sub_account": "float"
    },
    "(1 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "as_of_date": "str",
    "to_date": "str",
    "is_comparision_report": "bool",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(3 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "date_range_label": "str",
    "date_range_label_col_span": "int",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      "(empty)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_generalledger

```json
{
  "code": "int",
  "message": "str",
  "generalledger": [
    {
      "name": "str",
      "account_id": "str",
      "credit_total": "float",
      "debit_total": "float",
      "balance": "float",
      "is_debit": "bool",
      "previous_values": [
        "(empty)"
      ],
      "values": [
        {
          "debit_total": "float",
          "balance": "float",
          "credit_total": "float"
        },
        "(1 items)"
      ]
    },
    "(67 items)"
  ],
  "page_context": {
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "is_inv_txn_job_in_progress": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "previous_date_range": [
      "(empty)"
    ],
    "is_for_date_range": "str",
    "show_rows": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(4 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(2 items)"
    ],
    "date_range_label": "str",
    "is_period_basis": "str",
    "fifo_scheduler_status": {
      "is_queue_entry_present": "bool",
      "is_job_status_completed": "bool"
    },
    "date_range_list": [
      {
        "date_range_label": "str",
        "from_date": "str",
        "to_date": "str"
      },
      "(1 items)"
    ],
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### report_taxsummary

```json
{
  "code": "int",
  "message": "str",
  "tax": [
    "(empty)"
  ],
  "page_context": {
    "page": "int",
    "per_page": "int",
    "has_more_page": "bool",
    "report_name": "str:'Tax Summary'",
    "can_show_reports_banner": "bool",
    "can_schedule": "bool",
    "cash_based": "bool",
    "report_basis": "str",
    "is_already_scheduled": "bool",
    "entity_list": [
      "str",
      "(23 items)"
    ],
    "report_type": "str",
    "applied_filter": "str",
    "from_date": "str",
    "to_date": "str",
    "is_for_date_range": "str",
    "last_accessed_time_formatted": "str",
    "select_columns": [
      {
        "field": "str",
        "group": "str"
      },
      "(4 items)"
    ],
    "group_by": [
      {
        "field": "str",
        "group": "str"
      },
      "(1 items)"
    ],
    "is_period_basis": "str",
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### account_txn_4235431000000000468

```json
{
  "code": "int",
  "message": "str",
  "transactions": [
    "(empty)"
  ],
  "page_context": {
    "page": "int",
    "per_page": "int",
    "has_more_page": "bool",
    "report_name": "str:'Transactions'",
    "account_name": "str",
    "report_basis": "str",
    "applied_filter": "str",
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### account_txn_4235431000000000474

```json
{
  "code": "int",
  "message": "str",
  "transactions": [
    "(empty)"
  ],
  "page_context": {
    "page": "int",
    "per_page": "int",
    "has_more_page": "bool",
    "report_name": "str:'Transactions'",
    "account_name": "str",
    "report_basis": "str",
    "applied_filter": "str",
    "sort_column": "str",
    "sort_order": "str"
  }
}
```

### vendorpayments

```json
{
  "payment_id": "str",
  "vendor_id": "str",
  "currency_id": "str",
  "status": "str:'paid'",
  "vendor_name": "str",
  "bill_numbers": "str",
  "payment_mode": "str:'banktransfer'",
  "payment_number": "str",
  "description": "str",
  "date": "str",
  "reference_number": "str",
  "exchange_rate": "float",
  "amount": "float",
  "bcy_amount": "float",
  "paid_through_account_id": "str",
  "paid_through_account_name": "str",
  "balance": "float",
  "currency_code": "str",
  "bcy_balance": "float",
  "created_time": "str",
  "last_modified_time": "str",
  "is_paid_via_print_check": "bool",
  "has_attachment": "bool",
  "tags": [
    "(empty)"
  ],
  "is_ach_payment": "bool",
  "ach_payment_status": "str",
  "ach_gw_transaction_id": "str",
  "gw_reference_number": "str",
  "is_advance_payment": "bool",
  "product_description": "str",
  "check_details": {
    "check_id": "str",
    "check_status": "str",
    "check_number": "str",
    "expiry_date": "str",
    "clearance_account_id": "str",
    "clearance_account_name": "str",
    "memo": "str"
  },
  "registration_details": {}
}
```

### bills

```json
{
  "bill_id": "str",
  "vendor_id": "str",
  "vendor_name": "str",
  "status": "str:'paid'",
  "color_code": "str",
  "current_sub_status_id": "str",
  "current_sub_status": "str",
  "bill_number": "str",
  "reference_number": "str",
  "date": "str",
  "due_date": "str",
  "due_days": "str",
  "currency_id": "str",
  "currency_code": "str",
  "price_precision": "int",
  "exchange_rate": "float",
  "total": "float",
  "tds_total": "float",
  "balance": "float",
  "unprocessed_payment_amount": "float",
  "created_time": "str",
  "last_modified_time": "str",
  "created_time_formatted": "str",
  "last_modified_time_formatted": "str",
  "created_by": "str",
  "last_modified_by": "str",
  "is_opening_balance": "str",
  "attachment_name": "str",
  "has_attachment": "bool",
  "tags": [
    "(empty)"
  ],
  "is_uber_bill": "bool",
  "is_tally_bill": "bool",
  "entity_type": "str",
  "client_viewed_time": "str",
  "is_viewed_by_client": "bool",
  "is_bill_reconciliation_violated": "bool",
  "balance_due": "float",
  "registration_details": {}
}
```

### customerpayment_detail

```json
{
  "code": "int",
  "message": "str",
  "payment": {
    "payment_id": "str",
    "payment_number": "str",
    "sales_channel": "str",
    "account_identifier": "str",
    "payment_link_id": "str",
    "created_by": "str",
    "created_time": "str",
    "updated_time": "str",
    "lock_details": {
      "can_lock": "bool"
    },
    "locked_actions": [
      "(empty)"
    ],
    "payment_number_prefix": "str",
    "payment_number_suffix": "str",
    "documents": [
      "(empty)"
    ],
    "beat_id": "str",
    "beat_number": "str",
    "journey_plan_id": "str",
    "sales_person_id": "str",
    "sales_person_name": "str",
    "customer_id": "str",
    "customer_name": "str",
    "payment_mode": "str:'banktransfer'",
    "card_type": "str",
    "date": "str",
    "offline_created_date_with_time": "str",
    "is_pre_gst": "bool",
    "account_id": "str",
    "account_name": "str",
    "account_type": "str:'bank'",
    "customer_advance_account_id": "str",
    "customer_advance_account_name": "str",
    "currency_id": "str",
    "currency_symbol": "str",
    "currency_code": "str",
    "exchange_rate": "float",
    "amount": "float",
    "unused_amount": "float",
    "bank_charges": "float",
    "bank_charges_account_id": "str",
    "bank_charges_account_name": "str",
    "tax_account_id": "str",
    "is_client_review_settings_enabled": "bool",
    "tax_account_name": "str",
    "tax_amount_withheld": "float",
    "description": "str",
    "product_description": "str",
    "reference_number": "str",
    "online_transaction_id": "str",
    "payment_gateway": "str",
    "settlement_status": "str",
    "tds_type": "str",
    "tds_tax_id": "str",
    "is_ondc_channel": "bool",
    "is_paid_via_check": "bool",
    "invoices": [
      {
        "invoice_number": "str",
        "invoice_payment_id": "str",
        "invoice_id": "str",
        "invoice_customer_id": "str",
        "invoice_customer_name": "str",
        "amount_applied": "float",
        "tax_amount_withheld": "float",
        "total": "float",
        "balance": "float",
        "date": "str",
        "due_date": "str",
        "unprocessed_payment_amount": "float",
        "price_precision": "int",
        "apply_date": "str",
        "allow_partial_payments": "str",
        "invoice_installments": [
          "(empty)"
        ],
        "installments": [
          "(empty)"
        ]
      },
      "(1 items)"
    ],
    "check_details": {
      "check_id": "str",
      "check_number": "str",
      "memo": "str",
      "check_status": "str",
      "expiry_date": "str",
      "clearance_account_id": "str"
    },
    "registration_details": {},
    "payment_status": "str",
    "tender_id": "str",
    "payment_refunds": [
      "(empty)"
    ],
    "deposit_details": [
      "(empty)"
    ],
    "last_four_digits": "str",
    "template_id": "str",
    "template_name": "str",
    "page_width": "str",
    "page_height": "str",
    "orientation": "str",
    "template_type": "str",
    "attachment_name": "str",
    "can_send_in_mail": "bool",
    "can_send_payment_sms": "bool",
    "is_payment_details_required": "bool",
    "custom_fields": [
      "(empty)"
    ],
    "custom_field_hash": {},
    "imported_transactions": [
      "(empty)"
    ],
    "price_precision": "int",
    "rounding_mode": "str",
    "tags": [
      "(empty)"
    ]
  }
}
```

### bill_detail

```json
{
  "code": "int",
  "message": "str",
  "bill": {
    "bill_id": "str",
    "purchaseorder_ids": [
      "(empty)"
    ],
    "non_catalog_items_count": "int",
    "vendor_id": "str",
    "vendor_name": "str",
    "source": "str",
    "can_amend_transaction": "bool",
    "contact_category": "str",
    "invoice_conversion_type": "str",
    "unused_credits_payable_amount": "float",
    "status": "str:'paid'",
    "color_code": "str",
    "current_sub_status_id": "str",
    "current_sub_status": "str",
    "sub_statuses": [
      "(empty)"
    ],
    "bill_number": "str",
    "date": "str",
    "is_pre_gst": "bool",
    "due_date": "str",
    "discount_setting": "str",
    "tds_calculation_type": "str",
    "is_tds_amount_in_percent": "bool",
    "tds_percent": "str",
    "tds_amount": "float",
    "tax_account_id": "str",
    "payment_terms": "int",
    "payment_terms_label": "str",
    "payment_expected_date": "str",
    "reference_number": "str",
    "scanned_po_number": "str",
    "scanned_po_id": "str",
    "recurring_bill_id": "str",
    "due_by_days": "int",
    "due_in_days": "str",
    "currency_id": "str",
    "currency_code": "str",
    "currency_symbol": "str",
    "currency_name_formatted": "str",
    "documents": [
      "(empty)"
    ],
    "subject_content": "str",
    "price_precision": "int",
    "exchange_rate": "float",
    "custom_fields": [
      "(empty)"
    ],
    "custom_field_hash": {},
    "is_viewed_by_client": "bool",
    "client_viewed_time": "str",
    "is_item_level_tax_calc": "bool",
    "is_inclusive_tax": "bool",
    "tax_rounding": "str",
    "is_uber_bill": "bool",
    "is_tally_bill": "bool",
    "track_discount_in_account": "bool",
    "is_bill_reconciliation_violated": "bool",
    "bill_order_type": "str",
    "lock_details": {
      "can_lock": "bool"
    },
    "locked_actions": [
      "(empty)"
    ],
    "lock_detail": {
      "can_lock": "bool",
      "custom_locks": [
        "(empty)"
      ],
      "system_locks": [
        "(empty)"
      ]
    },
    "line_items": [
      {
        "purchaseorder_id": "str",
        "purchaseorder_item_id": "str",
        "line_item_id": "str",
        "item_id": "str",
        "line_item_category": "str",
        "image_document_id": "str",
        "name": "str",
        "account_id": "str",
        "account_name": "str",
        "account_code": "str",
        "description": "str",
        "bcy_rate": "float",
        "rate": "float",
        "sales_rate": "str",
        "pricebook_id": "str",
        "header_id": "str",
        "header_name": "str",
        "tags": [
          "(empty)"
        ],
        "quantity": "float",
        "quantity_received": "float",
        "discount": "float",
        "discounts": [
          "(empty)"
        ],
        "discount_account_id": "str",
        "discount_account_name": "str",
        "markup_percent": "float",
        "tax_id": "str",
        "tax_name": "str",
        "tax_type": "str",
        "tax_percentage": "int",
        "tds_tax_id": "str",
        "tds_tax_name": "str",
        "tds_tax_percentage": "str",
        "tds_tax_amount": "float",
        "line_item_taxes": [
          "(empty)"
        ],
        "line_item_tds": [
          "(empty)"
        ],
        "item_total": "float",
        "item_order": "int",
        "unit": "str",
        "item_type": "str",
        "item_code": {},
        "image_name": "str",
        "image_type": "str",
        "is_billable": "bool",
        "customer_id": "str",
        "receipt_line_item_id": "str",
        "customer_name": "str",
        "project_id": "str",
        "project_name": "str",
        "invoice_id": "str",
        "invoice_number": "str",
        "item_custom_fields": [
          "(empty)"
        ],
        "purchase_request_items": [
          "(empty)"
        ],
        "item_matching_type": "str",
        "receive_line_items": [
          "(empty)"
        ]
      },
      "(1 items)"
    ],
    "submitted_date": "str",
    "submitted_by": "str",
    "submitted_by_name": "str",
    "submitted_by_email": "str",
    "submitted_by_photo_url": "str",
    "submitter_id": "str",
    "approver_id": "str",
    "adjustment": "float",
    "adjustment_description": "str",
    "discount_amount": "float",
    "discount": "float",
    "discount_applied_on_amount": "float",
    "is_discount_before_tax": "bool",
    "discount_account_id": "str",
    "discount_account_name": "str",
    "discount_type": "str",
    "sub_total": "float",
    "sub_total_inclusive_of_tax": "float",
    "tax_total": "float",
    "discount_total": "float",
    "discount_percent": "float",
    "total": "float",
    "payment_made": "float",
    "vendor_credits_applied": "float",
    "is_line_item_invoiced": "bool",
    "purchaseorders": [
      "(empty)"
    ],
    "taxes": [
      "(empty)"
    ],
    "computation_type": "str",
    "tax_override_preference": "str",
    "tds_override_preference": "str",
    "tds_summary": [
      "(empty)"
    ],
    "balance": "float",
    "unprocessed_payment_amount": "float",
    "billing_address_id": "str",
    "billing_address": {
      "address": "str",
      "street2": "str",
      "city": "str",
      "state": "str",
      "zip": "str",
      "country": "str",
      "fax": "str",
      "phone": "str",
      "attention": "str"
    },
    "payments": [
      {
        "payment_id": "str",
        "bill_id": "str",
        "bill_payment_id": "str",
        "payment_mode": "str:'banktransfer'",
        "payment_number": "str",
        "description": "str",
        "date": "str",
        "reference_number": "str",
        "exchange_rate": "float",
        "amount": "float",
        "apply_date": "str",
        "credit_account_id": "str",
        "paid_through_account_id": "str",
        "paid_through_account_name": "str",
        "paid_through_account_type": "str",
        "is_single_bill_payment": "bool",
        "is_paid_via_print_check": "bool",
        "check_details": {
          "check_n
```

### vendorpayment_detail

```json
{
  "code": "int",
  "message": "str",
  "vendorpayment": {
    "payment_id": "str",
    "vendor_id": "str",
    "vendor_name": "str",
    "status": "str:'paid'",
    "is_online_payment": "bool",
    "is_flagged_for_risk": "str",
    "transfer_type": "str",
    "payment_mode": "str:'banktransfer'",
    "payment_number": "str",
    "payment_number_prefix": "str",
    "payment_number_suffix": "str",
    "purpose_code": "str",
    "custom_fields": [
      "(empty)"
    ],
    "custom_field_hash": {},
    "description": "str",
    "documents": [
      "(empty)"
    ],
    "date": "str",
    "reference_number": "str",
    "exchange_rate": "float",
    "tds_tax_id": "str",
    "indirect_tds_tax_id": "str",
    "indirect_tds_tax_amount": "float",
    "indirect_tcs_tax_id": "str",
    "indirect_tcs_tax_amount": "float",
    "indirect_tds_tax_details": [
      "(empty)"
    ],
    "indirect_tcs_tax_details": [
      "(empty)"
    ],
    "tds_calculation_type": "str",
    "is_tds_amount_in_percent": "bool",
    "tds_override_preference": "str",
    "tds_summary": [
      "(empty)"
    ],
    "tax_account_id": "str",
    "tax_account_name": "str",
    "tax_amount_withheld": "float",
    "amount": "float",
    "total_payment_amount": "float",
    "balance": "float",
    "currency_id": "str",
    "currency_code": "str",
    "currency_symbol": "str",
    "created_time": "str",
    "last_modified_time": "str",
    "created_by_id": "str",
    "created_by_name": "str",
    "credit_account_id": "str",
    "paid_through_account_id": "str",
    "paid_through_account_name": "str",
    "paid_through_account_type": "str",
    "is_paid_via_print_check": "bool",
    "offset_account_id": "str",
    "offset_account_name": "str",
    "is_pre_gst": "bool",
    "is_advance_payment": "bool",
    "product_description": "str",
    "is_ach_payment": "bool",
    "ach_payment_status": "str",
    "gw_reference_number": "str",
    "check_details": {
      "check_id": "str",
      "check_number": "str",
      "expiry_date": "str",
      "memo": "str",
      "clearance_account_id": "str",
      "clearance_account_name": "str",
      "amount_in_words": "str",
      "check_status": "str",
      "template_id": "str",
      "retain_txn_in_void_check": "bool"
    },
    "billing_address": {
      "address": "str",
      "street2": "str",
      "city": "str",
      "state": "str",
      "zip": "str",
      "country": "str",
      "fax": "str",
      "phone": "str",
      "attention": "str"
    },
    "bills": [
      {
        "bill_number": "str",
        "price_precision": "int",
        "bill_payment_id": "str",
        "bill_id": "str",
        "is_opening_balance": "bool",
        "total": "float",
        "balance": "float",
        "unprocessed_payment_amount": "float",
        "amount_applied": "float",
        "apply_date": "str",
        "tax_amount_withheld": "float",
        "total_payment_amount": "float",
        "date": "str",
        "due_date": "str",
        "indirect_tds_tax_id": "str",
        "indirect_tds_tax_amount": "float",
        "indirect_tcs_tax_id": "str",
        "indirect_tcs_tax_amount": "float",
        "indirect_tds_tax_details": [
          "(empty)"
        ],
        "indirect_tcs_tax_details": [
          "(empty)"
        ]
      },
      "(1 items)"
    ],
    "vendorpayment_refunds": [
      "(empty)"
    ],
    "comments": [
      {
        "comment_id": "str",
        "description": "str",
        "commented_by_id": "str",
        "commented_by": "str",
        "date": "str",
        "date_description": "str",
        "time": "str",
        "operation_type": "str"
      },
      "(1 items)"
    ],
    "imported_transactions": [
      "(empty)"
    ],
    "approvers_list": [
      "(empty)"
    ],
    "submitted_date": "str",
    "submitted_by": "str",
    "submitted_by_name": "str",
    "submitted_by_email": "str",
    "submitted_by_photo_url": "str",
    "submitter_id": "str",
    "approver_id": "str",
    "tags": [
      "(empty)"
    ],
    "is_multi_match_approval": "bool",
    "approval_name": "str",
    "approval_path": [
      "(empty)"
    ],
    "approvers": [
      "(empty)"
    ],
    "note_to_approver": "str",
    "registration_details": {}
  }
}
```


---

## Interpretation (hand-written, 2026-09-26)

> The sections above are generated by `scripts/phase0/zoho_spike.py` and are overwritten if the script is re-run. This section is not.

**Run context:**
- Trial organisation `60089553909` ("Crita Creative LLP", created 2026-09-26, Premium trial, **GST disabled**).
- It holds a 21-record **TEST** dataset created by `scripts/phase0/seed_test_data.py`: 1 bank account, 3 customers, 1 vendor, 7 invoices (1 draft, 1 void), 3 customer payments, 4 expenses, 1 bill and 1 vendor payment. The manifest is in `.spike/seed-manifest.json`, which is local.
- The director's live organisation `60069959305` was **not** accessed.

**Run history:**
1. The consenting account had no organisation. That was the wrong login.
2. Only `accountants.READ` was granted, and every report returned 401, code 57.
3. A transient "server disconnected" error occurred; retries were then added.
4. Empty organisation, with `reports.READ` granted: every report worked.
5. **This run:** read-only, 34 calls, against the populated TEST organisation.

**Verified:**
- **OAuth:** the server-based flow works with one Crita app. The callback carries `location` and `accounts-server`. The token response includes `api_domain` and the granted `scope`. Revoke returns HTTP 200.
- **Scopes:** `ZohoBooks.reports.READ` is **required** for every `reports/*` endpoint; `accountants.READ` does not cover them.
- **Endpoints:** every planned endpoint works, including monthly P&L (one call per month) and `cash_based=true`. `group_by=month` is silently ignored. `reports/accounttransactions` does not exist (404).
- **Data rules:**
  - Amounts arrive as JSON floats, so the connector must parse them as `Decimal`.
  - The invoice list has no base-currency total.
  - The expense list has no account IDs.
  - A partly-paid overdue invoice has `status: overdue`.
  - Draft and void invoices keep a balance.
  - `fiscal_year_start_month` is `"april"` in the detail call and `3` (0-based) in the list call.
- **Rate limit:** 1,000 calls a day on this trial, exposed in `x-rate-limit-*` headers.
- **Figures:** 53 of 53 hand-calculated checks pass. See [`test-data-verification.md`](test-data-verification.md).

**Not verified:**
- The GST / tax-summary source, because GST is disabled here.
- Live-organisation data variety: multi-currency, GST fields, large volumes, other statuses.
- The paid plan's API limits.
- Non-India data centers.

These are carried forward in `FINAL_ARCHITECTURE_PLAN.md` as risks R2, R3 and R11.
