# 12 — Payroll history (RAW MYOB export)

⚠️ **HIGH-SENSITIVITY DATA — read `../../PRIVACY.md` before pulling.**

Payroll Activity, Entitlement Balances, and Super accrual reports for
the conversion FY. These exports contain identified earnings,
deductions, super, PAYG, and leave per employee.

## What goes here

- Payroll Activity (detailed) for conversion FY — `payroll_activity_<from>_<to>.csv`.
- Entitlement Balances — `leave_balances_<date>.csv`.
- Superannuation accrual / payment report — `super_<from>_<to>.csv`.
- PAYG withholding summary — `payg_<from>_<to>.csv`.
- STP finalisation evidence (PDF) for the previous FY — `stp_final_<fy>.pdf`.

## Privacy controls

Same as `../04_employees/README.md` — this dataset carries identified
earnings information and is equally sensitive. Treat as TFN-adjacent:
even where the TFN itself isn't in the file, identity + earnings is
serious-harm-grade data under the NDB scheme.

## Xero limitation — what actually gets loaded

Xero's API does **not** accept historical payruns. The data in this
folder seeds two outputs only:

1. **Employee YTD opening balances** at the conversion date
   (gross, PAYG, super, leave-pay items, allowances).
2. **Reference-only bills or manual journals** for any historic
   payruns the client wants visible inside Xero. These do not
   appear in Payroll History and must not be edited as payroll.

Things that do **not** come across at all:
- Casual employees' leave entitlement balances — set manually in
  Xero before the first pay run.
- Employer expenses other than superannuation.
- Pay items not used during the conversion FY.
- Detailed payrun breakdowns (only YTD totals survive).

## Data minimisation guidance

When you transform these into Stage-02 opening balances, carry forward
**only** what Xero needs to seed YTD figures and leave balances per
current employee. Terminated employees from prior FYs do not need to
be migrated — their history stays in the locked Stage-03 PDFs.

## Do NOT

- ❌ Send these reports as email attachments.
- ❌ Combine with the `04_employees/` export into a single "everything"
      file — keep the datasets separated so access can be revoked
      independently.
- ❌ Commit to Git.
- ❌ Retain past the destruction date in `../../PRIVACY.md` §5.
