# Excel ↔ Google Sheets Sync (VBA)

A pure-VBA tool that syncs data between Microsoft Excel and Google Sheets in both directions — no add-ins, no external DLLs, no manual button clicks required.

## Features

| Feature | Description |
|---------|-------------|
| **Two-way sync** | Push Excel data to Google, pull Google data into Excel, or let both sides stay in step simultaneously |
| **Automatic sync** | Timer-based sync via `Application.OnTime` — fires on a configurable interval with no user interaction |
| **Change-triggered sync** | Wire a `Worksheet_Change` event to push edits to Google within seconds (debounced) |
| **Sync specific range** | Every sheet mapping specifies an exact range — sync only the cells you care about |
| **Multiple sheet sync** | Define as many sheet/range pairs as you need in `modConfig.bas`; `SyncAll` handles all of them |
| **Conflict resolution** | Four strategies: `EXCEL_WINS`, `GOOGLE_WINS`, `NEWER_WINS`, `ASK_USER` |
| **Persistent auth** | OAuth 2.0 refresh token is stored once in a hidden sheet; re-authorization is never needed unless revoked |
| **Audit log** | Every sync operation is timestamped in a hidden `_SyncLog` sheet |

---

## File structure

```
excel_google_sheets_sync/
├── src/
│   ├── GoogleSheetsSync.bas   Public API – the only module you call
│   ├── modConfig.bas          Credentials, spreadsheet ID, sheet mappings
│   ├── modOAuth.bas           OAuth 2.0 flow and token management
│   ├── modGoogleAPI.bas       Google Sheets API v4 HTTP calls + JSON parsing
│   ├── modSyncEngine.bas      Core push / pull / two-way sync logic
│   ├── modAutoSync.bas        Timer-based and change-triggered auto sync
│   ├── modMultiSheet.bas      Orchestrates sync across all configured sheets
│   └── modUtils.bas           Logging and setup dialog
├── examples/
│   └── ExampleUsage.bas       Ready-to-run example macros
└── docs/
    └── SETUP.md               Full setup guide
```

---

## Quick start

```
1. Enable Google Sheets API in Google Cloud Console
2. Create OAuth 2.0 Desktop credentials → copy Client ID & Secret
3. Import all src/*.bas files into your workbook via VBA Editor
4. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SPREADSHEET_ID in modConfig.bas
5. Run  Authorize       (one time – opens browser for Google consent)
6. Run  SyncAll         (syncs every sheet defined in GetSheetConfigs)
```

Full step-by-step walkthrough: [docs/SETUP.md](docs/SETUP.md)

---

## API reference

```vba
' --- Authorization ---
Authorize                        ' Run once: OAuth consent + token storage

' --- Sync ---
SyncAll                          ' Sync all sheets from modConfig
PushToGoogle                     ' Push all outbound sheets
PullFromGoogle                   ' Pull all inbound sheets
SyncSheet  "SheetName"           ' Sync one sheet by name
SyncRange  localSheet, localRange, googleSheet, googleRange, direction
'   direction: "TO_GOOGLE" | "FROM_GOOGLE" | "TWO_WAY"

' --- Auto sync (no button clicks) ---
StartAutoSync [intervalMinutes]  ' Default: DEFAULT_SYNC_INTERVAL_MINUTES in modConfig
StopAutoSync

' --- Diagnostics ---
SyncStatus                       ' Configuration summary dialog
ShowLog                          ' Open the hidden log sheet
ClearLog                         ' Wipe log entries
Setup                            ' Help dialog
```

---

## Sync directions

| Direction | Behaviour |
|-----------|-----------|
| `TO_GOOGLE` | Excel range is written to Google; Google data is not read |
| `FROM_GOOGLE` | Google range is read into Excel; Excel data is not written |
| `TWO_WAY` | Both sides are compared; winner is decided by `CONFLICT_STRATEGY` |

---

## Requirements

- Microsoft Excel 2016+ on Windows (uses `MSXML2.XMLHTTP.6.0`)
- A Google account with access to the target spreadsheet
- Google Sheets API enabled in a Google Cloud project
