# Stage 03 — Finalized reports (locked source of truth)

The reports in this folder are the **frozen "before" picture** of the
client's books. Nothing here gets edited after sign-off; everything in
Xero (Stage 04) must reconcile back to it.

## Subfolders

| Folder | What goes in here |
| ------ | ----------------- |
| `01_pre_conversion_snapshots/` | PDF copies of MYOB BS, P&L, TB at conversion date |
| `02_reconciliation_reports/` | Bank reconciliation summaries, AR/AP ageing reconciliations |
| `03_trial_balance_comparisons/` | Side-by-side MYOB vs Stage-02 cleansed totals |
| `04_conversion_date_balance_sheet/` | The single locked BS used as the conversion-balances input |
| `05_sign_off_documents/` | Client-signed approval to proceed with upload |

## Required reports (all from MYOB, all PDF + CSV)

| # | Report | Period | Why it's needed |
| - | ------ | ------ | --------------- |
| 1 | Balance Sheet | As at conversion date | Drives conversion balances in Xero |
| 2 | Profit & Loss | Conversion FY YTD | YTD comparatives in Xero |
| 3 | Trial Balance | As at conversion date | Master reconciliation target |
| 4 | Aged Receivables (detail) | As at conversion date | Per-contact AR reconciliation |
| 5 | Aged Payables (detail) | As at conversion date | Per-contact AP reconciliation |
| 6 | Last lodged BAS / GST report | Last quarter | GST control account reconciliation |
| 7 | Payroll Activity (YTD) | Conversion FY YTD | Payroll opening balances |
| 8 | Bank reconciliation summary per account | As at conversion date | Bank opening reconciliation |
| 9 | Inventory valuation | As at conversion date | Inventory control account check |
| 10 | Fixed asset register | As at conversion date | Asset / accumulated depreciation check |

## Sign-off

`05_sign_off_documents/` holds the client's written approval that the
Stage 03 reports represent the correct closing position of MYOB.
**Do not start Stage 04 (upload to Xero) without this sign-off.**
