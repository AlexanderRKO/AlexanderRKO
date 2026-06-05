# MYOB → Xero account type mapping

Xero requires a specific `Type` value per account in the chart-of-accounts
import. Use this table to convert MYOB account categories.

| MYOB classification | MYOB header prefix | Xero `Type` value |
| -------------------- | ------------------ | ----------------- |
| Asset – Bank | 1-1xxx | BANK |
| Asset – Current | 1-2xxx | CURRENT |
| Asset – Fixed | 1-3xxx | FIXED |
| Asset – Inventory | 1-4xxx | INVENTORY |
| Asset – Non-current | 1-5xxx | NONCURRENT |
| Asset – Prepayment | 1-6xxx | PREPAYMENT |
| Liability – Current | 2-1xxx | CURRLIAB |
| Liability – GST/PAYG | 2-2xxx | CURRLIAB |
| Liability – Non-current | 2-3xxx | TERMLIAB |
| Equity | 3-xxxx | EQUITY |
| Income – Sales | 4-xxxx | SALES / REVENUE |
| Income – Other | 4-9xxx | OTHERINCOME |
| COGS | 5-xxxx | DIRECTCOSTS |
| Expense – Operating | 6-xxxx | EXPENSE |
| Expense – Overhead | 7-xxxx | OVERHEADS |
| Expense – Depreciation | 6-9xxx | DEPRECIATN |
| Other expense | 8-xxxx | OTHEREXPENSE |
