# MYE Tool — User Guide

How to access and use `mye_tool`, the converter/editor for MYOB `.MYE`
general ledger files (the file Xero creates under **Accounting → Export
accounting data → Accountants Enterprise (MAS)**).

What it does, in one line: open a `.mye` file, see what's inside, check
it balances, export it to Excel/CSV/JSON/QuickBooks, or edit the data
and save it back as a valid `.mye`.

---

## 1. One-time setup

You need two things: **Python 3** and a copy of this repository.

### Check Python is installed

Open a terminal (Mac: **Terminal** app; Windows: **PowerShell**) and type:

```bash
python3 --version        # Mac/Linux
python --version         # Windows
```

You want version 3.9 or newer. If you don't have it, download it from
https://www.python.org/downloads/ (on Windows, tick **"Add Python to
PATH"** during install).

> **Windows note:** everywhere this guide says `python3`, type `python`
> instead.

### Get the repository

If you don't already have it on this computer:

```bash
git clone https://github.com/AlexanderRKO/AlexanderRKO.git
cd AlexanderRKO
```

If you already have it, just update it:

```bash
cd AlexanderRKO
git pull
```

### Install the one optional extra (for Excel export)

```bash
pip install openpyxl
```

Everything else (viewing, checking, CSV export, editing, repacking)
works with plain Python — no installs needed.

### Make sure you run commands from the repository folder

All commands below assume your terminal is sitting in the `AlexanderRKO`
folder (the one that contains `mye_tool/`). If a command says
`No module named mye_tool`, you're in the wrong folder — `cd` back to it.

---

## 2. Get a .MYE file out of Xero

1. In Xero: **Accounting → Export accounting data**
2. Select product: **Accountants Enterprise (MAS)**
3. Pick the date range (e.g. 1 Jul 2024 – 30 Jun 2025)
4. Download the **General Ledger** — you'll get something like
   `KeepMyBooksOnli_AE_GL_2026_JUN_11.mye`

In the commands below, replace `ledger.mye` with the path to your
downloaded file, e.g. `~/Downloads/KeepMyBooksOnli_AE_GL_2026_JUN_11.mye`.

> Tip: you can drag the file from Finder/Explorer into the terminal
> window and it will type the full path for you.

---

## 3. Everyday commands

### See what's in the file

```bash
python3 -m mye_tool info ledger.mye
```

Shows company name, period, and how many accounts and journal entries
the file contains.

### List the chart of accounts

```bash
python3 -m mye_tool accounts ledger.mye
```

### Browse the journal

```bash
# First 50 lines
python3 -m mye_tool journal ledger.mye

# Everything posted to account 477 (Wages & Salaries)
python3 -m mye_tool journal ledger.mye --account 477 --limit 0

# Find transactions by memo text
python3 -m mye_tool journal ledger.mye --search "bank fee"
```

`--limit 0` means "show all"; the default is 50 lines.

### Trial balance (net movement per account)

```bash
python3 -m mye_tool trial-balance ledger.mye
```

### Health-check the file before sending it to an accountant

```bash
python3 -m mye_tool check ledger.mye
```

Confirms every journal entry balances to zero, every account code used
exists in the chart, and all dates are valid and inside the export
period. Prints `OK` if clean, or lists each problem if not.

---

## 4. Export to Excel, CSV and other formats

```bash
python3 -m mye_tool export ledger.mye -o exported/
```

This creates an `exported/` folder containing:

| File | What it is |
|---|---|
| `<name>.xlsx` | Excel workbook with 4 sheets: Company, Accounts, Journal, Trial Balance |
| `journal.csv` | Every journal line with debit/credit columns and account names |
| `accounts.csv` | The chart of accounts |
| `trial_balance.csv` | Net movement per account |
| `company.csv` | Company details and export metadata |
| `<name>.json` | The whole file as structured data (for other software) |
| `<name>.iif` | QuickBooks Desktop general journal import file |

