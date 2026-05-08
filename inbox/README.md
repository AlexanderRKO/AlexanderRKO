# Inbox — Drop Monthly Reports Here

Each month gets its own folder named `YYYY-MM` (e.g. `2026-04`). Drop all
source files for that month into the folder. The ingest pipeline parses
them and updates `dashboard/src/data.json` automatically.

## What to drop

| File | Source | Filename hint (any of) |
|---|---|---|
| Zai Tax Invoice PDF | Zai billing portal | `*zai*invoice*.pdf` |
| Platform Revenue CSV | Managed admin → Reports | `*platform*revenue*.csv` |
| Agency Performance CSV | Admin → Reports → Agency Monthly Performance | `*agency*performance*.csv` |
| MW Platform Charges CSV | Admin → Platform Charges (Plan #4 + month range) | `*mw*charges*.csv` |
| `manual.yml` | hand-edited | exact name |

The ingest pipeline matches by case-insensitive substring on the filename, so
`Zai Invoice 4420.pdf` and `zai_tax_invoice_apr26.pdf` both work.

## manual.yml

The `manual.yml` file holds figures that can't be parsed (MW rebate amount,
agency rev share, reconciliation notes). Copy `inbox/_template/manual.yml`
into your month folder and fill in the gaps.

## Folder structure

```
inbox/
├── _template/
│   └── manual.yml           # template — copy this into each new month
├── _archive/                # auto-archived after successful ingest
├── 2026-04/                 # one folder per month
│   ├── zai-invoice-4420.pdf
│   ├── platform-revenue-apr26.csv
│   ├── agency-performance-apr26.csv
│   ├── mw-charges-apr26.csv
│   └── manual.yml
└── 2026-05/
    └── ...
```

## How updates happen

- **Watcher mode** — `python -m ingest watch` runs a daemon that re-parses
  the month folder ~5 seconds after files stop arriving. Good for "drop and
  forget" workflow.
- **One-shot mode** — `python -m ingest ingest inbox/2026-04` parses a
  single folder. Good for catching up or re-running after editing manual.yml.
- **Bulk mode** — `python -m ingest all` walks every YYYY-MM folder and
  ingests them in chronological order. Used to backfill or rebuild data.json.

## Validation

After parsing, the pipeline checks that `zaiNet` equals the sum of all 14
Zai line items (within $0.02 rounding). If it doesn't, you'll see a warning;
edit `manual.yml` to set the correct totals or add the difference to the
largest line (`payoutRealtime`).
