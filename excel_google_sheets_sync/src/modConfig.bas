Attribute VB_Name = "modConfig"
' ============================================================
' modConfig.bas
' Central configuration for Excel <-> Google Sheets Sync
'
' REQUIRED SETUP:
'   1. Replace GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET with
'      values from Google Cloud Console > Credentials
'   2. Replace SPREADSHEET_ID with the ID from the Google Sheet URL:
'      https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit
'   3. Edit GetSheetConfigs() to define which sheets/ranges to sync
' ============================================================
Option Explicit

' --------------- Google OAuth Credentials -------------------
' Create a Desktop OAuth 2.0 client at:
'   console.cloud.google.com > APIs & Services > Credentials
Public Const GOOGLE_CLIENT_ID     As String = "YOUR_CLIENT_ID_HERE"
Public Const GOOGLE_CLIENT_SECRET As String = "YOUR_CLIENT_SECRET_HERE"

' --------------- Target Spreadsheet -------------------------
Public Const SPREADSHEET_ID As String = "YOUR_SPREADSHEET_ID_HERE"

' --------------- Internal Storage ---------------------------
' A hidden sheet used to persist tokens and sync timestamps.
' Do NOT rename or delete this sheet manually.
Public Const TOKEN_STORAGE_SHEET As String = "_SyncConfig"
Public Const TOKEN_CELL          As String = "A1"   ' refresh token

' --------------- Sync Behaviour -----------------------------
' How often (minutes) the auto-sync timer fires
Public Const DEFAULT_SYNC_INTERVAL_MINUTES As Integer = 5

' Conflict resolution when both sides may have changed:
'   EXCEL_WINS  - Excel always overwrites Google
'   GOOGLE_WINS - Google always overwrites Excel
'   NEWER_WINS  - The side synced most recently wins
'   ASK_USER    - Prompt the user each time
Public Const CONFLICT_STRATEGY As String = "EXCEL_WINS"

' --------------- Logging ------------------------------------
Public Const LOG_ENABLED As Boolean = True
Public Const LOG_SHEET   As String = "_SyncLog"

' ============================================================
' GetSheetConfigs
' Returns a 2-D array describing every sheet/range pair to sync.
'
' Column index  Meaning
'   0           Local Excel sheet name
'   1           Local range address  (e.g. "A1:Z100")
'   2           Google Sheet tab name
'   3           Google range address (e.g. "A1:Z100")
'   4           Direction: TO_GOOGLE | FROM_GOOGLE | TWO_WAY
' ============================================================
Public Function GetSheetConfigs() As Variant
    ' Resize the array to hold as many rows as you need.
    Dim configs(0 To 2, 0 To 4) As String

    ' --- Entry 0: main data sheet, fully bidirectional ---
    configs(0, 0) = "Sheet1"
    configs(0, 1) = "A1:Z100"
    configs(0, 2) = "Sheet1"
    configs(0, 3) = "A1:Z100"
    configs(0, 4) = "TWO_WAY"

    ' --- Entry 1: summary sheet, push Excel -> Google only ---
    configs(1, 0) = "Summary"
    configs(1, 1) = "A1:F20"
    configs(1, 2) = "Summary"
    configs(1, 3) = "A1:F20"
    configs(1, 4) = "TO_GOOGLE"

    ' --- Entry 2: import sheet, pull Google -> Excel only ---
    configs(2, 0) = "Imports"
    configs(2, 1) = "A1:D50"
    configs(2, 2) = "ExternalData"
    configs(2, 3) = "A1:D50"
    configs(2, 4) = "FROM_GOOGLE"

    GetSheetConfigs = configs
End Function
