Attribute VB_Name = "modAutoSync"
' ============================================================
' modAutoSync.bas
' Programmatic (no-button) automatic sync using
' Application.OnTime and Worksheet_Change events.
'
' Usage:
'   StartAutoSync [intervalMinutes]   ' default from modConfig
'   StopAutoSync
'   IsAutoSyncRunning()               ' Boolean
'
' To trigger sync on cell edits, add this to each sheet module:
'   Private Sub Worksheet_Change(ByVal Target As Range)
'       OnSheetChange Me.Name, Target.Address
'   End Sub
' ============================================================
Option Explicit

Private m_Running      As Boolean
Private m_IntervalMins As Integer
Private m_NextFireTime As Date

' Public name used by Application.OnTime – must match exactly
Private Const TIMER_PROC As String = "RunScheduledSync"

' ============================================================
' StartAutoSync
' ============================================================
Public Sub StartAutoSyncService(Optional intervalMinutes As Integer = 0)
    If intervalMinutes <= 0 Then
        intervalMinutes = DEFAULT_SYNC_INTERVAL_MINUTES
    End If

    m_Running      = True
    m_IntervalMins = intervalMinutes
    m_NextFireTime = Now() + MinutesToDays(intervalMinutes)

    Application.OnTime m_NextFireTime, TIMER_PROC

    LogMessage "AutoSync started – every " & intervalMinutes & " min. " & _
               "Next fire: " & Format(m_NextFireTime, "HH:MM:SS")
End Sub

' ============================================================
' StopAutoSyncService
' ============================================================
Public Sub StopAutoSyncService()
    m_Running = False
    On Error Resume Next
    Application.OnTime m_NextFireTime, TIMER_PROC, , False
    On Error GoTo 0
    LogMessage "AutoSync stopped."
End Sub

' ============================================================
' RunScheduledSync  (called by Application.OnTime)
' Do NOT rename – must match TIMER_PROC above.
' ============================================================
Public Sub RunScheduledSync()
    If Not m_Running Then Exit Sub

    LogMessage "AutoSync fired at " & Format(Now(), "HH:MM:SS")

    On Error Resume Next
    SyncAllSheets
    If Err.Number <> 0 Then
        LogMessage "AutoSync error: " & Err.Description
        Err.Clear
    End If
    On Error GoTo 0

    ' Reschedule
    m_NextFireTime = Now() + MinutesToDays(m_IntervalMins)
    Application.OnTime m_NextFireTime, TIMER_PROC
    LogMessage "AutoSync rescheduled for " & Format(m_NextFireTime, "HH:MM:SS")
End Sub

' ============================================================
' OnSheetChange
' Call this from Worksheet_Change in any sheet module to get
' near-real-time sync.  Implements a 5-second debounce so
' rapid edits don't flood the API.
' ============================================================
Public Sub OnSheetChange(sheetName As String, changedAddress As String)
    ' Only act on sheets configured for outbound sync
    Dim configs As Variant
    configs = GetSheetConfigs()

    Dim i As Long
    For i = 0 To UBound(configs, 1)
        If configs(i, 0) = sheetName Then
            Dim dir As String : dir = UCase(configs(i, 4))
            If dir = "TO_GOOGLE" Or dir = "TWO_WAY" Then
                ' Cancel any queued debounce timer
                On Error Resume Next
                Application.OnTime m_NextFireTime, TIMER_PROC, , False
                On Error GoTo 0

                ' Re-queue with a 5-second debounce
                m_NextFireTime = Now() + (5 / 86400)
                Application.OnTime m_NextFireTime, TIMER_PROC

                LogMessage "Change in " & sheetName & " [" & changedAddress & _
                           "] – sync queued in 5 s"
            End If
            Exit For
        End If
    Next i
End Sub

' ============================================================
' IsAutoSyncRunning
' ============================================================
Public Function IsAutoSyncRunning() As Boolean
    IsAutoSyncRunning = m_Running
End Function

' ----------------------------------------------------------
' Helper
' ----------------------------------------------------------
Private Function MinutesToDays(mins As Integer) As Double
    MinutesToDays = mins / 1440
End Function
