# Stage 01 — Exports from MYOB (raw)

This folder receives **every download/export pulled out of MYOB Online**,
kept in its original, detailed format. Files in this stage are
**immutable** — never edit them in place. Transformations happen in
`../02_cleansed_for_xero/`.

> ⚠️ **Payroll subfolders (`04_employees/`, `12_payroll_history/`) are
> high-sensitivity.** They carry TFNs, DOBs, bank details, and
> identified earnings, governed by the Privacy Act 1988 and the TFN
> Rule. Read `../PRIVACY.md` and complete its §8 pre-pull sign-off
> before exporting either.

## Subfolders

| Folder | What goes in here | Suggested file |
| ------ | ----------------- | -------------- |
| `00_company_file_info/` | Company info screen, users, lock dates, fiscal year settings | `company_info_<date>.pdf` |
| `01_chart_of_accounts/` | Accounts list export (with account numbers, types, tax codes) | `chart_of_accounts_<date>.csv` |
| `02_contacts_customers/` | Customer cards: Card ID, Name, ABN, billing/shipping, terms | `customers_<date>.csv` |
| `03_contacts_suppliers/` | Supplier cards: Card ID, Name, ABN, terms, bank details | `suppliers_<date>.csv` |
| `04_employees/` | Employee cards, standard pay, super fund, TFN, leave accruals | `employees_<date>.csv` |
| `05_inventory_items/` | Item list with on-hand quantity, avg cost, sell price, tax codes | `items_<date>.csv` |
| `06_open_invoices_AR/` | Open sales invoices with line-level detail and ageing | `open_invoices_<date>.csv` |
| `07_open_bills_AP/` | Open purchase bills with line-level detail and ageing | `open_bills_<date>.csv` |
| `08_bank_accounts_statements/` | One CSV/OFX per bank/credit-card account for the reconciliation window | `bank_<acct>_<from>_<to>.csv` |
| `09_general_ledger/` | Full GL detail covering the conversion FY (used for sanity checks) | `gl_detail_<from>_<to>.csv` |
| `10_trial_balance/` | Trial Balance at exactly the conversion date | `trial_balance_<date>.csv` |
| `11_tax_GST_BAS/` | Tax code list + last lodged BAS / GST detail | `gst_<period>.pdf` |
| `12_payroll_history/` | Payroll Activity, Entitlement Balances, Super accrual reports | `payroll_<from>_<to>.csv` |
| `13_fixed_assets/` | Fixed asset register + depreciation schedule | `fixed_assets_<date>.xlsx` |
| `14_jobs_tracking/` | Jobs list / categories used for analysis | `jobs_<date>.csv` |
| `15_recurring_transactions/` | Recurring sales, purchases, payments | `recurring_txns_<date>.csv` |
| `16_attachments_documents/` | Bulk export of attached source documents (PDF, receipts) | `<docs>/` |

## Rules for this stage

1. **Never edit a file here** after it lands. If the export was wrong,
   re-export with a new date suffix and supersede in `INDEX.md`.
2. Always export to CSV where MYOB offers it (not PDF), so the next
   stage can transform it.
3. File names must follow `<entity>_<scope>_<YYYYMMDD>.<ext>`.
4. Bulk attachments: keep MYOB's folder structure, do not flatten.
5. Tick the corresponding row in `../INDEX.md` once each export lands.
