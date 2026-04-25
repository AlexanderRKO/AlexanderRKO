Attribute VB_Name = "modMultiSheet"
' ============================================================
' modMultiSheet.bas
' Orchestrates sync across all sheets defined in modConfig,
' plus helpers for selective and custom-range sync.
' ============================================================
Option Explicit

' ============================================================
' SyncAllSheets
' Iterates every row in GetSheetConfigs() and syncs each one
' according to its configured direction.
' ============================================================
Public Sub SyncAllSheets()
    LogMessage "==== SyncAllSheets START ===="

    Dim configs As Variant
    configs = GetSheetConfigs()

    Dim successCount As Long
    Dim errorCount   As Long
    Dim i As Long

    For i = 0 To UBound(configs, 1)
        Dim localSheet  As String : localSheet  = configs(i, 0)
        Dim localRange  As String : localRange  = configs(i, 1)
        Dim googleSheet As String : googleSheet = configs(i, 2)
        Dim googleRange As String : googleRange = configs(i, 3)
        Dim direction   As String : direction   = UCase(configs(i, 4))

        If localSheet = "" Then GoTo NextRow

        On Error GoTo RowError

        Select Case direction
            Case "TO_GOOGLE"
                SyncExcelToGoogle localSheet, localRange, googleSheet, googleRange
            Case "FROM_GOOGLE"
                SyncGoogleToExcel googleSheet, googleRange, localSheet, localRange
            Case "TWO_WAY"
                TwoWaySync localSheet, localRange, googleSheet, googleRange
            Case Else
                LogMessage "Unknown direction '" & direction & "' for sheet " & localSheet
        End Select

        successCount = successCount + 1
        GoTo NextRow

RowError:
        LogMessage "ERROR row " & i & " (" & localSheet & "): " & Err.Description
        errorCount = errorCount + 1
        Err.Clear
        Resume NextRow

NextRow:
    Next i

    LogMessage "==== SyncAllSheets END – OK:" & successCount & " ERR:" & errorCount & " ===="
End Sub

' ============================================================
' SyncSheetByName
' Syncs only the first config entry whose local sheet matches.
' ============================================================
Public Sub SyncSheetByName(localSheetName As String)
    Dim configs As Variant
    configs = GetSheetConfigs()

    Dim i As Long
    For i = 0 To UBound(configs, 1)
        If UCase(configs(i, 0)) = UCase(localSheetName) Then
            Select Case UCase(configs(i, 4))
                Case "TO_GOOGLE"
                    SyncExcelToGoogle configs(i, 0), configs(i, 1), configs(i, 2), configs(i, 3)
                Case "FROM_GOOGLE"
                    SyncGoogleToExcel configs(i, 2), configs(i, 3), configs(i, 0), configs(i, 1)
                Case "TWO_WAY"
                    TwoWaySync configs(i, 0), configs(i, 1), configs(i, 2), configs(i, 3)
            End Select
            Exit Sub
        End If
    Next i

    LogMessage "Sheet '" & localSheetName & "' not found in sync config."
End Sub

' ============================================================
' PushAllToGoogle
' Sends every outbound (TO_GOOGLE or TWO_WAY) sheet to Google.
' ============================================================
Public Sub PushAllToGoogle()
    LogMessage "Push all -> Google"
    Dim configs As Variant : configs = GetSheetConfigs()
    Dim i As Long
    For i = 0 To UBound(configs, 1)
        Dim dir As String : dir = UCase(configs(i, 4))
        If (dir = "TO_GOOGLE" Or dir = "TWO_WAY") And configs(i, 0) <> "" Then
            On Error Resume Next
            SyncExcelToGoogle configs(i, 0), configs(i, 1), configs(i, 2), configs(i, 3)
            If Err.Number <> 0 Then
                LogMessage "Push error (" & configs(i, 0) & "): " & Err.Description
                Err.Clear
            End If
            On Error GoTo 0
        End If
    Next i
End Sub

' ============================================================
' PullAllFromGoogle
' Fetches every inbound (FROM_GOOGLE or TWO_WAY) sheet.
' ============================================================
Public Sub PullAllFromGoogle()
    LogMessage "Pull all <- Google"
    Dim configs As Variant : configs = GetSheetConfigs()
    Dim i As Long
    For i = 0 To UBound(configs, 1)
        Dim dir As String : dir = UCase(configs(i, 4))
        If (dir = "FROM_GOOGLE" Or dir = "TWO_WAY") And configs(i, 0) <> "" Then
            On Error Resume Next
            SyncGoogleToExcel configs(i, 2), configs(i, 3), configs(i, 0), configs(i, 1)
            If Err.Number <> 0 Then
                LogMessage "Pull error (" & configs(i, 0) & "): " & Err.Description
                Err.Clear
            End If
            On Error GoTo 0
        End If
    Next i
End Sub

' ============================================================
' SyncCustomRange
' One-off sync of any range not necessarily in the config.
'   direction: "TO_GOOGLE" | "FROM_GOOGLE" | "TWO_WAY"
' ============================================================
Public Sub SyncCustomRange(localSheet  As String, localRange  As String, _
                            googleSheet As String, googleRange As String, _
                            direction   As String)
    Select Case UCase(direction)
        Case "TO_GOOGLE"
            SyncExcelToGoogle localSheet, localRange, googleSheet, googleRange
        Case "FROM_GOOGLE"
            SyncGoogleToExcel googleSheet, googleRange, localSheet, localRange
        Case "TWO_WAY"
            TwoWaySync localSheet, localRange, googleSheet, googleRange
        Case Else
            Err.Raise vbObjectError + 3001, "SyncCustomRange", _
                      "Invalid direction '" & direction & _
                      "'. Use TO_GOOGLE, FROM_GOOGLE, or TWO_WAY."
    End Select
End Sub

' ============================================================
' ShowSyncStatus
' Quick summary dialog.
' ============================================================
Public Sub ShowSyncStatus()
    Dim msg As String
    msg = "Excel <-> Google Sheets Sync" & vbNewLine & vbNewLine
    msg = msg & "Auto sync: " & IIf(IsAutoSyncRunning(), "RUNNING", "STOPPED") & vbNewLine & vbNewLine
    msg = msg & "Configured sheet mappings:" & vbNewLine

    Dim configs As Variant : configs = GetSheetConfigs()
    Dim i As Long
    For i = 0 To UBound(configs, 1)
        If configs(i, 0) <> "" Then
            msg = msg & "  [" & configs(i, 4) & "]  " & _
                  configs(i, 0) & "!" & configs(i, 1) & "  <->  " & _
                  configs(i, 2) & "!" & configs(i, 3) & vbNewLine
        End If
    Next i

    MsgBox msg, vbInformation, "Sync Status"
End Sub
