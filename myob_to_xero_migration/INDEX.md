# Master Index — MYOB → Xero Migration

Single source of truth for "where is every artefact and what state is it in".
Update the **Status** column every time a file moves between stages.

Status legend: `⬜ todo` · `🟡 in progress` · `🟢 done` · `⚠ exception`

## Client header

| Field | Value |
| ----- | ----- |
| Client / entity | _TBD_ |
| Conversion date | _TBD_ |
| MYOB file ID | _TBD_ |
| Xero organisation | _TBD_ |
| Lead accountant | _TBD_ |
| Migration started | _TBD_ |
| Migration completed | _TBD_ |

## 01 — Exports from MYOB

| # | Artefact | File pattern | Stage-01 status | Notes |
| - | -------- | ------------ | --------------- | ----- |
| 00 | Company file metadata | `company_info_<date>.pdf` | ⬜ | |
| 01 | Chart of accounts (full) | `chart_of_accounts_<date>.csv` | ⬜ | |
| 02 | Customers list | `customers_<date>.csv` | ⬜ | |
| 03 | Suppliers list | `suppliers_<date>.csv` | ⬜ | |
| 04 | Employees + standard pay | `employees_<date>.csv` | ⬜ | |
| 05 | Inventory items + on-hand | `items_<date>.csv` | ⬜ | |
| 06 | Open invoices (AR detail) | `open_invoices_<date>.csv` | ⬜ | |
| 07 | Open bills (AP detail) | `open_bills_<date>.csv` | ⬜ | |
| 08 | Bank statements (per acct) | `bank_<acct>_<from>_<to>.csv` | ⬜ | one row per account |
| 09 | General ledger (conversion FY) | `gl_detail_<from>_<to>.csv` | ⬜ | |
| 10 | Trial balance @ conv. date | `trial_balance_<date>.csv` | ⬜ | |
| 11 | GST / BAS report + tax codes | `gst_report_<period>.pdf` | ⬜ | |
| 12 | Payroll activity + leave | `payroll_activity_<period>.csv` | ⬜ | |
| 13 | Fixed asset register | `fixed_assets_<date>.xlsx` | ⬜ | |
| 14 | Jobs / categories | `jobs_<date>.csv` | ⬜ | |
| 15 | Recurring transactions | `recurring_txns_<date>.csv` | ⬜ | |
| 16 | Attachments / source docs | `<docs>/` | ⬜ | bulk export |

## 02 — Cleansed for Xero

| # | Xero template | File | Stage-02 status | Validated against template |
| - | ------------- | ---- | --------------- | -------------------------- |
| 01 | Chart of accounts CSV | `xero_chart_of_accounts.csv` | ⬜ | ⬜ |
| 02 | Contacts CSV | `xero_contacts.csv` | ⬜ | ⬜ |
| 03 | Employees | `xero_employees.csv` | ⬜ | ⬜ |
| 04 | Inventory items | `xero_items.csv` | ⬜ | ⬜ |
| 05 | Conversion balances | `xero_conversion_balances.csv` | ⬜ | ⬜ |
| 06 | Open invoices (sales) | `xero_invoices.csv` | ⬜ | ⬜ |
| 07 | Open bills (purchases) | `xero_bills.csv` | ⬜ | ⬜ |
| 08 | Bank statements | `xero_bank_<acct>.csv` | ⬜ | ⬜ |
| 09 | Manual journals | `xero_manual_journals.csv` | ⬜ | ⬜ |
| 10 | Tracking categories | `xero_tracking.csv` | ⬜ | ⬜ |
| 11 | Fixed asset register | `xero_fixed_assets.csv` | ⬜ | ⬜ |
| 12 | Payroll opening balances | `xero_payroll_opening.csv` | ⬜ | ⬜ |

## 03 — Finalized reports (locked source of truth)

| Report | Period | File | Status |
| ------ | ------ | ---- | ------ |
| Balance Sheet @ conversion date | _date_ | `bs_<date>.pdf` | ⬜ |
| Profit & Loss (YTD) | _from–to_ | `pl_<from>_<to>.pdf` | ⬜ |
| Trial Balance @ conversion date | _date_ | `tb_<date>.pdf` | ⬜ |
| Aged Receivables detail | _date_ | `ar_<date>.pdf` | ⬜ |
| Aged Payables detail | _date_ | `ap_<date>.pdf` | ⬜ |
| Last lodged BAS / GST report | _period_ | `bas_<period>.pdf` | ⬜ |
| Payroll Activity (YTD) | _from–to_ | `payroll_<from>_<to>.pdf` | ⬜ |
| Bank reconciliation summaries | _date_ | `bank_recs_<date>.pdf` | ⬜ |
| Client sign-off form | _date_ | `signoff_pre_upload.pdf` | ⬜ |

## 04 — Xero post-upload checks

| Check | Account / contact group | Status | Variance ($) | Resolution |
| ----- | ----------------------- | ------ | ------------ | ---------- |
| Chart of accounts loaded | — | ⬜ | — | — |
| Contacts loaded | Customers | ⬜ | — | — |
| Contacts loaded | Suppliers | ⬜ | — | — |
| Conversion balances posted | All BS accounts | ⬜ | — | — |
| Open AR matches MYOB | Per customer | ⬜ | — | — |
| Open AP matches MYOB | Per supplier | ⬜ | — | — |
| Bank accounts opening match | Per account | ⬜ | — | — |
| GST control accounts match | BAS period | ⬜ | — | — |
| Payroll opening balances match | Per employee | ⬜ | — | — |
| Fixed assets register loaded | All assets | ⬜ | — | — |
| Tracking categories active | All categories | ⬜ | — | — |
| Final Trial Balance match | All accounts | ⬜ | — | — |
| Client final sign-off | — | ⬜ | — | — |

## Change log

| Date | Author | Change |
| ---- | ------ | ------ |
| _yyyy-mm-dd_ | _name_ | Migration kicked off |
