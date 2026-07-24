# How to Use – Excel ↔ Google Sheets Sync

This guide covers everyday usage of the sync tool. It assumes you have already completed the one-time setup: imported all `src/*.bas` modules into your workbook, filled in your credentials in `modConfig.bas`, and run `Authorize` at least once. If you have not done that yet, start with [docs/SETUP.md](docs/SETUP.md).

---

## Quick reference

| Procedure | What it does |
|-----------|-------------|
| `Authorize` | Open Google consent screen and save tokens (run once) |
| `SyncAll` | Sync every sheet/range pair defined in `modConfig.bas` |
| `PushToGoogle` | Push all outbound (`TO_GOOGLE` / `TWO_WAY`) sheets to Google |
| `PullFromGoogle` | Pull all inbound (`FROM_GOOGLE` / `TWO_WAY`) sheets from Google |
| `SyncSheet "Name"` | Sync one named sheet using its configured direction |
| `SyncRange l, lr, g, gr, dir` | One-off sync of any range (not required to be in config) |
| `StartAutoSync [n]` | Start a repeating timer that syncs every `n` minutes |
| `StopAutoSync` | Cancel the repeating timer |
| `SyncStatus` | Dialog showing all mappings and current timer state |
| `ShowLog` | Open the hidden `_SyncLog` sheet |
| `ClearLog` | Wipe all log entries |
| `Setup` | Help dialog listing all available commands |

All procedures live in `GoogleSheetsSync.bas` and can be called from the VBA Immediate window (`Ctrl+G`), from any macro, or assigned to a button.

---

## 1. Sync all configured sheets

The simplest way to sync everything in one call:

```vba
SyncAll
```

This iterates every row in `GetSheetConfigs()` (inside `modConfig.bas`) and executes the configured direction for each one. Errors on individual rows are logged but do not stop the rest of the sync.

To push only, or pull only:

```vba
PushToGoogle     ' sends all TO_GOOGLE and TWO_WAY sheets to Google
PullFromGoogle   ' fetches all FROM_GOOGLE and TWO_WAY sheets into Excel
```

---

## 2. Sync a specific range

Use `SyncRange` to sync any Excel range to/from any Google range, regardless of whether it appears in the config. The five parameters are:

```
SyncRange  localSheet,  localRange,  googleSheet,  googleRange,  direction
```

**Direction values:** `"TO_GOOGLE"` · `"FROM_GOOGLE"` · `"TWO_WAY"`

Examples:

```vba
' Push the Sales sheet to Google (Excel overwrites Google)
SyncRange "Sales", "A1:F500", "Sales", "A1:F500", "TO_GOOGLE"

' Pull a price list from Google into Excel
SyncRange "Prices", "A1:C200", "MasterPrices", "A1:C200", "FROM_GOOGLE"

' Keep a dashboard in sync with both sides able to write
SyncRange "Dashboard", "A1:Z50", "Dashboard", "A1:Z50", "TWO_WAY"
```

To sync a single sheet that is already in the config (using its configured direction):

```vba
SyncSheet "Sales"
```

---

## 3. Automatic sync (no button clicks)

### Option A – Timer-based sync

Start a repeating sync that fires automatically every N minutes:

```vba
StartAutoSync 5    ' sync every 5 minutes
StopAutoSync       ' cancel the timer
```

Omitting the interval uses the default from `modConfig.bas` (`DEFAULT_SYNC_INTERVAL_MINUTES`).

**Note:** `Application.OnTime` does not persist across Excel sessions. To restart the timer automatically when the workbook is opened, add the following to the `ThisWorkbook` module (not a standard module):

```vba
Private Sub Workbook_Open()
    StartAutoSync 5
End Sub
```

Open the VBA Editor (`Alt+F11`), expand your workbook in the Project Explorer, and double-click **ThisWorkbook** to find that module.

### Option B – Sync on every cell edit (Worksheet_Change)

For near-real-time push, wire a `Worksheet_Change` event on the sheet you want to watch. This triggers a sync within 5 seconds of the last edit (debounced — rapid keystrokes are batched into a single sync call).

**Where to paste this:** in the VBA Editor, expand your workbook in the Project Explorer, double-click the specific sheet (e.g., `Sheet1`), and paste into that sheet module — not into a standard module.

```vba
Private Sub Worksheet_Change(ByVal Target As Range)
    ' Only sync when the edit falls inside the data range
    If Not Intersect(Target, Me.Range("A1:F100")) Is Nothing Then
        OnSheetChange Me.Name, Target.Address
    End If
End Sub
```

Change `"A1:F100"` to match your actual data range. This calls the debounce handler in `modAutoSync.bas`, which queues a `SyncAll` call 5 seconds after the last edit.

---

## 4. Working with multiple sheets

Open `modConfig.bas` in the VBA Editor and edit the `GetSheetConfigs()` function. Each row of the returned array defines one sync mapping.

**Column layout:**

| Index | Meaning | Example |
|-------|---------|---------|
| 0 | Local Excel sheet name | `"Sales"` |
| 1 | Local range address | `"A1:F500"` |
| 2 | Google Sheet tab name | `"Sales"` |
| 3 | Google range address | `"A1:F500"` |
| 4 | Direction | `"TWO_WAY"` |

**To add more sheet mappings**, first resize the array declaration to match the number of rows you need, then fill in each row:

