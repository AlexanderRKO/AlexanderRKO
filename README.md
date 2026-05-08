# Managed Revenue & Cost Intelligence

Dashboard and ingest platform for **MAN2077 — Managed Platforms**, prepared
by LMS Advisory.

A React dashboard tracking monthly billing economics — revenue, Zai supplier
fees, Marshall White rebates, agency rev share, contribution margin — fed by
a Python ingest pipeline that watches a drop-folder for new monthly reports
and updates the dashboard's data file automatically.

All figures are **ex GST**.

## Layout

```
dashboard/   # Vite + React + Recharts (the UI)
ingest/      # Python folder-watcher + parsers (the data pipeline)
inbox/       # Drop YYYY-MM folders here to register a new month
tests/       # Parser smoke tests
DASHBOARD_INSTRUCTIONS.md   # Schema, business rules, monthly workflow
```

## Quick start

### 1. Run the dashboard

```bash
cd dashboard
npm install
npm run dev               # localhost:5173
# or
npm run build && npm run preview
```

The dashboard reads `dashboard/src/data.json`. That file is the single source
of truth for all months and MW office breakdowns.

### 2. Set up the ingest pipeline

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Add a new month

Create a folder under `inbox/` named `YYYY-MM` and drop these in:

| File | What it is |
|---|---|
| `*zai*invoice*.pdf` | Zai supplier tax invoice |
| `*platform*revenue*.csv` | Revenue by line item from the Managed admin portal |
| `*agency*performance*.csv` | Agency monthly performance export |
| `*mw*charges*.csv` | Marshall White platform charges (Plan #4 filter) |
| `manual.yml` | Hand-entered figures (MW rebate, agency rev share, notes) — copy from `inbox/_template/manual.yml` |

Then either:

```bash
# One-shot ingest (run after dropping files in)
python -m ingest ingest inbox/2026-04

# Or run the watcher — auto-picks up changes ~5 seconds after files stop arriving
python -m ingest watch
```

The pipeline parses what it can, lets `manual.yml` override anything, runs
validation (`zaiNet ≈ sum(zaiLines)`) and writes the new month into
`dashboard/src/data.json`. Rebuild the dashboard with
`npm run build --prefix dashboard` to ship the updated site.

### 4. Backfill from existing reports

```bash
python -m ingest all
```

Walks every `YYYY-MM` folder under `inbox/` in chronological order.

## Architecture notes

- **Single source of truth.** `dashboard/src/data.json` holds everything.
  The dashboard reads it at build time. The ingest pipeline writes it.
- **Parsers are best-effort.** PDF / CSV formats vary across exports. Each
  parser extracts what it can; `manual.yml` fills the gaps. The user always
  wins against an automated guess.
- **Idempotent upserts.** Re-ingesting the same month replaces its entry
  rather than duplicating. Safe to re-run after editing `manual.yml`.
- **Public mode toggle.** The dashboard masks invoice numbers, account codes
  and client identifiers by default — safe to screenshot and share. Flip
  the toggle in the header for internal working view.

See `DASHBOARD_INSTRUCTIONS.md` for the full schema, business rules, and
monthly workflow checklist.
