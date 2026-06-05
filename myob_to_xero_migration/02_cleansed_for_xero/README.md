# Stage 02 — Cleansed for Xero (upload-ready)

Working folder where the raw exports from `01_exports_from_myob/` are
transformed into **Xero-approved CSV templates** ready to upload.

## Subfolders

Each folder mirrors a Xero import endpoint and **must use Xero's column
order exactly** — see `../templates/xero_csv_templates/`. Xero rejects
files where headers don't match.

| Folder | Xero target | Template |
| ------ | ----------- | -------- |
| `01_chart_of_accounts/` | Accounting ▸ Chart of accounts ▸ Import | `xero_chart_of_accounts_template.csv` |
| `02_contacts/` | Contacts ▸ Import | `xero_contacts_template.csv` |
| `03_employees/` | Payroll ▸ Employees ▸ Import | `xero_employees_template.csv` |
| `04_inventory_items/` | Products & services ▸ Import | `xero_items_template.csv` |
| `05_conversion_balances/` | Accounting ▸ Advanced ▸ Conversion balances | `xero_conversion_balances_template.csv` |
| `06_open_invoices_AR/` | Sales ▸ Invoices ▸ Import | `xero_invoices_template.csv` |
| `07_open_bills_AP/` | Purchases ▸ Bills ▸ Import | `xero_bills_template.csv` |
| `08_bank_statements/` | Bank account ▸ Import statement | `xero_bank_statement_template.csv` |
| `09_manual_journals/` | Accounting ▸ Manual journals ▸ Import | `xero_manual_journals_template.csv` |
| `10_tracking_categories/` | Accounting ▸ Advanced ▸ Tracking | `xero_tracking_template.csv` |
| `11_fixed_assets_register/` | Fixed assets ▸ Import | `xero_fixed_assets_template.csv` |
| `12_payroll_opening_balances/` | Payroll ▸ Opening balances | `xero_payroll_opening_template.csv` |
| `_validation_logs/` | Outputs of pre-flight validation runs | — |

## Cleansing rules (apply to every dataset)

1. **Account codes**: re-map MYOB ranges (1-xxxx assets, 2-xxxx
   liabilities …) to Xero account codes; ensure each code is unique
   and 3-10 characters.
2. **Tax codes**: MYOB → Xero mapping table lives in
   `../templates/checklists/tax_code_mapping.md`. Do not invent new
   Xero rates — use the standard set unless the client truly has a
   custom rate registered.
3. **Contacts**: deduplicate by ABN where possible; merge duplicate
   customer/supplier cards into a single Xero contact.
4. **Dates**: convert to `DD/MM/YYYY` (Xero AU default).
5. **Amounts**: tax-inclusive vs tax-exclusive — match the Xero
   template's expectation per column, never mix within a file.
6. **Encoding**: save as UTF-8 with BOM, comma-delimited, LF line
   endings.
7. **Pre-flight validation**: run every file through the validator
   (`../templates/scripts/validate_xero_csv.py`) before promoting to
   Stage 03. Logs land in `_validation_logs/`.

## Promotion rule

A file only leaves Stage 02 when:

- It passes the Xero template validator with zero errors.
- Its row count and control totals match the source export in Stage 01
  (record the reconciliation in `_validation_logs/`).
- The row in `../INDEX.md` (Stage-02 column) is ticked.
