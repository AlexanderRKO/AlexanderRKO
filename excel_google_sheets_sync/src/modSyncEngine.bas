Attribute VB_Name = "modSyncEngine"
' ============================================================
' modSyncEngine.bas
' Core sync operations.
'
' Public surface:
'   SyncExcelToGoogle  – push a local range to Google
'   SyncGoogleToExcel  – pull a Google range into Excel
'   TwoWaySync         – bidirectional with conflict resolution
' ============================================================
Option Explicit

' ============================================================
' SyncExcelToGoogle
' Reads localSheet!localRange from Excel and writes it to
' googleSheet!googleRange via the Sheets API.
' ============================================================
Public Sub SyncExcelToGoogle(localSheet  As String, localRange  As String, _
                              googleSheet As String, googleRange As String)
    LogMessage "PUSH  " & localSheet & "!" & localRange & " -> " & _
               googleSheet & "!" & googleRange

    Dim ws As Worksheet
    On Error GoTo ErrHandler
    Set ws = ThisWorkbook.Sheets(localSheet)

    Dim data As Variant
    data = ws.Range(localRange).Value

    EnsureSheetExists googleSheet
    WriteGoogleRange googleSheet, googleRange, data
    StampSync localSheet, "TO_GOOGLE"

    LogMessage "PUSH  complete"
    Exit Sub
ErrHandler:
    LogMessage "ERROR SyncExcelToGoogle: " & Err.Description
    Err.Raise Err.Number, Err.Source, Err.Description
End Sub

' ============================================================
' SyncGoogleToExcel
' Reads googleSheet!googleRange and writes it into
' localSheet!localRange, creating the sheet if needed.
' ============================================================
Public Sub SyncGoogleToExcel(googleSheet As String, googleRange As String, _
                              localSheet  As String, localRange  As String)
    LogMessage "PULL  " & googleSheet & "!" & googleRange & " -> " & _
               localSheet & "!" & localRange

    On Error GoTo ErrHandler
    Dim data As Variant
    data = ReadGoogleRange(googleSheet, googleRange)

    If IsEmpty(data) Then
        LogMessage "PULL  no data returned – nothing written"
        Exit Sub
    End If

    Dim ws As Worksheet
    Set ws = GetOrCreateSheet(localSheet)

    ' Write starting at the top-left cell of localRange
    Dim anchor As Range
    Set anchor = ws.Range(localRange).Cells(1, 1)

    Dim rowCount As Long : rowCount = UBound(data, 1) - LBound(data, 1) + 1
    Dim colCount As Long : colCount = UBound(data, 2) - LBound(data, 2) + 1

    Dim dest As Range
    Set dest = anchor.Resize(rowCount, colCount)
    dest.Value = data

    StampSync localSheet, "FROM_GOOGLE"
    LogMessage "PULL  complete (" & rowCount & " rows x " & colCount & " cols)"
    Exit Sub
ErrHandler:
    LogMessage "ERROR SyncGoogleToExcel: " & Err.Description
    Err.Raise Err.Number, Err.Source, Err.Description
End Sub

' ============================================================
' TwoWaySync
' Reads both sides and resolves conflicts per CONFLICT_STRATEGY.
' ============================================================
Public Sub TwoWaySync(localSheet  As String, localRange  As String, _
                      googleSheet As String, googleRange As String)
    LogMessage "TWOWAY " & localSheet & " <-> " & googleSheet

    On Error GoTo ErrHandler

    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets(localSheet)

    Dim excelData As Variant
    excelData = ws.Range(localRange).Value

    Dim googleData As Variant
    googleData = ReadGoogleRange(googleSheet, googleRange)

    Select Case UCase(CONFLICT_STRATEGY)

        Case "EXCEL_WINS"
            WriteGoogleRange googleSheet, googleRange, excelData
            StampSync localSheet, "TO_GOOGLE"

        Case "GOOGLE_WINS"
            If Not IsEmpty(googleData) Then
                PasteToExcel ws, localRange, googleData
                StampSync localSheet, "FROM_GOOGLE"
            End If

        Case "NEWER_WINS"
            Dim toGoogle As Date   : toGoogle   = ReadStamp(localSheet, "TO_GOOGLE")
            Dim fromGoogle As Date : fromGoogle = ReadStamp(localSheet, "FROM_GOOGLE")
            If toGoogle >= fromGoogle Then
                WriteGoogleRange googleSheet, googleRange, excelData
                StampSync localSheet, "TO_GOOGLE"
            Else
                If Not IsEmpty(googleData) Then
                    PasteToExcel ws, localRange, googleData
                    StampSync localSheet, "FROM_GOOGLE"
                End If
            End If

        Case "ASK_USER"
            Dim choice As VbMsgBoxResult
            choice = MsgBox( _
                "Sheet '" & localSheet & "' – which version should win?" & vbNewLine & vbNewLine & _
                "Yes  = Keep Excel  (push Excel  -> Google)" & vbNewLine & _
                "No   = Keep Google (pull Google -> Excel)", _
                vbYesNo + vbQuestion, "Sync Conflict")

            If choice = vbYes Then
                WriteGoogleRange googleSheet, googleRange, excelData
                StampSync localSheet, "TO_GOOGLE"
            Else
                If Not IsEmpty(googleData) Then
                    PasteToExcel ws, localRange, googleData
                    StampSync localSheet, "FROM_GOOGLE"
                End If
            End If

    End Select

    LogMessage "TWOWAY complete for " & localSheet
    Exit Sub
