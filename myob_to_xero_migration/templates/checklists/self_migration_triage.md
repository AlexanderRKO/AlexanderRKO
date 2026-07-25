# Self-migration triage — which client files do we convert ourselves?

The point of this framework is to stop the practice being blocked by a
third party's queue. Most client ledgers can be migrated in-house in a
few hours. A minority genuinely need a full conversion service. This
decides which is which, before you start, rather than discovering it
halfway through.

## The two fundamentally different jobs

People say "migration" to mean two different things, and conflating them
is what makes the decision feel hard.

**Opening-balance conversion (what you do yourself).** Xero starts at the
conversion date with correct balances, open debtors, open creditors and
open bank positions. History stays in the archived MYOB file, readable
forever through MYOB AE. This is what most small business clients
actually need, and it is what a large share of accountants do as standard
practice.

**Full historical conversion (what JetConvert does).** Years of
transaction detail recreated inside Xero. Genuinely valuable when the
client lives in the ledger daily and searches old transactions, or when
a lender or auditor expects history in the live file.

The question is never "can we do this ourselves" — it is "does this
client need history *live in Xero*, or is readable-on-request enough?"

## Decision rule

Self-migrate when **all** of these hold:

- No payroll, or payroll can start fresh from a period boundary
- No inventory carrying stock on hand and average cost
- Single currency
- The debtors and creditors subledgers reconcile to their control
  accounts (nil out of balance)
- The client does not need years of transaction history live in Xero
- No unusual sub-modules in use (jobs costing, fixed-asset register
  driving depreciation entries)

Send to JetConvert when **any** of these hold:

- Payroll running mid-year with meaningful year-to-date balances,
  leave accruals and STP history to preserve
- Inventory with stock on hand, average cost and item history
- Multi-currency
- The client explicitly wants full transaction history inside Xero
- The file is out of balance in ways you cannot resolve quickly
- The client is high-value or high-sensitivity and you want a third
  party carrying the conversion risk

## Why timing pushes toward doing it now

Payroll is the single biggest driver of conversion complexity, and its
difficulty is a function of how far into the financial year you are.
Convert close to 1 July and year-to-date payroll is near zero, so a
client with payroll may still be a self-migration candidate. Convert in
March and you are reconstructing three quarters of YTD figures, leave
balances and STP reporting — which is precisely when you want a
conversion service.

The practical consequence: files you could comfortably do yourself in
July become JetConvert files by summer. Triage the whole book now and
move the easy ones while the window is open.

## Sequencing the book

Do not start with the most urgent client. Start with the most boring one.

1. **Pilot** — one small, simple, low-risk client. Prove the process end
   to end and time it honestly.
2. **Batch the simple ones** — everything matching the self-migrate rule.
   These get faster each time; the second is half the effort of the first.
3. **Clients with a deadline** — anyone who must move on a date you
   control rather than a date JetConvert controls.
4. **Queue the complex ones with JetConvert** — and because you have
   removed everything easy from their queue, the ones that remain get
   attention sooner.

Keep MYOB AE as the permanent archive throughout. Nothing is deleted;
history stays readable. That is what makes this reversible in practice
and is the single most important risk control in the whole approach.

## Per-file process (self-migration)

1. Run the readiness checks in `myob_file_readiness.md` — reconcile
   bank, debtors, creditors and GST at the conversion date.
2. Export the source reports (see `01_exports_from_myob/` folder READMEs
   for exactly which report and which as-at date).
3. Convert open items and confirm the reconciliation gate passes:

   ```
   python migration.py convert --report "<Receivables Reconciliation [Detail].txt>" \
       --terms-report "<Aged Receivables [Detail].txt>" \
       --side AR --out ./<client>/ --account-code <code>
   ```

   The command refuses to write files if the subledger does not agree
   with the general ledger. Treat a failure as a genuine stop, not an
   obstacle to override — an out-of-balance file converted is an
   out-of-balance file you now have to fix inside Xero.
4. Repeat with `--side AP` for creditors.
5. Load chart of accounts, contacts, open items, then conversion
   balances, in that order.
6. Verify against the acceptance checks before the client transacts.
7. Archive the MYOB file and record its location on the client file.

## What to tell clients

Keep it short and lead with what they get, not with the mechanics:

> We are moving your file to Xero as at [date]. Your opening balances,
> outstanding invoices and bills all come across, so nothing is lost and
> your day-to-day carries on unchanged. Your full MYOB history stays
> archived and we can access it any time you need it.

Most clients care about two things: does my data survive, and does
anything break on Monday. Answer both in the first sentence.
