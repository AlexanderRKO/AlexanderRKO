# 06 — Open invoices (Accounts Receivable, RAW)

The unpaid **sales invoices** owed to the business as at the conversion
date. In Xero these become open Sales Invoices (Business ▸ Invoices ▸
Import), carried across so the customer ledger and AR ageing continue
seamlessly.

## MYOB AccountRight — which report to run

> **Reports ▸ Index to Reports ▸ Sales tab ▸ Receivables ▸
> Receivables Reconciliation [Detail]**
>
> 1. Set the **"as at" date to the conversion date**.
> 2. **Send to ▸ Excel** (or Export).
> 3. Save here as `open_invoices_<YYYYMMDD>.csv` (or `.xlsx`).

### Why this report and not the others

- **It is "as at" a date you choose.** It recalculates what was
  actually outstanding on the conversion date, backing out any payments
  entered *after* that date. This is the single most important property
  for a migration — a live screen cannot do it.
- **It reports the balance still owing per invoice**, not the original
  invoice amount — exactly what Xero loads as the open item.
- **It is the reconciliation report by design.** Its grand total *must
  equal* the Accounts Receivable control account on the conversion-date
  Trial Balance (`10_trial_balance/`). That tie-out is your completeness
  proof — it is the check in
  `templates/checklists/myob_file_readiness.md` §2.

**Acceptable alternative:** *Aged Receivables [Detail]* (same Sales tab)
carries the same line-level open-invoice data with ageing buckets. Fine
to use, but Receivables Reconciliation is purpose-built to tie to the
ledger, so prefer it as the source of truth.

### Two traps to avoid

1. **Do NOT use File ▸ Export Data ▸ Sales.** It looks like the obvious
   "export" answer, but it dumps *all* sales transactions in a date
   range with no open/unpaid filter and no remaining-balance column —
   you would have to net off payments yourself.
2. **Do NOT rely on Sales ▸ Sales Register ▸ Open Invoices.** That screen
   shows the position as at *today* with no as-at date control, so if you
   export it even a day after the conversion date it silently drops
   invoices that have since been paid.

## Before you export — reconcile

Confirm all three of these are equal at the conversion date (per
`myob_file_readiness.md` §2):

```
Receivables Reconciliation [Detail] total
    = Aged Receivables ageing total
    = Trial Balance AR control account
```

If they do not agree, fix it in MYOB *before* exporting — a mismatch
here becomes a mismatch in Xero that is far harder to unpick after the
upload. Make sure all customer credit notes / payments have been applied
against the open invoices first.

## Expected columns (after the report is reshaped for Xero)

The MYOB report groups by customer with subtotal rows; reshape it into
Xero's Sales Invoice import template in Stage 02
(`02_cleansed_for_xero/`). Xero needs, per invoice line:

| Xero column | Source in the MYOB report |
| ----------- | ------------------------- |
| `*ContactName` | Customer / Co./Last Name |
| `*InvoiceNumber` | Invoice # |
| `*InvoiceDate` | Date — **keep the original invoice date** |
| `*DueDate` | Due date — **keep the original**, so ageing carries across |
| `Description` | free text (e.g. "Balance brought forward from MYOB") |
| `*Quantity` | `1` |
| `*UnitAmount` | **balance due** (not the original amount) |
| `*AccountCode` | your AR conversion / suspense account per the Xero conversion method |
| `*TaxType` | mapped from the MYOB tax code (see `templates/checklists/tax_code_mapping.md`) |

> ⚠️ During a Xero conversion these open invoices are reconciled against
> the AR **conversion balance**, so revenue is not recognised twice. Use
> the account code your conversion method specifies — do **not** just
> re-post to the original income accounts, or you will double-count
> income in Xero. Confirm the approach before uploading.