ErrHandler:
    LogMessage "ERROR TwoWaySync: " & Err.Description
    Err.Raise Err.Number, Err.Source, Err.Description
End Sub

' ----------------------------------------------------------
' Private helpers
' ----------------------------------------------------------

' Write a 2-D Variant array into an Excel sheet starting at
' the top-left cell of rangeAddr.
Private Sub PasteToExcel(ws As Worksheet, rangeAddr As String, data As Variant)
    Dim anchor As Range
    Set anchor = ws.Range(rangeAddr).Cells(1, 1)
    Dim dest As Range
    Set dest = anchor.Resize( _
        UBound(data, 1) - LBound(data, 1) + 1, _
        UBound(data, 2) - LBound(data, 2) + 1)
    dest.Value = data
End Sub

' Get an existing sheet or create a new one at the end
Public Function GetOrCreateSheet(name As String) As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(name)
    On Error GoTo 0

    If ws Is Nothing Then
        Set ws = ThisWorkbook.Sheets.Add( _
            After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        ws.Name = name
        LogMessage "Created Excel sheet: " & name
    End If

    Set GetOrCreateSheet = ws
End Function

' Create (or retrieve) a hidden sheet used for config/token storage
Public Function GetOrCreateHiddenSheet(name As String) As Worksheet
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(name)
    On Error GoTo 0

    If ws Is Nothing Then
        Set ws = ThisWorkbook.Sheets.Add( _
            After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        ws.Name = name
    End If

    ws.Visible = xlSheetVeryHidden
    Set GetOrCreateHiddenSheet = ws
End Function

' ----------------------------------------------------------
' Sync timestamps – stored in the hidden config sheet (col B/C)
' ----------------------------------------------------------

Private Sub StampSync(sheetName As String, direction As String)
    Dim cfg As Worksheet
    Set cfg = GetOrCreateHiddenSheet(TOKEN_STORAGE_SHEET)

    Dim key As String : key = sheetName & "|" & direction
    Dim lastRow As Long
    lastRow = cfg.Cells(cfg.Rows.Count, "B").End(xlUp).Row

    Dim i As Long
    For i = 1 To lastRow
        If cfg.Cells(i, "B").Value = key Then
            cfg.Cells(i, "C").Value = Now()
            Exit Sub
        End If
    Next i

    cfg.Cells(lastRow + 1, "B").Value = key
    cfg.Cells(lastRow + 1, "C").Value = Now()
End Sub

Private Function ReadStamp(sheetName As String, direction As String) As Date
    Dim cfg As Worksheet
    On Error Resume Next
    Set cfg = ThisWorkbook.Sheets(TOKEN_STORAGE_SHEET)
    On Error GoTo 0
    If cfg Is Nothing Then ReadStamp = CDate(0) : Exit Function

    Dim key As String : key = sheetName & "|" & direction
    Dim lastRow As Long
    lastRow = cfg.Cells(cfg.Rows.Count, "B").End(xlUp).Row

    Dim i As Long
    For i = 1 To lastRow
        If cfg.Cells(i, "B").Value = key Then
            ReadStamp = CDate(cfg.Cells(i, "C").Value)
            Exit Function
        End If
    Next i

    ReadStamp = CDate(0)
End Function
