# Conversion Action Checklist — _<Client Name>_

**Conversion date:** _yyyy-mm-dd_
**MYOB file:** _<file ref>_
**Xero organisation:** _<org name / tenant ID>_
**Delivered by:** _<lead accountant>_
**Date delivered:** _yyyy-mm-dd_

This is the single client-facing summary of the conversion. It rolls up
all Stage-04 checks into one document. Attach the post-conversion
Trial Balance PDF when delivering.

---

## 1. What was converted ✅

| Area | Scope | Notes |
| ---- | ----- | ----- |
| Chart of accounts | All active accounts | Inactive accounts archived in Xero |
| Customers / suppliers | All active contacts | Dedupes documented |
| Inventory items | Active items + on-hand at conv. date | Basic data only |
| Open AR invoices | All open at conv. date | Reconciled per contact |
| Open AP bills | All open at conv. date | Reconciled per contact |
| Bank accounts | All active | Opening balances match statements |
| Conversion balances | Trial Balance @ conv. date | See Section 3 |
| Tracking categories | (List names) | Was MYOB Jobs |
| Tax rates | Standard AU + custom (list) | See tax mapping doc |
| Fixed assets | Register loaded | Depreciation method per asset |
| Payroll | Employee opening balances + YTD | See Section 4 limitations |

## 2. What was NOT converted ⚠

| Item | Why | Action you need to take |
| ---- | --- | ----------------------- |
| Historical payruns | Xero API does not accept historic payruns | Already reflected in YTD opening balances |
| Closed-period detail beyond conv. FY | Out of scope for this package | Refer to locked MYOB PDFs in `03_finalized_reports/` |
| Casual employees' leave balances | Xero does not accept casual leave on import | Set up manually in Xero if required |
| MYOB In Tray attachments | Manual re-attach | Use Hubdoc / Xero Files |
| Recurring transaction templates | Schedules don't migrate | Recreate in Xero (list provided) |
| Custom MYOB reports | No equivalent in Xero | Replace with Xero report packs |
| Free-text employee notes | Privacy minimisation | Re-enter only if business-required |

## 3. Post-conversion checks already completed ✅

| Check | Result | Variance | Evidence |
| ----- | ------ | -------- | -------- |
| Conversion balances saved (Xero accepted) | ✅ | — | Screenshot |
| Equity = Net Profit movement | ✅ | $0.00 | `equity_vs_net_profit_check.csv` |
| Trial Balance match (MYOB vs Xero) | ✅ | within $1 | `trial_balance_diff.csv` |
| Aged Receivables per contact | ✅ | — | `02_contact_verifications/` |
| Aged Payables per contact | ✅ | — | `02_contact_verifications/` |
| Bank opening balances vs statements | ✅ | — | `bank_recs_<date>.pdf` |
| GST control accounts vs last BAS | ✅ | — | `gst_<period>.pdf` |
| Clearing/suspense accounts at NIL | ✅ | $0.00 | `clearing_accounts_tracker.csv` |
| Payroll YTD per employee | ✅ | — | Per-employee diff |
| Fixed asset cost & accum. depreciation | ✅ | — | Register diff |
| Tracking categories active | ✅ | — | Settings screenshot |
| Inventory valuation | ✅ | — | Inventory report diff |

## 4. Payroll — important notes for you

- Historic payruns appear in Xero as **bills or manual journals**,
  not as payroll runs. They are reference-only and **must not** be
  re-edited as payroll.
- Employee YTD figures are loaded as **opening balances**. Your next
  pay run in Xero will pick up from these figures.
- Casual employees: leave entitlement balances were **not** carried.
  Set them in Xero before the first pay run.
- Pay items previously linked to bank/asset accounts in MYOB have
  been redirected to a **payroll clearing account**. Unlink them
  before processing your first Xero pay run (see Section 5).

## 5. Things you need to do in Xero before going live

- [ ] Connect bank feeds for each active bank/credit card account.
- [ ] Verify and unlink the payroll clearing account from any pay
      items still pointing at it.
- [ ] Review the Suspense account — it must be cleared via manual
      journals before the first BAS.
- [ ] Set the **Lock Date** in Xero to the conversion date so no-one
      back-posts into the converted period.
- [ ] Invite users with appropriate roles.
- [ ] Recreate recurring sales/purchase templates (list attached).
- [ ] Re-attach Hubdoc / In Tray sources to bills as required.
- [ ] Confirm STP enrolment in Xero Payroll.
- [ ] Update direct-debit / direct-credit details with vendors and
      customers (BSB/account from MYOB has been migrated).

## 6. Sign-off

**Accountant** _<name>_ confirms the data above reconciles to the
locked MYOB reports in `03_finalized_reports/`.

Signature: _______________________  Date: __________

**Client** _<name>_ accepts the Xero file as the new system of record.

Signature: _______________________  Date: __________

## 7. Attached evidence

- `trial_balance_<date>.pdf` (MYOB)
- `trial_balance_<date>_xero.pdf` (Xero)
- `aged_receivables_<date>.pdf` (MYOB vs Xero)
- `aged_payables_<date>.pdf` (MYOB vs Xero)
- `bank_recs_<date>.pdf`
- `gst_<period>.pdf`
- `payroll_<from>_<to>.pdf`
- Privacy: `payroll_destruction_log.md`