Want just one format? Add `--format xlsx` (or `csv`, `json`, `iif`).

---

## 5. Edit a .MYE and save it back as .MYE

Three steps: **unpack → edit → pack**.

### Step 1 — Unpack into editable CSVs

```bash
python3 -m mye_tool unpack ledger.mye -o work/
```

This creates a `work/` folder with `journal.csv`, `accounts.csv`,
`company.csv` and `Extract.inf`.

### Step 2 — Edit in Excel (or any editor)

- **journal.csv** — change dates, amounts, memos, account codes; add or
  delete lines. Rows with the same `entry` number belong to the same
  journal entry, and each entry must sum to zero. The `amount` column is
  the master value (positive = debit, negative = credit); if you'd
  rather type in the `debit`/`credit` columns, blank out `amount` on
  that row.
- **accounts.csv** — rename accounts or add new codes. Every code used
  in the journal must exist here.
- **company.csv** — company name, address, period dates.

> **Excel warnings:**
> - When saving, keep the file as **CSV** (Excel will nag you — say yes).
> - Dates must stay in **DD/MM/YYYY** format. If Excel reformats them,
>   select the date column and set the format back before saving.
> - Account codes like `610A` are fine, but format the code columns as
>   **Text** so Excel doesn't mangle anything numeric.

### Step 3 — Pack back into a .MYE

```bash
python3 -m mye_tool pack work/ -o edited.mye
```

The tool **re-validates before writing** — if an entry no longer
balances or uses an unknown account code, it lists the problems and
refuses to write the file (so you can't accidentally produce a broken
ledger). Fix the CSVs and run `pack` again. If you truly need to write
anyway, add `--force`.

Then confirm the result:

```bash
python3 -m mye_tool check edited.mye
```

The output is a genuine `.mye` that MYOB AE/AO will import. An unedited
unpack→pack reproduces the original file byte-for-byte.

---

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `python3: command not found` | Install Python (section 1); on Windows use `python` |
| `No module named mye_tool` | `cd` into the `AlexanderRKO` folder first |
| `Excel export needs the 'openpyxl' package` | `pip install openpyxl` |
| `Not a recognised .MYE file` | The file isn't a MAS general ledger export — re-export from Xero choosing **Accountants Enterprise (MAS)** |
| `is not a ZIP-based .MYE file` | Very old Mac AccountEdge exports were StuffIt archives; extract with The Unarchiver first |
| `pack` refuses with "does not balance" | A journal entry's lines don't sum to zero — check the `amount` column for the entry number it names |
| Dates look wrong after editing in Excel | Re-format the date column to DD/MM/YYYY and re-save as CSV |

---

## 7. Quick reference

```bash
python3 -m mye_tool info ledger.mye                      # summary
python3 -m mye_tool accounts ledger.mye                  # chart of accounts
python3 -m mye_tool journal ledger.mye --search "rent"   # browse/filter journal
python3 -m mye_tool trial-balance ledger.mye             # per-account totals
python3 -m mye_tool check ledger.mye                     # validate
python3 -m mye_tool export ledger.mye -o exported/       # Excel/CSV/JSON/IIF
python3 -m mye_tool unpack ledger.mye -o work/           # edit step 1
python3 -m mye_tool pack work/ -o edited.mye             # edit step 3
python3 -m mye_tool --help                               # all options
```

## 8. Good to know

- **Privacy:** everything runs locally on your computer — no data is
  uploaded anywhere.
- **Scope:** a MAS `.mye` contains the general ledger only (chart of
  accounts + journals). Contacts, invoices and payroll detail are not
  in the file — export those separately (see `myob_to_xero_migration/`).
- **Technical format details and the Python API** are documented in
  [`mye_tool/README.md`](README.md).
- **Tests:** `python3 -m pytest mye_tool/tests/ -v` (needs `pip install pytest`).
