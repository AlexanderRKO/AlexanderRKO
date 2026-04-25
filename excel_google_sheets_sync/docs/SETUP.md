# Setup Guide – Excel ↔ Google Sheets Sync

## Prerequisites

| Requirement | Notes |
|------------|-------|
| Microsoft Excel 2016 or later | Windows only (MSXML2 HTTP stack) |
| Google Account | The account that owns the target spreadsheet |
| Google Cloud project | Free tier is sufficient |

---

## Step 1 – Enable the Google Sheets API

1. Go to [console.cloud.google.com](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Navigate to **APIs & Services → Library**.
4. Search for **Google Sheets API** and click **Enable**.

---

## Step 2 – Create OAuth 2.0 credentials

1. Go to **APIs & Services → Credentials**.
2. Click **+ Create Credentials → OAuth client ID**.
3. Choose **Desktop app** as the application type.
4. Give it a name (e.g. "Excel Sync") and click **Create**.
5. Copy the **Client ID** and **Client Secret** – you will need them in Step 4.

> If prompted, configure the OAuth consent screen first.  
> Add your Google account as a **Test user** while the app is in testing mode.

---

## Step 3 – Find your Spreadsheet ID

Open the target Google Sheet in your browser.  
The URL looks like:

```
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        This is your SPREADSHEET_ID
```

---

## Step 4 – Import the VBA modules into Excel

1. Open your Excel workbook.
2. Press **Alt + F11** to open the VBA editor.
3. In the **Project Explorer**, right-click your workbook and choose **Import File**.
4. Import **every `.bas` file** from the `src/` folder in this repo (order does not matter):

   ```
   modConfig.bas
   modOAuth.bas
   modGoogleAPI.bas
   modSyncEngine.bas
   modAutoSync.bas
   modMultiSheet.bas
   modUtils.bas
   GoogleSheetsSync.bas
   ```

5. Optionally import `examples/ExampleUsage.bas` for reference.

---

## Step 5 – Configure the tool

Open `modConfig.bas` in the VBA editor and replace the placeholder values:

```vba
Public Const GOOGLE_CLIENT_ID     As String = "123456789.apps.googleusercontent.com"
Public Const GOOGLE_CLIENT_SECRET As String = "GOCSPX-abc123..."
Public Const SPREADSHEET_ID       As String = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
```

Then edit `GetSheetConfigs()` to describe your sheet/range mappings:

```vba
' Column index  Meaning
'   0           Local Excel sheet name
'   1           Local range address   e.g. "A1:Z100"
'   2           Google Sheet tab name
'   3           Google range address  e.g. "A1:Z100"
'   4           Direction: TO_GOOGLE | FROM_GOOGLE | TWO_WAY

configs(0, 0) = "Sales"
configs(0, 1) = "A1:F500"
configs(0, 2) = "Sales"
configs(0, 3) = "A1:F500"
configs(0, 4) = "TWO_WAY"
```

---

## Step 6 – Authorize (one time only)

In the VBA editor, open the **Immediate window** (Ctrl + G) and run:

```vba
Authorize
```

Your browser will open the Google consent screen.  
After granting permission, copy the authorization code and paste it into the Excel dialog.  
The refresh token is saved in a hidden sheet and reused automatically from then on.

---

## Usage

### Manual sync

```vba
SyncAll               ' Sync every configured sheet
PushToGoogle          ' Push all outbound sheets
PullFromGoogle        ' Pull all inbound sheets
SyncSheet "Sales"     ' Sync only the "Sales" sheet
```

### Custom range (not in config)

```vba
SyncRange "Sheet1", "A1:D20", "Sheet1", "A1:D20", "TWO_WAY"
SyncRange "Report", "A1:Z50", "Report", "A1:Z50", "TO_GOOGLE"
SyncRange "Imports", "A1:C100", "SourceData", "A1:C100", "FROM_GOOGLE"
```

### Automatic sync (no button clicks)

```vba
StartAutoSync 5       ' Sync every 5 minutes
StopAutoSync          ' Stop the timer
```

### Near-real-time sync on cell edits

Add this to the sheet module (not a standard module):

```vba
Private Sub Worksheet_Change(ByVal Target As Range)
    If Not Intersect(Target, Me.Range("A1:F100")) Is Nothing Then
        OnSheetChange Me.Name, Target.Address
    End If
End Sub
```

Changes are debounced: the sync fires 5 seconds after the last edit.

---

## Conflict resolution

Set `CONFLICT_STRATEGY` in `modConfig.bas`:

| Value | Behaviour |
|-------|-----------|
| `EXCEL_WINS` | Excel always overwrites Google (default) |
| `GOOGLE_WINS` | Google always overwrites Excel |
| `NEWER_WINS` | The side synced most recently wins |
| `ASK_USER` | A dialog asks you each time |

---

## Diagnostics

```vba
SyncStatus    ' Show config dialog
ShowLog       ' Open the sync log sheet
ClearLog      ' Wipe log entries
Setup         ' Show setup help
```

---

## Security notes

- Credentials are stored in the **VBA source code** (`modConfig.bas`).  
  Do **not** share the workbook with untrusted parties.
- The refresh token is stored in a `xlSheetVeryHidden` sheet named `_SyncConfig`.  
  It is not visible from the sheet tab bar and cannot be unhidden via the UI.
- If you need to revoke access, run `ClearTokens` in the Immediate window,  
  then revoke the app at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).
