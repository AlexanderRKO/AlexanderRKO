Attribute VB_Name = "GoogleSheetsSync"
' ============================================================
' GoogleSheetsSync.bas  –  Public API
'
' This is the only module your macros and VBA code should call.
' All implementation detail lives in the mod* modules.
'
' QUICK START
' -----------
'   1.  Edit modConfig.bas  – set CLIENT_ID, CLIENT_SECRET, SPREADSHEET_ID
'   2.  Run  Authorize       – complete the one-time Google consent screen
'   3.  Run  SyncAll         – sync every configured sheet
'
' IMPORTING INTO EXCEL
' --------------------
'   VBA Editor > File > Import File, then import every .bas file
'   in the src/ folder.  Requires no external libraries.
' ============================================================
Option Explicit

' ============================================================
' Authorize
' Opens the Google consent screen and persists tokens so you
' only need to run this once per workbook.
' ============================================================
Public Sub Authorize()
    AuthorizeApplication
End Sub

' ============================================================
' SyncAll
' Syncs every sheet/range pair defined in modConfig.GetSheetConfigs()
' ============================================================
Public Sub SyncAll()
    SyncAllSheets
End Sub

' ============================================================
' PushToGoogle
' Pushes all outbound (TO_GOOGLE or TWO_WAY) sheets.
' ============================================================
Public Sub PushToGoogle()
    PushAllToGoogle
End Sub

' ============================================================
' PullFromGoogle
' Pulls all inbound (FROM_GOOGLE or TWO_WAY) sheets.
' ============================================================
Public Sub PullFromGoogle()
    PullAllFromGoogle
End Sub

' ============================================================
' SyncSheet  sheetName
' Syncs only the named sheet using its configured direction.
' ============================================================
Public Sub SyncSheet(localSheetName As String)
    SyncSheetByName localSheetName
End Sub

' ============================================================
' SyncRange
' One-off sync of any Excel range to/from any Google range.
'
'   direction: "TO_GOOGLE" | "FROM_GOOGLE" | "TWO_WAY"
'
' Example:
'   SyncRange "Inventory", "A1:E200", "Inventory", "A1:E200", "TWO_WAY"
' ============================================================
Public Sub SyncRange(localSheet  As String, localRange  As String, _
                     googleSheet As String, googleRange As String, _
                     direction   As String)
    SyncCustomRange localSheet, localRange, googleSheet, googleRange, direction
End Sub

' ============================================================
' StartAutoSync  [intervalMinutes]
' Starts a repeating timer-based sync.  Defaults to the
' interval in modConfig (DEFAULT_SYNC_INTERVAL_MINUTES).
' ============================================================
Public Sub StartAutoSync(Optional intervalMinutes As Integer = 0)
    StartAutoSyncService intervalMinutes
End Sub

' ============================================================
' StopAutoSync
' Cancels the repeating timer.
' ============================================================
Public Sub StopAutoSync()
    StopAutoSyncService
End Sub

' ============================================================
' SyncStatus
' Shows a dialog with the current configuration and sync state.
' ============================================================
Public Sub SyncStatus()
    ShowSyncStatus
End Sub

' ============================================================
' ShowLog  /  ClearLog
' ============================================================
Public Sub ShowLog()
    DisplaySyncLog
End Sub

Public Sub ClearLog()
    EraseSyncLog
End Sub

' ============================================================
' Setup
' Opens the setup/help dialog.
' ============================================================
Public Sub Setup()
    ShowSetupDialog
End Sub
