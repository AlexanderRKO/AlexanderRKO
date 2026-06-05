# 12 — Payroll opening balances (CLEANSED for Xero upload)

⚠️ **HIGH-SENSITIVITY DATA — read `../../PRIVACY.md` before working
in this folder.**

Per-employee YTD figures (earnings, tax, super, leave) reshaped for
Xero's payroll opening-balances import.

## Scope

- Conversion FY YTD: gross, PAYG withheld, super (SG + salary
  sacrifice + employee contributions), pre-tax / post-tax deductions.
- Leave balances at conversion date (annual, personal/carer's, long
  service if applicable).
- Allowances and reportable fringe benefits.

## Minimisation

- Current employees only — leave balances and YTD figures for
  terminated staff are not carried forward.
- No commentary, no termination reasons, no medical notes.

## Xero-specific gotchas to flag to the client

- **Casual leave balances are dropped** by the Xero importer. Note
  the affected employees in the Action Checklist so the client can
  re-enter them manually.
- **Pay items linked to bank/asset accounts in MYOB** are remapped
  to a payroll clearing account on the Xero side. The client must
  unlink them before the first Xero pay run; track in
  `../../04_xero_post_upload_checks/03_balance_reconciliations/clearing_accounts_tracker.csv`.
- **Only superannuation** comes across as employer expense — other
  employer costs (payroll tax, workers comp) do not seed.

## Channel, storage, logging

Same controls as `../03_employees/` — managed storage only, HTTPS
upload only, validator logs must not echo identified amounts at
employee level (aggregate row counts and hashes only).

## Sign-off & destruction

- Sign-off lives in `../../03_finalized_reports/05_sign_off_documents/`
  before any upload.
- Secure-delete within 30 days of final Xero sign-off; log the
  destruction in `../../04_xero_post_upload_checks/06_final_sign_off/`.
