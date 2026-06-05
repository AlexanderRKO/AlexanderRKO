# Stage 04 — Post-upload checks (inside Xero)

After the cleansed files are uploaded to Xero, this folder is where the
**account-by-account verification** happens. The goal: prove that every
balance in the new Xero file matches the locked report in Stage 03,
one line at a time.

## Subfolders

| Folder | Purpose |
| ------ | ------- |
| `01_account_by_account_checklists/` | One worksheet per GL account with MYOB total, Xero total, variance |
| `02_contact_verifications/` | Per-customer / per-supplier balance and open-doc checks |
| `03_balance_reconciliations/` | Bank, GST control, payroll clearing, inventory control reconciliations |
| `04_transaction_spot_checks/` | Sampled transactions (first / last / random N per account) |
| `05_exception_log/` | Any variance > tolerance, with cause and resolution |
| `06_final_sign_off/` | Client and accountant signed acceptance of the Xero file |

## Workflow

1. **Pull a Trial Balance from Xero** at the conversion date and save
   it next to the Stage 03 MYOB TB.
2. **Run the automated acceptance gate**
   (`../templates/scripts/post_upload_acceptance_check.py`) with the
   MYOB TB and Xero TB as inputs — it produces / overwrites
   `01_account_by_account_checklists/trial_balance_diff.csv` and
   exits non-zero if any variance exceeds tolerance.
3. Investigate any variance > A$1.00:
   - If it's a cleansing/upload error → fix, re-upload, re-tick.
   - If it's a legitimate adjustment → record it in
     `05_exception_log/` with the journal that resolves it.
4. Run the same diff for:
   - Aged Receivables (per contact)
   - Aged Payables (per contact)
   - Bank balances (per account)
   - GST control
   - Payroll YTD per employee
   - Inventory valuation
   - Fixed asset cost and accumulated depreciation
5. **Clearing / suspense accounts** — every account in
   `03_balance_reconciliations/clearing_accounts_tracker.csv` must
   reach its target balance (typically zero) with a documented
   clearing journal reference. None of these accounts may carry a
   residual at sign-off.
6. **Equity vs Net Profit sanity check** — record in
   `03_balance_reconciliations/equity_vs_net_profit_check.csv`. The
   P&L Net Profit for the period must equal the movement in retained
   earnings on the Balance Sheet within tolerance.
7. When every check is 🟢, populate
   `06_final_sign_off/action_checklist_template.md` and deliver it as
   the consolidated client-facing summary of the conversion.

## Tolerance

- ≤ A$1.00 per account → accepted, recorded.
- > A$1.00 → must appear in `05_exception_log/` with resolution before
  sign-off.

## Definition of done

- Every row in `../INDEX.md` § 04 is 🟢 or has a documented exception.
- Xero Trial Balance == MYOB Trial Balance at conversion date (within
  tolerance, evidenced by the diff CSV).
- Client signed-off PDF stored in `06_final_sign_off/`.
