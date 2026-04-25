Attribute VB_Name = "modGoogleAPI"
' ============================================================
' modGoogleAPI.bas
' Thin wrapper around Google Sheets API v4.
'
' Public surface used by the rest of the tool:
'   ReadGoogleRange    – returns a 2-D Variant array
'   WriteGoogleRange   – accepts a 2-D Variant array
'   ClearGoogleRange   – empties cells on the remote sheet
'   BatchWriteRanges   – multiple ranges in one API round-trip
'   EnsureSheetExists  – creates a tab if it does not yet exist
' ============================================================
Option Explicit

Private Const API_BASE As String = _
    "https://sheets.googleapis.com/v4/spreadsheets/"

' ============================================================
' ReadGoogleRange
' Returns a 1-based 2-D Variant array (rows x cols).
' Returns an empty Variant if the range has no data.
' ============================================================
Public Function ReadGoogleRange(googleSheet As String, _
                                rangeAddr  As String) As Variant
    Dim url As String
    url = API_BASE & SPREADSHEET_ID & "/values/" & _
          UrlEncode(googleSheet & "!" & rangeAddr)

    Dim json As String
    json = ApiGet(url)

    ReadGoogleRange = ParseValuesJson(json)
    LogMessage "READ  " & googleSheet & "!" & rangeAddr
End Function

' ============================================================
' WriteGoogleRange
' Overwrites the remote range with data (2-D Variant array).
' valueInputOption USER_ENTERED so formulas are respected.
' ============================================================
Public Sub WriteGoogleRange(googleSheet As String, _
                             rangeAddr  As String, _
                             data       As Variant)
    Dim url As String
    url = API_BASE & SPREADSHEET_ID & "/values/" & _
          UrlEncode(googleSheet & "!" & rangeAddr) & _
          "?valueInputOption=USER_ENTERED"

    Dim body As String
    body = "{""range"":""" & googleSheet & "!" & rangeAddr & """," & _
           """values"":" & Array2dToJsonRows(data) & "}"

    ApiPut url, body
    LogMessage "WRITE " & googleSheet & "!" & rangeAddr
End Sub

' ============================================================
' ClearGoogleRange
' ============================================================
Public Sub ClearGoogleRange(googleSheet As String, rangeAddr As String)
    Dim url As String
    url = API_BASE & SPREADSHEET_ID & "/values/" & _
          UrlEncode(googleSheet & "!" & rangeAddr) & ":clear"

    ApiPost url, "{}"
    LogMessage "CLEAR " & googleSheet & "!" & rangeAddr
End Sub

' ============================================================
' BatchWriteRanges
' items is a Collection; each element is a 3-element array:
'   (0) googleSheetName  (1) rangeAddress  (2) 2-D data Variant
' ============================================================
Public Sub BatchWriteRanges(items As Collection)
    Dim url As String
    url = API_BASE & SPREADSHEET_ID & "/values:batchUpdate"

    Dim dataArr As String
    dataArr = "["
    Dim first As Boolean
    first = True

    Dim item As Variant
    For Each item In items
        If Not first Then dataArr = dataArr & ","
        dataArr = dataArr & _
            "{""range"":""" & item(0) & "!" & item(1) & """," & _
            """values"":" & Array2dToJsonRows(item(2)) & "}"
        first = False
    Next item
    dataArr = dataArr & "]"

    ApiPost url, "{""valueInputOption"":""USER_ENTERED"",""data"":" & dataArr & "}"
    LogMessage "BATCH WRITE – " & items.Count & " ranges"
End Sub