```vba
Public Function GetSheetConfigs() As Variant
    Dim configs(0 To 3, 0 To 4) As String   ' 4 rows (indices 0-3)

    ' Row 0: main data – fully bidirectional
    configs(0, 0) = "Sales"
    configs(0, 1) = "A1:F500"
    configs(0, 2) = "Sales"
    configs(0, 3) = "A1:F500"
    configs(0, 4) = "TWO_WAY"

    ' Row 1: summary – push Excel to Google only
    configs(1, 0) = "Summary"
    configs(1, 1) = "A1:D20"
    configs(1, 2) = "Summary"
    configs(1, 3) = "A1:D20"
    configs(1, 4) = "TO_GOOGLE"

    ' Row 2: price list – pull from Google only
    configs(2, 0) = "Prices"
    configs(2, 1) = "A1:C200"
    configs(2, 2) = "MasterPrices"
    configs(2, 3) = "A1:C200"
    configs(2, 4) = "FROM_GOOGLE"

    ' Row 3: dashboard – bidirectional
    configs(3, 0) = "Dashboard"
    configs(3, 1) = "A1:Z50"
    configs(3, 2) = "Dashboard"
    configs(3, 3) = "A1:Z50"
    configs(3, 4) = "TWO_WAY"

    GetSheetConfigs = configs
End Function
```

**Things to watch:**
- The array size `(0 To N-1, 0 To 4)` must exactly match the number of rows you define.
- Google tab names are **case-sensitive**. `"Sales"` and `"sales"` are different tabs.
- If a Google tab does not exist, the tool creates it automatically on the first push.
- Avoid overlapping ranges across multiple rows — syncing the same cells twice in one `SyncAll` call can cause the second write to overwrite the first.

---

## 5. Conflict resolution

When using `TWO_WAY`, both sides may have changed since the last sync. The `CONFLICT_STRATEGY` constant in `modConfig.bas` controls which side wins.

```vba
Public Const CONFLICT_STRATEGY As String = "EXCEL_WINS"
```

| Strategy | Behaviour | Best for |
|----------|-----------|----------|
| `EXCEL_WINS` | Excel always overwrites Google | You are the sole owner of the data in Excel |
| `GOOGLE_WINS` | Google always overwrites Excel | Others edit the Google Sheet; you pull authoritative data in |
| `NEWER_WINS` | Compares last-sync timestamps; the more recently synced side wins | You work solo, alternating between Excel and Google |
| `ASK_USER` | A dialog asks you each time a two-way sync runs | Shared workbooks where you want explicit per-sync control |

Change the constant, save `modConfig.bas`, and the new strategy applies on the next sync call.

---

## 6. Diagnostics

### View sync status

```vba
SyncStatus
```

Opens a dialog showing every configured sheet mapping and whether the auto-sync timer is currently running.

### View the sync log

```vba
ShowLog
```

Makes the hidden `_SyncLog` sheet visible and activates it. Each row records a timestamp and a message from the last sync operations. The log is automatically trimmed to 1 000 rows.

Re-hide the sheet when done by right-clicking its tab and choosing **Hide**, or it will stay visible until the workbook is closed.

```vba
ClearLog    ' wipe all log entries (header row is preserved)
```

### Check timer state from the Immediate window

Press `Ctrl+G` to open the Immediate window in the VBA Editor, then type:

```vba
? IsAutoSyncRunning()
```

Returns `True` if the timer is active, `False` otherwise.

### Setup help dialog

```vba
Setup
```

Shows a dialog with your current configuration values and a list of all available commands.

---

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Authorization cancelled` dialog | User dismissed the auth code InputBox | Run `Authorize` again and paste the code from the browser |
| HTTP 401 after working previously | Refresh token revoked (e.g., password change, security review) | Run `Authorize` again |
| HTTP 403 Forbidden | Google Sheets API not enabled, or `SPREADSHEET_ID` is wrong | Enable the API in Google Cloud Console; double-check the spreadsheet ID |
| `Subscript out of range` on a sheet name | The Excel sheet named in config does not exist in the workbook | Create the sheet in Excel or correct the name in `GetSheetConfigs()` |
| Data appears in the wrong Google tab | Tab name mismatch (case-sensitive) | Verify the Google tab name matches `configs(i, 2)` exactly |
| Auto-sync stops after reopening Excel | `Application.OnTime` does not persist across sessions | Add `StartAutoSync n` to the `Workbook_Open` event in `ThisWorkbook` |
| Sync pushes empty rows below your data | The configured range is larger than the actual data | Shrink the range in `GetSheetConfigs()` to match the data footprint |
| `Compile error: Ambiguous name detected` | A procedure name exists in two modules | Ensure you have imported all `.bas` files cleanly; delete any duplicate module |
| Slow sync on large data | One API call per range; large payloads take time | Reduce range size, or run sync less frequently via `StartAutoSync` |

---

## 8. Tips and best practices

- **Test on a small range first.** Before enabling auto-sync on production data, run `SyncRange "Sheet1", "A1:C5", "Sheet1", "A1:C5", "TWO_WAY"` manually and check the result in both directions.
- **Start with `EXCEL_WINS`.** Switch to a more nuanced strategy only once you are comfortable with the sync timing.
- **Check the log after every first sync** (`ShowLog`) to confirm there are no silent errors.
- **Save as `.xlsm`.** Regular `.xlsx` files strip all VBA on save. The workbook must be saved as a macro-enabled workbook.
- **Do not rename or delete `_SyncConfig` or `_SyncLog`.** These hidden sheets store your refresh token and audit log. Deleting `_SyncConfig` forces re-authorization.
- **Revoke access cleanly.** To disconnect the tool from Google, run `ClearTokens` in the Immediate window, then revoke the app at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).
