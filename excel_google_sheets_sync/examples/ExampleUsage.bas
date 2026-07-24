Attribute VB_Name = "ExampleUsage"
' ============================================================
' ExampleUsage.bas
' Copy whichever examples you need into a standard module in
' your workbook, or run them directly from the VBA editor.
' ============================================================
Option Explicit

' ----------------------------------------------------------
' Example 1 – Authorize once (run first, ever)
' ----------------------------------------------------------
Sub Ex1_Authorize()
    Authorize
End Sub

' ----------------------------------------------------------
' Example 2 – Sync all sheets defined in modConfig
' ----------------------------------------------------------
Sub Ex2_SyncAll()
    SyncAll
    MsgBox "Sync complete.", vbInformation
End Sub

' ----------------------------------------------------------
' Example 3 – Push a specific sheet to Google only
' ----------------------------------------------------------
Sub Ex3_PushSalesSheet()
    ' Pushes the "Sales" sheet, range A1:F500, to a Google tab
    ' named "Sales" at the same range.
    SyncRange "Sales", "A1:F500", "Sales", "A1:F500", "TO_GOOGLE"
End Sub

' ----------------------------------------------------------
' Example 4 – Pull a price list from Google into Excel
' ----------------------------------------------------------
Sub Ex4_PullPriceList()
    ' Reads "PriceList!A1:C200" from Google and writes it into
    ' the local "Prices" sheet.
    SyncRange "Prices", "A1:C200", "PriceList", "A1:C200", "FROM_GOOGLE"
End Sub

' ----------------------------------------------------------
' Example 5 – True two-way sync of a single range
' ----------------------------------------------------------
Sub Ex5_TwoWaySync()
    SyncRange "Dashboard", "A1:Z50", "Dashboard", "A1:Z50", "TWO_WAY"
End Sub

' ----------------------------------------------------------
' Example 6 – Auto sync every 10 minutes (timer-based)
' ----------------------------------------------------------
Sub Ex6_StartAutoSync_10min()
    StartAutoSync 10
    MsgBox "Auto sync started. All configured sheets will sync every 10 minutes.", _
           vbInformation
End Sub

' ----------------------------------------------------------
' Example 7 – Stop the auto-sync timer
' ----------------------------------------------------------
Sub Ex7_StopAutoSync()
    StopAutoSync
    MsgBox "Auto sync stopped.", vbInformation
End Sub

' ----------------------------------------------------------
' Example 8 – Sync only one named sheet from the config
' ----------------------------------------------------------
Sub Ex8_SyncOneSheet()
    SyncSheet "Summary"
End Sub

' ----------------------------------------------------------
' Example 9 – Near-real-time push via Worksheet_Change
'
' Paste this block into the Sheet module (not a standard
' module) of the sheet you want to watch.  Every time the
' user edits a cell in A1:F100 the change is queued to push
' to Google within 5 seconds (debounced).
' ----------------------------------------------------------
'
'   Private Sub Worksheet_Change(ByVal Target As Range)
'       If Not Intersect(Target, Me.Range("A1:F100")) Is Nothing Then
'           OnSheetChange Me.Name, Target.Address
'       End If
'   End Sub
'
' ----------------------------------------------------------

' ----------------------------------------------------------
' Example 10 – Batch sync multiple custom ranges at once
' ----------------------------------------------------------
Sub Ex10_BatchSync()
    SyncRange "Inventory", "A1:E200", "Inventory",   "A1:E200", "TWO_WAY"
    SyncRange "Orders",    "A1:H500", "Orders",      "A1:H500", "TO_GOOGLE"
    SyncRange "Prices",    "A1:C50",  "MasterPrices", "A1:C50", "FROM_GOOGLE"
    MsgBox "Batch sync complete.", vbInformation
End Sub

' ----------------------------------------------------------
' Example 11 – Show current sync status and log
' ----------------------------------------------------------
Sub Ex11_ViewStatus()
    SyncStatus
End Sub

Sub Ex11_ViewLog()
    ShowLog
End Sub
