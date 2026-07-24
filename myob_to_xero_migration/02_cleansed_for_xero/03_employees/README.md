# 03 — Employees (CLEANSED for Xero upload)

⚠️ **HIGH-SENSITIVITY DATA — read `../../PRIVACY.md` before working
in this folder.**

Employee records reshaped into Xero's payroll import template,
minimised to what Xero actually needs at cut-over.

## Data minimisation rules (apply before any upload)

- Keep **current employees only**. Terminated employees go in the
  locked Stage-03 PDFs, not into Xero.
- Drop free-text "notes" fields from MYOB cards — they often contain
  performance or medical commentary that has no place in the new file.
- Keep **current** address and bank account per employee — strip
  history.
- Emergency contacts: include only if the client has explicitly
  confirmed; otherwise omit.
- TFNs: include once, in the dedicated column. Never duplicate into
  description, notes, or filename fields.

## Validation logging

The validator (`../../templates/scripts/validate_xero_csv.py`) must
**never** echo TFN, DOB, or bank values to its log. Logs for this
folder should record row counts, hashes, and column-level pass/fail
only — see `../_validation_logs/`.

## Channel & storage

- Upload directly from this folder to Xero's import UI over HTTPS.
  Do not stage the file on a third-party converter or "CSV cleaner"
  web tool.
- Once Xero confirms the import, **secure-delete** this CSV within 30
  days and log the destruction.

## Do NOT

- ❌ Email the cleansed CSV to the client for "review" — share a
      redacted PDF summary instead.
- ❌ Commit to Git.
- ❌ Reuse this CSV for another client by find/replace — generate
      fresh from MYOB.
