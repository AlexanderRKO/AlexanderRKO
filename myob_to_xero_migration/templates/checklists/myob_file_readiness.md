# MYOB file-readiness checklist (pre-export gate)

Complete **every** item in this checklist inside the client's MYOB file
**before** any export lands in `01_exports_from_myob/`. A dirty source
file makes the rest of the migration unreliable — the cheapest fix is
upstream.

Owner: lead accountant. Witness/reviewer: support staff.

## 1. Reconciliations

- [ ] Every bank and credit-card account reconciliation is complete
      up to the last statement date.
- [ ] **All bank transactions have been coded** — no entries sitting
      in an "uncategorised" or "electronic clearing" account.
- [ ] Statement balance on each account matches the bank statement
      at the last reconciliation date (record value + date below).
- [ ] All **clearing accounts reconcile to NIL** (electronic clearing,
      undeposited funds, payroll clearing, GST clearing, inter-company
      clearing). List any non-zero residual in the exception log.

| Account | Last rec date | Stmt balance | MYOB balance | Variance |
| ------- | ------------- | ------------ | ------------ | -------- |
| | | | | |

## 2. AR / AP integrity

- [ ] Accounts Receivable ageing total = Trial Balance AR control =
      AR reconciliation report.
- [ ] Accounts Payable ageing total = Trial Balance AP control =
      AP reconciliation report.
- [ ] All applicable credit notes have been applied against open
      invoices/bills (unless intentionally held open).
- [ ] No negative AR/AP balances per contact without a documented
      reason.

## 3. GST / BAS

- [ ] Last lodged BAS reconciles to the GST control accounts at the
      end-of-period.
- [ ] GST collected − GST paid in the system matches BAS lodgement.
- [ ] PAYG withholding control matches the PAYG payable balance.

## 4. Payroll (only if payroll is in scope)

- [ ] Last pay run is fully posted and reconciled.
- [ ] Super clearing account is at NIL or matches the next-quarter
      liability.
- [ ] Terminated employees have a termination date recorded.
- [ ] STP submissions are up to date.
- [ ] Leave balances reconcile to the entitlement report.

## 5. Inventory (only if inventory is in scope)

- [ ] Inventory valuation report = Inventory control account in TB.
- [ ] Negative on-hand quantities are zero or documented.
- [ ] Average cost is set for every active item.

## 6. File-level housekeeping

- [ ] `File ▸ Verify Company File` runs clean (no errors / warnings).
- [ ] A backup of the MYOB file has been taken **and stored** in the
      firm's managed location (`01_exports_from_myob/00_company_file_info/`).
- [ ] **Period Lock Date** set as close to today as possible, leaving
      only unreconciled periods open.
- [ ] **End-of-Year Lock Date** set to the day immediately before the
      conversion date.
- [ ] Inactive users disabled; remaining user list documented.
- [ ] No pending or draft journals older than 7 days.

## 7. Final readiness gate

- [ ] All sections above ticked, or exceptions logged in
      `../../04_xero_post_upload_checks/05_exception_log/exceptions.csv`
      with `area = pre-export`.
- [ ] Lead accountant signature + date below.
- [ ] Row in `../../INDEX.md` change log records "file readiness
      cleared".

Signed: _______________________  Date: __________

Reviewer:_______________________ Date: __________
