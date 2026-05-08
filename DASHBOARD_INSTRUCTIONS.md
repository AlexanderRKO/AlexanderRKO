# Managed Revenue & Cost Intelligence — Dashboard Instructions

## Companion file for the React dashboard
**Account:** MAN2077 · Managed Platforms · LMS Advisory Pty Ltd
**Prepared by:** LMS Advisory — Certified Practising Accountants, Registered Tax Agent, ABN 65 302 567 149
**Stack:** Vite + React + Recharts dashboard, Python ingest pipeline

---

## 1. What This Dashboard Is

A React dashboard tracking Managed Platforms' monthly billing economics.
Originally built as a single Claude artifact (`zai-index.jsx`), now ported
to a Vite project with a folder-watching ingest pipeline so monthly reports
can be drag-dropped into `inbox/YYYY-MM/`.

**It covers:**
- Revenue waterfall (Managed Core, Managed Pro, Transaction, Tradie, SMS, Implementation)
- Zai supplier fee breakdown (14 line items per month)
- Marshall White (MW) reimbursement reconciliation
- Agency Rev Share tracking
- Per-unit economics (per PUM, per lease, per agency)
- Contribution margin and COGS analysis
- Agency/PUM growth tracking

**All figures are ex GST throughout.** No exceptions.

---

## 2. File Structure

```
.
├── dashboard/                  # Vite + React app
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx             # Dashboard component (renders all 8 tabs)
│       ├── data.json           # Single source of truth — MONTHS + MW_OFFICES
│       └── styles.css
├── ingest/                     # Python pipeline
│   ├── __main__.py             # CLI: `python -m ingest <cmd>`
│   ├── watcher.py              # watchdog daemon
│   ├── ingest.py               # one-shot orchestration
│   ├── month_builder.py        # combines parser outputs + manual.yml
│   ├── data_writer.py          # reads/writes data.json idempotently
│   └── parsers/
│       ├── zai_invoice.py      # Zai tax invoice PDF
│       ├── platform_revenue.py # Platform revenue CSV
│       ├── agency_performance.py
│       ├── mw_charges.py
│       └── manual.py           # YAML override loader
├── inbox/                      # Drop folder for monthly reports
│   ├── _template/manual.yml    # Copy into each new month
│   └── _archive/               # Successfully-processed folders move here
└── tests/
```

---

## 3. The data.json Schema

Each entry in `months[]` follows this exact structure. All amounts ex GST:

```json
{
  "month":            "Apr-26",
  "label":            "April 2026",
  "short":            "Apr",
  "invoiceNo":        "4420",
  "dueDate":          "10 May 2026",
  "smsRevenue":       2250.00,
  "implFees":         6609.09,
  "mwRebate":         11077.95,
  "agencyRevShare":   2270.03,
  "note":             "...",
  "agencies":         293,
  "activeAgencies":   276,
  "inactiveAgencies": 17,
  "totalLeases":      22278,
  "totalProperties":  24953,
  "vaActive":         15932,
  "vaSetup":          2010,
  "zaiNet":           51286.33,
  "zaiGst":           5128.63,
  "zaiTotal":         56414.96,
  "revenue": {
    "baseSub":     { "billed": 0, "completed": 0, "debtors": 0 },
    "managedPlus": { "billed": 0, "completed": 0, "debtors": 0 },
    "transaction": { "billed": 0, "completed": 0, "debtors": 0 },
    "tradie":      { "billed": 0, "completed": 0, "debtors": 0 }
  },
  "zaiLines": {
    "payinBpay": 0, "payinRealtime": 0,
    "payoutBpay": 0, "payoutDirect": 0, "payoutEntry": 0, "payoutRealtime": 0,
    "cardVisa": 0, "cardMaster": 0, "cardDebit": 0, "cardAmex": 0,
    "vaActive": 0, "vaSetup": 0,
    "chargebacks": 0, "disputes": 0, "manualMatch": 0
  }
}
```

### Critical: zaiNet must equal sum of all zaiLines

The ingest pipeline validates this on every parse. Rounding discrepancies of
$0.01–$0.02 are accepted; anything larger blocks the write and emits an
error. To fix, edit `manual.yml` for that month or add the gap to
`payoutRealtime` (the largest line).

---

## 4. mwOffices Schema

Keyed by month string (must match the `month` field exactly):

```json
{
  "Apr-26": {
    "invoicedTotal":  8140.94,
    "dashboardTotal": 11077.95,
    "mwInvoiceNo":    "#796",
    "mwPaid":         11077.95,
    "note":           "...",
    "offices": [
      { "office": "Armadale", "invoiceNo": null, "properties": 978, "jobFeesExGst": 2090.81 }
    ]
  }
}
```

### invoicedTotal vs mwPaid
- `invoicedTotal` = what the platform charged MW (sum of office platform invoices)
- `mwPaid` = what MW invoiced back to Managed (their consolidated reimbursement)
- The difference is the **reconciliation gap** shown in the cumulative balance table
- Positive gap = MW paid more than platform charged (MW net ahead / Managed has overpaid)
- Negative gap = MW paid less than platform charged (MW owes Managed)

---

## 5. Computed Fields (auto-derived in App.jsx)

