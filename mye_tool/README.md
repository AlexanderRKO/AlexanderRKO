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

Amounts have four decimal places; **positive = debit, negative =
credit**, so each journal entry sums to zero. (Quirk: journal lines end
with `\r\r\n`; the writer reproduces this so a round trip is byte-exact.)

## Usage

```bash
# What's in the file?
python -m mye_tool info ledger.mye
python -m mye_tool accounts ledger.mye
python -m mye_tool journal ledger.mye --account 477 --search payroll --limit 0
python -m mye_tool trial-balance ledger.mye

# Sanity-check before sending to your accountant
python -m mye_tool check ledger.mye

# Convert: CSV + Excel + JSON + QuickBooks IIF
python -m mye_tool export ledger.mye -o exported/ --format all

# Edit workflow: unpack -> edit CSVs in Excel -> repack
python -m mye_tool unpack ledger.mye -o work/
#   ... edit work/journal.csv, work/accounts.csv, work/company.csv ...
python -m mye_tool pack work/ -o edited.mye
```

`pack` re-validates everything and refuses to write a `.MYE` whose
entries don't balance (override with `--force`).

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
