# mye_tool — read, convert and edit MYOB `.MYE` general ledger files

Reads the `.MYE` general ledger files produced by **Xero → Accounting →
Export accounting data → Accountants Enterprise (MAS)** (the same format
MYOB AccountRight/AccountEdge "Accountants Link" produces for MYOB
AE/AO). It can:

- show the contents in a legible format (company info, chart of
  accounts, journal, trial balance)
- validate the file (every journal entry balances, account codes exist,
  dates are inside the export period)
- export to **CSV**, **Excel (.xlsx)**, **JSON** and **QuickBooks IIF**
- **edit and save back as `.MYE`** — unpack to CSVs, edit them in Excel,
  repack to a valid `.MYE`

No dependencies for reading/CSV/editing; Excel export needs `openpyxl`.

## The .MYE format

A `.MYE` file is a ZIP archive containing two members:

| Member | Contents |
|---|---|
| `Extract.inf` | INI metadata: extract date, date range, company file name, batch id |
| `MYOBAO.TXT` | The ledger data — cp1252 text, CRLF line endings, tab-delimited |

`MYOBAO.TXT` has three sections:

```
[MYOB2000.05]
<company name> TAB <address> TAB TAB TAB <period start> TAB <period end>
[ACCOUNTS]
<code> TAB TAB <account name> TAB          (one line per account)
[JOURNAL]
<DD/MM/YYYY> TAB <ref> TAB <account code> TAB <amount> TAB <memo>
...                                        (blank line between entries)
```

Amounts are **positive = debit, negative = credit**, so each journal
entry sums to zero.

### Format variants handled

Different MYOB/Xero products emit slightly different `.MYE` files. The
tool detects each quirk on load and reproduces it on save, so a round
trip of the `MYOBAO.TXT` ledger is **byte-exact** in every case:

| Quirk | Accountants Enterprise (MAS) | Premier / BASLink |
|---|---|---|
| Journal line ending | `\r\r\n` | `\r\n` |
| Amount decimals | 4 (`242.0900`) | 2 (`-372.79`) |
| Trailing blank line | usually present | sometimes absent |
| Company ABN | often blank | in field 3 |
| Member name case | `Extract.inf` | `EXTRACT.INF` |
| Extra members | — | `BASLINK.TXT` (BAS/GST data) |

Any extra archive members (e.g. `BASLINK.TXT`) are carried through
verbatim, so editing and re-saving never drops BAS/GST side data.

## Usage

```bash
# What's in the file?
python -m mye_tool info ledger.mye
python -m mye_tool accounts ledger.mye
python -m mye_tool journal ledger.mye --account 477 --search payroll --limit 0
python -m mye_tool trial-balance ledger.mye

# Sanity-check before sending to your accountant
python -m mye_tool check ledger.mye

# Convert: CSV + Excel + JSON + QuickBooks IIF + Xero chart of accounts
python -m mye_tool export ledger.mye -o exported/ --format all

# Just the Xero (AU) chart-of-accounts import file
python -m mye_tool export ledger.mye -o exported/ --format xero-coa

# Edit workflow: unpack -> edit CSVs in Excel -> repack
python -m mye_tool unpack ledger.mye -o work/
#   ... edit work/journal.csv, work/accounts.csv, work/company.csv ...
python -m mye_tool pack work/ -o edited.mye
```

`pack` re-validates everything and refuses to write a `.MYE` whose
entries don't balance (override with `--force`).

### Xero chart-of-accounts import

A `.mye` only stores each account's **code and name** — Xero's importer
also requires **Type** and **Tax Code**, so importing a bare code/name
file fails with *"the first row does not contain the mandatory fields -
Code, Name, Type, Tax Code"*. The `xero-coa` export writes
`xero_chart_of_accounts.csv` (header `*Code,*Name,*Type,*Tax Code,...`)
plus a `xero_chart_of_accounts_REVIEW.csv` companion, and fills the
missing fields:

- **Type** is inferred, mostly from the account name (e.g. "Bank Fees" →
  `EXPENSE`, "Accounts Receivable" → `CURRENT`, "GST" → `CURRLIAB`,
  "Depreciation" → `DEPRECIATN`), with the code range as a fallback.
  Types are best-effort — rows flagged `REVIEW` in the companion file
  were guessed; check them before importing.
- **Tax Code** defaults to `BAS Excluded` on every account so the import
  succeeds cleanly; set GST on the income/expense accounts inside Xero
  afterwards.
- **Bank** accounts are mapped to `CURRENT` (current asset), not `BANK`,
  because Xero's CSV import rejects `BANK` accounts without a bank
  account number (which a `.mye` doesn't contain). Switch them to the
  Bank type in Xero after import — that's also where the BSB/account
  number is entered.
- **Xero-managed system accounts are excluded.** Accounts Xero creates
  and locks itself — Accounts Receivable, Accounts Payable, GST,
  Retained Earnings, Current Year Earnings, Rounding, Historical
  Adjustment, Tracking Transfers, Realised/Unrealised Currency Gains,
  Bank Revaluations, Wages Payable — already exist in every Xero org
  (including a clean file with the generic chart) and cannot be
  imported, so importing them makes the whole file fail. They are left
  out of the import file and listed as `SYSTEM - excluded` in the review
  file. (Pass `exclude_system=False` to the Python API to keep them.)

### Editing notes

- `journal.csv`: rows are grouped into journal entries by the `entry`
  column. The `amount` column (positive debit / negative credit) is
  authoritative; if you blank it, `debit`/`credit` columns are used.
- `accounts.csv`: add/rename/delete chart accounts. Every account code
  used in the journal must exist here.
- `company.csv`: company name, address and period dates.
- `Extract.inf` is carried through verbatim; edit it as plain text if
  you need to change the metadata MYOB AE/AO reads.

## Python API

```python
import mye_tool

mye = mye_tool.load("ledger.mye")
mye.company_name            # "KMB Online Pty Ltd"
mye.accounts                # [Account(code="610", name="Accounts Receivable"), ...]
mye.entries                 # journal entries, each a list of debit/credit lines
mye.trial_balance()         # (code, name, debits, credits, net) per account
mye.validate()              # list of problems, [] when clean

for line in mye.journal_lines:
    print(line.date, line.account_code, line.amount, line.memo)

mye.company_name = "New Name Pty Ltd"
mye.save("edited.mye")      # writes a valid .MYE ZIP archive
```

## Tests

```bash
python -m pytest mye_tool/tests/ -v
```

Tests use a synthetic fixture that mirrors the real byte layout — no
client data lives in this repository.

## Limitations

- Old Mac AccountEdge exports were sometimes StuffIt (`.sit`) archives
  rather than ZIP; the tool detects this and tells you to extract with
  `unar` first.
- The MAS export is a *general ledger* extract: chart of accounts +
  journals only. Contacts, invoices and payroll detail are not in the
  file, so no tool can extract them from it — export those separately
  (see `myob_to_xero_migration/` for the full migration checklist).
