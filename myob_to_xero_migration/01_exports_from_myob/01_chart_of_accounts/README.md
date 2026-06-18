# 01 — Chart of accounts (RAW)

> ⚠️ **DO NOT paste through Excel first.** Excel auto-converts MYOB
> codes like `1-9000` into the date `January 9000` and silently writes
> the date serial number into the cell. In real-world testing this
> corrupted **157 out of 340** account codes with no warning. Paste
> from MYOB Business **directly into the dashboard textarea** instead
> — the dashboard treats the clipboard as text, so no auto-conversion
> happens.

## MYOB AccountRight (desktop / hybrid)

`Accounts ▸ Accounts List ▸ Export` produces a clean CSV. Save it
here as `chart_of_accounts_<YYYYMMDD>.csv`. No paste workaround needed.

## MYOB Business (cloud-only) — there is no CSV export

This is the snag every MYOB Business migration hits. The
**Chart of accounts** screen has no Export button. The only way out
is to copy from the screen and paste. The clipboard format is
unusual: every source cell becomes its own row, with "Select row N"
markers between each record and group headings ("Assets",
"Liabilities", "Equity"…) sprinkled in.

### ✅ Recommended path — paste directly into the dashboard

This is the only path that preserves all account codes intact.

1. Open the dashboard (double-click the launcher in the toolkit root).
2. Navigate to **Paste from MYOB Business** in the sidebar.
3. In MYOB Business: open **Accounting ▸ Chart of accounts**, click
   into the table, `Ctrl+A` then `Ctrl+C` (macOS: `⌘+A` / `⌘+C`).
4. Paste **directly** into the dashboard's text area — **not** into
   Excel first. Click **Parse**.
5. The parser detects the MYOB Business "Select row N" format,
   aligns each row to the 7-column schema, drops group-heading
   rows, and tidies currency formatting in the Balance column.
6. Fix any misparsed cells in the editor; rename columns if needed.
7. Click **Save to project** → `01_chart_of_accounts/` →
   `chart_of_accounts_pasted.csv`.
8. Tick the matching row on the **Stage 01 — Exports** page.

### ⚠ Excel fallback (only if the recommended path is blocked)

If you've already pasted into Excel and need to recover what you can:

1. Select column A in Excel and copy it (`Ctrl+C`).
2. Paste into the dashboard textarea and click **Parse**.
3. The parser handles the same content equally well. **However**, any
   codes Excel already mangled into dates (e.g. `1-9000` →
   `1950-01-01`) are gone — the dashboard surfaces them in a red
   error banner with the count and keeps them in the **Code**
   column so you can fix them by hand. You will need to look up
   the originals in MYOB Business one by one. **This is why the
   recommended path is to bypass Excel.**

### Fallback — Python CLI

If you'd rather not use the browser, the same parser is reachable
as a library:

```python
from _paste_parser import parse_pasted_table
import pathlib

text = pathlib.Path("/tmp/pasted.txt").read_text()
df, meta = parse_pasted_table(text)
print(meta)
# {"strategy": "myob_business", "rows": 340, "date_corrupted_codes": 0, ...}
df.to_csv("chart_of_accounts_pasted.csv", index=False)
```

The `date_corrupted_codes` field in `meta` tells you whether Excel
got involved at any point in the chain.

## Expected columns (after parsing)

| MYOB column | Typical content |
| ----------- | --------------- |
| Code | `1-1100`, `2-1200`, …  |
| Name | free text |
| Type | `Bank`, `Other current asset`, `Expense`, … |
| Tax code | `GST`, `N-T`, `FRE`, … (blank on grouping rows) |
| Linked | the literal `Linked` for bank/clearing accounts; blank otherwise |
| Level | `Level 1` / `Level 2` / `Level 3` / `Level 4` |
| Current balance ($) | numeric, may be negative |

These get re-mapped to the Xero CoA template in Stage 02
(`02_cleansed_for_xero/01_chart_of_accounts/`). Note that MYOB
Business's `Level` and `Linked` columns have no Xero equivalents —
drop them during cleansing.
