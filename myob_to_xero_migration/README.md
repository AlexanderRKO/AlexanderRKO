# MYOB Online → Xero Migration Toolkit

A structured, repeatable project framework for converting a client's MYOB
Online (AccountRight Live / Essentials / Business) company file into a Xero
organisation file.

The toolkit enforces a four-stage pipeline:

```
  ┌──────────────┐   ┌────────────────┐   ┌──────────────────┐   ┌────────────────────┐
  │ 01_EXPORTS   │ → │ 02_CLEANSED    │ → │ 03_FINALIZED     │ → │ 04_POST_UPLOAD     │
  │  (raw MYOB)  │   │ (Xero template)│   │  REPORTS         │   │  CHECKS (in Xero)  │
  └──────────────┘   └────────────────┘   └──────────────────┘   └────────────────────┘
```

| Stage | Folder | Purpose |
| ----- | ------ | ------- |
| 1 | `01_exports_from_myob/` | Receive every raw export pulled out of MYOB, kept in original format. |
| 2 | `02_cleansed_for_xero/` | Transform raw exports into Xero-approved CSV/XLSX templates. |
| 3 | `03_finalized_reports/` | Snapshot of pre-conversion balances, reconciliations, sign-offs. |
| 4 | `04_xero_post_upload_checks/` | Account-by-account verification inside Xero after upload. |

See `PLAN.md` for the full conversion plan and export mapping, and
`INDEX.md` for the live status of every artefact.

> ⚠️ **Before you pull any employee or payroll data, read `PRIVACY.md`.**
> Payroll exports contain TFNs and identified earnings — they are
> governed by the Privacy Act 1988, the TFN Rule 2015, and the
> Notifiable Data Breaches scheme. Real client files must never be
> committed to this repository; see `.gitignore`.

## Quick start

1. Read `PLAN.md` end-to-end before pulling any data.
2. Fill in client details in `INDEX.md` (company name, conversion date,
   GST status, payroll cut-over, etc.).
3. Work top-down through the four folders — do not skip stages.
4. Update the status column in `INDEX.md` whenever an artefact moves
   between stages.

## Conventions

- File naming: `<entity>_<scope>_<YYYYMMDD>.<ext>`
  e.g. `chart_of_accounts_full_20260605.csv`
- Every folder contains its own `README.md` describing required inputs,
  expected outputs, and the Xero template (where relevant).
- Nothing leaves a stage until its checklist in `INDEX.md` is ticked.
- Raw exports in `01_*` are immutable — never edit them in place; copy
  forward into `02_*` and transform there.