' ============================================================
' EnsureSheetExists
' Checks the spreadsheet metadata; adds a tab if missing.
' ============================================================
Public Sub EnsureSheetExists(sheetName As String)
    Dim meta As String
    meta = ApiGet(API_BASE & SPREADSHEET_ID & "?fields=sheets.properties.title")

    ' A simple title search is sufficient – titles are unique per spreadsheet
    If InStr(meta, """title"": """ & sheetName & """") > 0 Then Exit Sub

    Dim body As String
    body = "{""requests"":[{""addSheet"":{""properties"":{""title"":""" & _
           EscapeJson(sheetName) & """}}}]}"
    ApiPost API_BASE & SPREADSHEET_ID & ":batchUpdate", body
    LogMessage "Created Google Sheet tab: " & sheetName
End Sub

' ----------------------------------------------------------
' JSON – parse Google Sheets API "values" response
' ----------------------------------------------------------

' Returns a 1-based 2-D Variant array, or an empty Variant
Private Function ParseValuesJson(json As String) As Variant
    ' Locate the "values" array
    Dim valKey As Long
    valKey = InStr(json, """values"":")
    If valKey = 0 Then
        ParseValuesJson = Empty
        Exit Function
    End If

    ' Find the opening '[' of the outer array
    Dim outerOpen As Long
    outerOpen = InStr(valKey, json, "[")
    If outerOpen = 0 Then
        ParseValuesJson = Empty
        Exit Function
    End If

    Dim outerClose As Long
    outerClose = MatchingBracket(json, outerOpen, "[", "]")
    If outerClose < 0 Then
        ParseValuesJson = Empty
        Exit Function
    End If

    Dim valuesText As String
    valuesText = Mid(json, outerOpen + 1, outerClose - outerOpen - 1)

    ' Split into row strings by finding each inner "[...]" block
    Dim rowStrings() As String
    Dim rowCount As Long
    rowCount = 0

    ReDim rowStrings(0 To 255)

    Dim pos As Long
    pos = 1
    Do While pos <= Len(valuesText)
        Dim rowOpen As Long
        rowOpen = InStr(pos, valuesText, "[")
        If rowOpen = 0 Then Exit Do
        Dim rowClose As Long
        rowClose = MatchingBracket(valuesText, rowOpen, "[", "]")
        If rowClose < 0 Then Exit Do

        rowStrings(rowCount) = Mid(valuesText, rowOpen + 1, rowClose - rowOpen - 1)
        rowCount = rowCount + 1
        pos = rowClose + 1
    Loop

    If rowCount = 0 Then
        ParseValuesJson = Empty
        Exit Function
    End If

    ' Find max column count
    Dim maxCols As Long
    Dim r As Long
    For r = 0 To rowCount - 1
        Dim cells() As String
        cells = SplitJsonRow(rowStrings(r))
        If UBound(cells) + 1 > maxCols Then maxCols = UBound(cells) + 1
    Next r

    ' Build the result array (1-based)
    Dim result() As Variant
    ReDim result(1 To rowCount, 1 To maxCols)

    For r = 0 To rowCount - 1
        cells = SplitJsonRow(rowStrings(r))
        Dim c As Long
        For c = 0 To UBound(cells)
            result(r + 1, c + 1) = UnescapeJson(Trim(cells(c)))
        Next c
    Next r

    ParseValuesJson = result
End Function

' Split a JSON row string into cell strings, respecting quoted strings
Private Function SplitJsonRow(rowText As String) As String()
    Dim items() As String
    ReDim items(0 To 255)
    Dim count As Long
    Dim current As String
    Dim inStr As Boolean
    Dim i As Long

    For i = 1 To Len(rowText)
        Dim ch As String
        ch = Mid(rowText, i, 1)
        If ch = """" Then
            If inStr And i > 1 And Mid(rowText, i - 1, 1) = "\" Then
                ' escaped quote inside string
                current = current & ch
            Else
                inStr = Not inStr
                current = current & ch
            End If
        ElseIf ch = "," And Not inStr Then
            items(count) = current
            count = count + 1
            current = ""
        Else
            current = current & ch
        End If
    Next i
    items(count) = current
    count = count + 1

    ReDim Preserve items(0 To count - 1)
    SplitJsonRow = items
End Function

' ----------------------------------------------------------
' JSON – build values body from 2-D array
' ----------------------------------------------------------

Public Function Array2dToJsonRows(data As Variant) As String
    If IsEmpty(data) Then
        Array2dToJsonRows = "[]"
        Exit Function
    End If

    Dim r1 As Long, r2 As Long, c1 As Long, c2 As Long
    r1 = LBound(data, 1) : r2 = UBound(data, 1)
    c1 = LBound(data, 2) : c2 = UBound(data, 2)

    Dim sb As String
    sb = "["
    Dim r As Long
    For r = r1 To r2
        If r > r1 Then sb = sb & ","
        sb = sb & "["
        Dim c As Long
        For c = c1 To c2
            If c > c1 Then sb = sb & ","
            sb = sb & JsonValue(data(r, c))
        Next c
        sb = sb & "]"
    Next r
    sb = sb & "]"
    Array2dToJsonRows = sb
End Function

Private Function JsonValue(v As Variant) As String
    If IsNull(v) Or IsEmpty(v) Then
        JsonValue = """"""
    ElseIf VarType(v) = vbBoolean Then
        JsonValue = IIf(v, "true", "false")
    ElseIf IsNumeric(v) Then
        JsonValue = CStr(v)
    ElseIf VarType(v) = vbDate Then
        JsonValue = """" & Format(v, "YYYY-MM-DD") & """"
    Else
        JsonValue = """" & EscapeJson(CStr(v)) & """"
    End If
End Function

' ----------------------------------------------------------
' JSON – string escaping / unescaping
' ----------------------------------------------------------

Public Function EscapeJson(s As String) As String
    s = Replace(s, "\",  "\\")
    s = Replace(s, """", "\""")
    s = Replace(s, Chr(8),  "\b")
    s = Replace(s, Chr(9),  "\t")
    s = Replace(s, Chr(10), "\n")
    s = Replace(s, Chr(12), "\f")
    s = Replace(s, Chr(13), "\r")
    EscapeJson = s
End Function

Private Function UnescapeJson(s As String) As String
    ' Strip surrounding quotes
    If Len(s) >= 2 And Left(s, 1) = """" And Right(s, 1) = """" Then
        s = Mid(s, 2, Len(s) - 2)
    End If
    s = Replace(s, "\""", """")
    s = Replace(s, "\\",  "\")
    s = Replace(s, "\n",  Chr(10))
    s = Replace(s, "\r",  Chr(13))
    s = Replace(s, "\t",  Chr(9))
    UnescapeJson = s
End Function

' Extract a scalar string/number value from a JSON response by key
Public Function ExtractJsonValue(json As String, key As String) As String
    Dim needle As String
    needle = """" & key & """:"

    Dim p As Long
    p = InStr(json, needle)
    If p = 0 Then ExtractJsonValue = "" : Exit Function

    p = p + Len(needle)
    Do While Mid(json, p, 1) = " "
        p = p + 1
    Loop

    If Mid(json, p, 1) = """" Then
        ' String value – walk to closing quote
        p = p + 1
        Dim e As Long : e = p
        Do While e <= Len(json)
            If Mid(json, e, 1) = """" And (e = 1 Or Mid(json, e - 1, 1) <> "\") Then Exit Do
            e = e + 1
        Loop
        ExtractJsonValue = Mid(json, p, e - p)
    Else
        ' Number / boolean / null – walk to delimiter
        Dim e2 As Long : e2 = p
        Do While e2 <= Len(json) And InStr(",}]" & vbNewLine, Mid(json, e2, 1)) = 0
            e2 = e2 + 1
        Loop
        ExtractJsonValue = Trim(Mid(json, p, e2 - p))
    End If
End Function

' ----------------------------------------------------------
' URL encoding
' ----------------------------------------------------------

Public Function UrlEncode(s As String) As String
    Dim i As Long
    Dim result As String
    For i = 1 To Len(s)
        Dim ch As String
        ch = Mid(s, i, 1)
        Select Case ch
            Case "A" To "Z", "a" To "z", "0" To "9", "-", "_", ".", "~"
                result = result & ch
            Case " "
                result = result & "%20"
            Case ":"
                result = result & "%3A"
            Case "!"
                result = result & "%21"
            Case Else
                result = result & "%" & Right("0" & Hex(Asc(ch)), 2)
        End Select
    Next i
    UrlEncode = result
End Function

' ----------------------------------------------------------
' HTTP helpers (GET / PUT / POST with bearer token)
' ----------------------------------------------------------

Private Function ApiGet(url As String) As String
    Dim http As Object
    Set http = CreateObject("MSXML2.XMLHTTP.6.0")
    http.Open "GET", url, False
    http.setRequestHeader "Authorization", "Bearer " & GetAccessToken()
    http.send

    If http.Status = 401 Then
        ' Token may have just expired – clear cache and retry once
        ClearTokens
        http.Open "GET", url, False
        http.setRequestHeader "Authorization", "Bearer " & GetAccessToken()
        http.send
    End If

    If http.Status <> 200 Then
        Err.Raise vbObjectError + 2001, "ApiGet", _
                  "HTTP GET failed (" & http.Status & "): " & http.responseText
    End If
    ApiGet = http.responseText
End Function

Private Sub ApiPut(url As String, body As String)
    Dim http As Object
    Set http = CreateObject("MSXML2.XMLHTTP.6.0")
    http.Open "PUT", url, False
    http.setRequestHeader "Authorization",  "Bearer " & GetAccessToken()
    http.setRequestHeader "Content-Type",   "application/json"
    http.send body

    If http.Status <> 200 Then
        Err.Raise vbObjectError + 2002, "ApiPut", _
                  "HTTP PUT failed (" & http.Status & "): " & http.responseText
    End If
End Sub

Private Sub ApiPost(url As String, body As String)
    Dim http As Object
    Set http = CreateObject("MSXML2.XMLHTTP.6.0")
    http.Open "POST", url, False
    http.setRequestHeader "Authorization",  "Bearer " & GetAccessToken()
    http.setRequestHeader "Content-Type",   "application/json"
    http.send body

    If http.Status <> 200 Then
        Err.Raise vbObjectError + 2003, "ApiPost", _
                  "HTTP POST failed (" & http.Status & "): " & http.responseText
    End If
End Sub

' ----------------------------------------------------------
' Bracket matcher – returns position of closing bracket
' ----------------------------------------------------------

Private Function MatchingBracket(s As String, openPos As Long, _
                                  openCh As String, closeCh As String) As Long
    Dim depth As Long
    Dim i As Long
    For i = openPos To Len(s)
        If Mid(s, i, 1) = openCh  Then depth = depth + 1
        If Mid(s, i, 1) = closeCh Then
            depth = depth - 1
            If depth = 0 Then
                MatchingBracket = i
                Exit Function
            End If
        End If
    Next i
    MatchingBracket = -1
End Function
