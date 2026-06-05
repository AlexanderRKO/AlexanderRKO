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
