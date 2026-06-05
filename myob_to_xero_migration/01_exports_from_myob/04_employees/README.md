# 04 — Employees (RAW MYOB export)

⚠️ **HIGH-SENSITIVITY DATA — read `../../PRIVACY.md` before pulling.**

This folder receives raw employee card exports from MYOB Payroll. The
contents are subject to the **Privacy Act 1988**, the **Tax File
Number Rule 2015**, and the **Notifiable Data Breaches scheme**.

## What goes here

- Employee card export (`employees_<date>.csv`) containing: name, DOB,
  TFN, address, bank/BSB, super fund, tax scale, leave balances,
  standard pay.
- Optionally: signed TFN declarations, super choice forms, contracts
  (PDFs) if the client wants them carried forward.

## Privacy controls (must be in place before export)

- [ ] You're listed on the authorised migration team in `../../INDEX.md`.
- [ ] MFA is on for MYOB, Xero, email, and storage.
- [ ] Storage is the firm's managed, access-controlled location — not
      a personal drive, not a USB stick, not email.
- [ ] `.gitignore` excludes this folder (verify with `git status`
      after the first export lands — only `.gitkeep` / `README.md`
      should appear as tracked).
- [ ] Transfer channel from MYOB → this folder is direct download to
      an encrypted device, or an encrypted expiring link from the
      client. **No plain-email attachments.**

## Do NOT

- ❌ Email this file anywhere.
- ❌ Paste TFNs / bank details into Slack, Teams, chat, or screenshots.
- ❌ Open this file during shared screen-share sessions without
      column redaction.
- ❌ Commit this file to Git.
- ❌ Retain this file past the destruction date in `../../PRIVACY.md` §5.

## Retention

Secure-delete within 30 days of final sign-off and log the destruction
in `../../04_xero_post_upload_checks/06_final_sign_off/`.
