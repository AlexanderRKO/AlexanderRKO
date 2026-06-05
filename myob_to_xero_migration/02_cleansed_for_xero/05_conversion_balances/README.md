# 05 — Conversion balances (CLEANSED for Xero upload)

Two related artefacts:

1. **`xero_conversion_balances.csv`** — the single Trial Balance at
   the conversion date that Xero loads into
   *Accounting ▸ Advanced ▸ Conversion balances*. This is the
   minimum that must be uploaded.

2. **`monthly_comparatives/`** — optional. Per-month opening
   balances for Balance Sheet and Profit & Loss accounts going as
   far back as MYOB will give them, so Xero can render historic
   comparative reports. Only useful when the client wants
   month-by-month historic reporting from Xero rather than
   referring back to the locked Stage-03 PDFs.

## When to do monthly comparatives

| Situation | Decision |
| --------- | -------- |
| Client only needs forward reporting from Xero | Skip — single TB only |
| Client wants prior-year monthly comparatives in Xero | Include for the comparison window |
| Bank or client requested historic Xero reporting | Include as far back as data allows |
| Source file has been rolled and historic detail is gone | Capture whatever monthly TB MYOB still produces |

## File layout for `monthly_comparatives/`

One CSV per month, named `comparatives_<YYYYMM>.csv`, columns
matching the Xero conversion-balances template
(`*AccountCode, *AccountName, *Debit, *Credit`). Xero ingests these
via the same conversion-balances screen using the "Add comparative
balances" option.

## Validation

- Sum of debits = sum of credits per file (trial balance must
  balance).
- Account codes already exist in the uploaded Chart of Accounts.
- Per-account monthly movement reconciles to the locked General
  Ledger detail in `../../01_exports_from_myob/09_general_ledger/`.
- File names in date order — no gaps in the month sequence.
