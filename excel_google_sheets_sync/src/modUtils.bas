Attribute VB_Name = "modUtils"
' ============================================================
' modUtils.bas
' Logging, diagnostics, and the setup dialog.
' ============================================================
Option Explicit

' ============================================================
' LogMessage
' Writes a timestamped entry to the Immediate window and to
' the hidden log sheet.  Automatically trims the log to 1000
' rows to prevent unbounded growth.
' ============================================================
Public Sub LogMessage(msg As String)
    Dim entry As String
    entry = "[" & Format(Now(), "YYYY-MM-DD HH:MM:SS") & "] " & msg
    Debug.Print entry

    If Not LOG_ENABLED Then Exit Sub

    Dim ws As Worksheet
    Set ws = GetOrCreateHiddenSheet(LOG_SHEET)

    ' Ensure header row
    If ws.Cells(1, 1).Value = "" Then
        ws.Cells(1, 1).Value = "Timestamp"
        ws.Cells(1, 2).Value = "Message"
        ws.Rows(1).Font.Bold = True
    End If

    Dim nextRow As Long
    nextRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row + 1

    ' Keep log bounded
    If nextRow > 1001 Then
        ws.Rows("2:101").Delete Shift:=xlShiftUp
        nextRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row + 1
    End If

    ws.Cells(nextRow, 1).Value = Now()
    ws.Cells(nextRow, 2).Value = msg
End Sub

' ============================================================
' ShowLog  /  ClearLog
' ============================================================
Public Sub DisplaySyncLog()
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(LOG_SHEET)
    On Error GoTo 0

    If ws Is Nothing Then
        MsgBox "No log entries yet.", vbInformation
        Exit Sub
    End If

    ws.Visible = xlSheetVisible
    ws.Activate
    ws.Columns("A:B").AutoFit
End Sub

Public Sub EraseSyncLog()
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(LOG_SHEET)
    On Error GoTo 0

    If Not ws Is Nothing Then
        Dim lastRow As Long
        lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
        If lastRow > 1 Then ws.Rows("2:" & lastRow).Delete
        LogMessage "Log cleared."
    End If
End Sub

' ============================================================
' ShowSetupDialog
' ============================================================
Public Sub ShowSetupDialog()
    Dim clientOK As String
    clientOK = IIf(GOOGLE_CLIENT_ID = "YOUR_CLIENT_ID_HERE", _
                   "[NOT SET]", Left(GOOGLE_CLIENT_ID, 16) & "...")

    Dim secretOK As String
    secretOK = IIf(GOOGLE_CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE", _
                   "[NOT SET]", "***")

    Dim sheetOK As String
    sheetOK = IIf(SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE", _
                  "[NOT SET]", Left(SPREADSHEET_ID, 20) & "...")

    Dim msg As String
    msg = "Excel <-> Google Sheets Sync" & vbNewLine & vbNewLine

    msg = msg & "Configuration" & vbNewLine
    msg = msg & "  Client ID     : " & clientOK  & vbNewLine
    msg = msg & "  Client Secret : " & secretOK  & vbNewLine
    msg = msg & "  Spreadsheet ID: " & sheetOK   & vbNewLine & vbNewLine

    msg = msg & "Quick-start" & vbNewLine
    msg = msg & "  1. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET in modConfig.bas" & vbNewLine
    msg = msg & "  2. Set SPREADSHEET_ID in modConfig.bas"                         & vbNewLine
    msg = msg & "  3. Run  Authorize()  once to grant access"                       & vbNewLine
    msg = msg & "  4. Run  SyncAll()    to sync all configured sheets"              & vbNewLine & vbNewLine

    msg = msg & "Available procedures" & vbNewLine
    msg = msg & "  Authorize          Re-run Google OAuth flow"          & vbNewLine
    msg = msg & "  SyncAll            Sync every configured sheet"       & vbNewLine
    msg = msg & "  PushToGoogle       Push all outbound sheets"          & vbNewLine
    msg = msg & "  PullFromGoogle     Pull all inbound sheets"           & vbNewLine
    msg = msg & "  SyncRange ...      One-off custom-range sync"         & vbNewLine
    msg = msg & "  StartAutoSync [n]  Start timer-based sync (n min)"   & vbNewLine
    msg = msg & "  StopAutoSync       Cancel the timer"                  & vbNewLine
    msg = msg & "  SyncStatus         Show config/status dialog"         & vbNewLine
    msg = msg & "  ShowLog            Open the log sheet"                & vbNewLine
    msg = msg & "  ClearLog           Wipe the log"                      & vbNewLine

    MsgBox msg, vbInformation, "Sync Setup"
End Sub
