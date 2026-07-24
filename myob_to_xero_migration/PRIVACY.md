# Privacy — Handling Payroll Data During Migration

Payroll data is the highest-sensitivity dataset in this migration. A
breach here exposes you to penalties under the **Privacy Act 1988**
(including the **Tax File Number Rule 2015**), the **Notifiable Data
Breaches (NDB) scheme**, and direct ATO obligations as an employer's
agent. Read this document **before** pulling anything from MYOB's
Payroll module.

> Nothing here is legal advice. If in doubt, consult the OAIC guidance
> at https://www.oaic.gov.au and the ATO's TFN handling rules.

## 1. What counts as sensitive payroll data

Treat every field below as **personal information**, and the TFN-flagged
ones as having **additional statutory protection** under the TFN Rule:

| Field | Sensitivity |
| ----- | ----------- |
| Tax File Number (TFN) | **TFN Rule** — strictly controlled |
| Date of birth | Personal information |
| Full name + home address | Personal information |
| Bank account / BSB | Sensitive (financial) |
| Superannuation member number | Sensitive (financial) |
| Salary, pay rate, deductions | Sensitive (employment) |
| Leave balances, leave reasons | Sensitive (may infer health) |
| Health/medical deductions, child support | Sensitive — strict need-to-know |
| Visa / work-rights documents | Sensitive |
| Emergency contacts | Personal (third-party data) |

## 2. Mandatory warnings

⚠️ **Never** email raw payroll exports as attachments. Email is not a
controlled channel and is the most common source of breaches.

⚠️ **Never** store payroll exports in personal cloud drives
(personal Dropbox, personal Google Drive, USB sticks). Use the firm's
approved, access-controlled storage only.

⚠️ **Never** share TFNs verbally, in chat (Slack, Teams, WhatsApp), or
in screenshots. The TFN Rule limits disclosure to the specific purpose
of administering tax law.

⚠️ **Never** commit payroll exports to this Git repository. See
`.gitignore` rules in §6.

⚠️ **Never** leave payroll data on your screen unattended. Lock the
workstation.

⚠️ **Never** retain payroll exports beyond the migration window. See
the retention/destruction schedule in §5.

## 3. Recommended controls (apply before pulling any data)

### People & access
- [ ] Limit access to a **named migration team** (lead accountant +
      ≤2 supporting staff). Record names in `INDEX.md`.
- [ ] Each team member has signed the firm's confidentiality
      undertaking covering payroll data and TFNs.
- [ ] Multi-factor authentication is enabled on every MYOB, Xero,
      email, and storage account used.
- [ ] Client has authorised the migration in writing and nominated a
      single point of contact for payroll questions.

### Transfer channels
- [ ] Pull MYOB exports directly to a **work-issued, full-disk-encrypted**
      device.
- [ ] Move files between client and firm using **encrypted, expiring
      links** (e.g. SharePoint/OneDrive with link expiry, or a secure
      portal). Avoid plain email attachments.
- [ ] If a physical handover is unavoidable, use an **encrypted USB**
      and obtain a signed chain-of-custody receipt.

### Storage at rest
- [ ] Project folder lives on a managed, access-controlled storage
      area (firm SharePoint, secure file share). The folder inherits
      a permission group containing only the migration team.
- [ ] Folder-level encryption-at-rest is enabled (provider default is
      usually fine; confirm).
- [ ] Workstation drives are encrypted (BitLocker / FileVault /
      LUKS).

### In-flight processing
- [ ] When cleansing in Stage 02, **minimise the data carried
      forward**. Drop fields Xero does not need (see §4).
- [ ] Do not open payroll CSVs in shared screen-share sessions
      without redacting TFN/DOB/bank columns first.
- [ ] Validation logs in `02_cleansed_for_xero/_validation_logs/`
      must not echo raw TFN or bank values — log row counts and
      hashes only.

## 4. Data minimisation — what NOT to carry into Xero

Xero stores TFNs encrypted, but you should still strip anything not
required for the conversion-date cut-over:

- Historical bank-account numbers for terminated employees — keep
  current employees only.
- Free-text "notes" fields on employee cards (may contain medical /
  performance commentary).
- Emergency contact details unless the client confirms they want them
  carried over.
- Old addresses — keep current address only.
- Documents/attachments (visas, contracts) — upload only those the
  client explicitly nominates.

## 5. Retention & destruction

| Artefact | Retain for | Then |
| -------- | ---------- | ---- |
| Stage 01 raw payroll exports | Until 30 days after final sign-off | **Secure delete** (cryptographic shred or vendor-supported purge). Document deletion in `04_xero_post_upload_checks/06_final_sign_off/`. |
| Stage 02 cleansed payroll CSVs | Until 30 days after final sign-off | Secure delete (uploaded copy lives in Xero from then on). |
| Stage 03 locked payroll reports (PDF) | 7 years (ATO record-keeping) | Move to long-term encrypted archive; remove from the active project folder. |
| Validation logs | 90 days | Secure delete. |
| Working notes / Slack chat | Migration window only | Purge after sign-off. |

Record the destruction action (who, when, what) in
`04_xero_post_upload_checks/06_final_sign_off/payroll_destruction_log.md`.

## 6. Git & this repository

This repository **must never contain real payroll data**, even
temporarily. The project's top-level `.gitignore` should exclude:

```
myob_to_xero_migration/01_exports_from_myob/04_employees/*
myob_to_xero_migration/01_exports_from_myob/12_payroll_history/*
myob_to_xero_migration/02_cleansed_for_xero/03_employees/*
myob_to_xero_migration/02_cleansed_for_xero/12_payroll_opening_balances/*
!**/.gitkeep
!**/README.md
```

Real client files belong on the firm's managed storage; only the
**structure, READMEs and templates** are version-controlled here.

## 7. If a breach occurs

A "breach" includes: a payroll file sent to the wrong address, a lost
device, an unauthorised access alert, or a misdirected link.

1. **Stop further transmission** immediately. Don't try to "fix" by
   forwarding again.
2. Notify the firm's privacy officer / partner-in-charge within the
   hour.
3. Preserve evidence (logs, email headers, link audit trails).
4. Assess against the NDB threshold: is serious harm likely? If yes,
   the OAIC and affected individuals must be notified — this is a
   statutory obligation, not a courtesy.
5. Record the incident in
   `04_xero_post_upload_checks/05_exception_log/exceptions.csv` with
   area = `privacy-incident` and the resolution path.

## 8. Pre-pull sign-off

Tick **all** of these before initiating any payroll export from MYOB:

- [ ] Client written authorisation on file.
- [ ] Migration team list locked and confidentiality undertakings
      signed.
- [ ] MFA confirmed on every system.
- [ ] Storage location confirmed (managed, encrypted, access-listed).
- [ ] Transfer channel confirmed (no plain email).
- [ ] `.gitignore` excludes payroll paths (verify with `git status`
      after a dry-run export).
- [ ] Retention/destruction owner named.
- [ ] This document acknowledged by every team member (record in
      `INDEX.md` change log).
