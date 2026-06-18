# 01 — Chart of accounts (RAW)

## MYOB AccountRight (desktop / hybrid)

`Accounts ▸ Accounts List ▸ Export` produces a clean CSV. Save it
here as `chart_of_accounts_<YYYYMMDD>.csv`.

## MYOB Business (cloud-only) — there is no CSV export

This is the snag every MYOB Business migration hits. The
**Chart of accounts** screen has no Export button. The only way out
is to copy from the screen and paste — and the clipboard pours every
source cell into Excel column A, one cell per line, with group
headings ("Assets", "Liabilities", "Equity"…) sprinkled in between.

### Recommended path — use the dashboard

1. Open the dashboard (double-click the launcher in the toolkit root).
2. Navigate to **Paste from MYOB Business** in the sidebar.
3. In MYOB Business: open **Accounting ▸ Chart of accounts**, click
   into the table, `Ctrl+A` then `Ctrl+C` (macOS: `⌘+A` / `⌘+C`).
4. Paste into the dashboard's text area, click **Parse**.
5. The parser detects the column stride from the account-code pattern,
   reshapes the flat list back into a table, strips group headings,
   and tidies currency formatting in any Balance column.
6. Fix any misparsed cells in the editor; rename columns if needed.
7. Click **Save to project** → `01_chart_of_accounts/` →
   `chart_of_accounts_pasted.csv`.
8. Tick the matching row on the **Stage 01 — Exports** page.

### Fallback — Python CLI

If you'd rather not use the browser, the same parser is reachable
as a library:

```python
from _paste_parser import parse_pasted_table
import pathlib

text = pathlib.Path("/tmp/pasted.txt").read_text()
df, meta = parse_pasted_table(text)
print(meta)            # {"strategy": "single_column_reshape", "stride": 5, ...}
df.to_csv("chart_of_accounts_pasted.csv", index=False)
```

The parser is tolerant: it handles tab-separated, multi-space-separated,
and the MYOB Business single-column case with one entry point.

## Expected columns (after parsing)

| MYOB column | Typical content |
| ----------- | --------------- |
| Account Number | `1-1100`, `2-1200`, …  |
| Account Name | free text |
| Type | `Bank`, `Accounts Receivable`, `Expense`, … |
| Tax Code | `GST`, `N-T`, `FRE`, … |
| Balance | currency, may be negative in parentheses |

These get re-mapped to the Xero CoA template in Stage 02
(`02_cleansed_for_xero/01_chart_of_accounts/`).