| Field | Formula |
|---|---|
| `recurringBilled` | sum of all 4 revenue lines billed |
| `totalBilled` | recurringBilled + implFees + smsRevenue |
| `totalDebtors` | sum of all 4 revenue lines debtors |
| `netRevenue` | recurringBilled − zaiNet |
| `totalCOGS` | zaiNet + mwRebate + agencyRevShare |
| `contribMargin` | recurringBilled − totalCOGS |
| `contribMarginPct` | contribMargin / recurringBilled × 100 |
| `tradieContrib` | tradie.billed − mwRebate − agencyRevShare |
| `zaiPct` | zaiNet / recurringBilled × 100 |

---

## 6. Revenue Naming Convention

| Platform Report Label | data.json field | Display Name |
|---|---|---|
| Base Subscription Revenue | `baseSub` | Managed Core |
| Managed+ Revenue | `managedPlus` | Managed Pro |
| Transaction Cost Revenue | `transaction` | Transaction Revenue |
| Tradie Job Revenue | `tradie` | Tradie Job Revenue |
| SMS Revenue | `smsRevenue` | SMS Revenue |
| Implementation Fees | `implFees` | Implementation Fees |

---

## 7. Monthly Update — Step by Step

### Files to collect (on the 10th of the following month)

| # | File | Source |
|---|---|---|
| 1 | Zai Tax Invoice PDF | Zai billing portal |
| 2 | Platform Revenue CSV | Managed admin portal |
| 3 | Agency Performance CSV | Admin → Reports → Agency Monthly Performance |
| 4 | MW Platform Charges CSV | Admin → Platform Charges → filter Plan #4 + date range |
| 5 | MW Reimbursement Invoice | kate.muller@marshallwhite.com.au |
| 6 | Agency Rev Share figure | Managed finance team |

### MW Platform Charges URL pattern

```
https://[domain]/admin/platform_charges
  ?q[calculated_at_gteq_datetime]=2026-[MM]-01
  &q[calculated_at_lteq_datetime]=2026-[MM]-[LAST_DAY]
  &q[plan_id_equals]=4
  &commit=Filter&order=id_desc
```

### Update workflow

1. Create folder `inbox/2026-MM/` (where MM is the period month).
2. Drop the Zai PDF, Platform CSV, Agency CSV, MW Charges CSV in.
3. Copy `inbox/_template/manual.yml` into that folder.
4. Fill in `mwRebate`, `agencyRevShare`, `_mw.mwInvoiceNo`, `_mw.mwPaid`,
   and any notes in `manual.yml`.
5. Run `python -m ingest ingest inbox/2026-MM` (or the watcher will pick
   it up automatically if running).
6. The pipeline validates `zaiNet ≈ sum(zaiLines)` and writes
   `dashboard/src/data.json`.
7. `npm run build --prefix dashboard` to rebuild the static site.

### Agency CSV warning

The Agency Performance CSV is a **live query**, not a locked snapshot.
Figures can change after month end as agents archive/unarchive properties.
Re-pulling may return different numbers — record the pull date in
`manual.yml` `note:`.

---

## 8. MW Reconciliation — How It Works

**The flow:**
1. Managed charges each MW office individually via platform invoices.
2. MW consolidates all office charges and sends ONE reimbursement invoice to Managed.
3. Managed pays MW.

**The reconciliation table** in the MW Deep Dive tab shows:
- Platform invoiced total per period (from individual office invoices)
- MW invoice amount (their consolidated reimbursement claim)
- Period variance and running cumulative balance

### Known reconciliation issues (as imported)

| Period | Status |
|---|---|
| Dec-25 | Short $1,005.99 after #786 + #790 — unresolved |
| Mar-26 | MW undercharged by $1,411.25 (Inv #794) |
| Apr-26 | MW overcharged by $2,937.01 (Inv #796) — likely Mar catch-up + ~$1,526 unexplained |

---

## 9. Dashboard Tabs

| Tab | What It Shows |
|---|---|
| Summary | KPI tiles for the most recent month + month-on-month snapshot |
| Month on Month | Side-by-side table of all revenue and cost lines across all months |
| Monthly Growth | Drill-down on a selected month vs prior month |
| Per Unit Charts | Revenue, Zai cost and net per PUM / per lease / per agency |
| Trends | Line and bar charts for key metrics across all months |
| Zai Deep Dive | All 14 Zai fee lines compared month-on-month |
| MW Deep Dive | Marshall White office breakdown + reconciliation table |
| Registry | Full data table — all months, all fields |

**Public Mode** (default ON): masks invoice numbers, account codes, and
client identifiers. Safe to share. Toggle off for internal working view.

---

## 10. Key Business Rules

- Revenue = **billed** amounts, not completed. Completed and debtors are
  captured but not used as primary metrics.
- Contribution Margin is calculated from **recurring revenue only** (excludes
  implFees and smsRevenue).
- COGS = Zai Net + MW Rebate + Agency Rev Share.
- Per-unit metrics use `recurringBilled` as numerator.
- Jul/Aug/Sep-25 are flagged with a VA counting error — Oct-25 is the clean baseline.
- All figures ex GST — GST is never included in any calculation.

---

*LMS Advisory Pty Ltd · Certified Practising Accountants · Registered Tax Agent · ABN 65 302 567 149*
