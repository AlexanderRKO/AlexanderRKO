Attribute VB_Name = "modOAuth"
' ============================================================
' modOAuth.bas
' OAuth 2.0 "installed app" flow for the Google Sheets API.
'
' Tokens are cached in-memory for the session and the refresh
' token is persisted in a hidden sheet so re-authorization is
' only needed once per workbook.
' ============================================================
Option Explicit

Private Const OAUTH_TOKEN_URL As String = "https://oauth2.googleapis.com/token"
Private Const OAUTH_AUTH_URL  As String = "https://accounts.google.com/o/oauth2/auth"
Private Const OAUTH_SCOPE     As String = "https://www.googleapis.com/auth/spreadsheets"

' In-memory token cache
Private m_AccessToken  As String
Private m_TokenExpiry  As Date
Private m_RefreshToken As String

' ============================================================
' GetAccessToken  (public – called by every API request)
' Returns a valid bearer token, refreshing silently when
' the cached one is within 60 seconds of expiry.
' ============================================================
Public Function GetAccessToken() As String
    If m_AccessToken = "" Or Now() >= m_TokenExpiry - (60 / 86400) Then
        If m_RefreshToken = "" Then
            m_RefreshToken = LoadRefreshToken()
        End If

        If m_RefreshToken = "" Then
            AuthorizeApplication
        Else
            RefreshAccessToken
        End If
    End If

    GetAccessToken = m_AccessToken
End Function

' ============================================================
' AuthorizeApplication
' Opens the user's browser for the Google consent screen,
' then exchanges the returned code for tokens.
' ============================================================
Public Sub AuthorizeApplication()
    Dim authUrl As String
    authUrl = OAUTH_AUTH_URL & _
              "?client_id="     & GOOGLE_CLIENT_ID & _
              "&redirect_uri=urn:ietf:wg:oauth:2.0:oob" & _
              "&response_type=code" & _
              "&scope="         & OAUTH_SCOPE & _
              "&access_type=offline" & _
              "&prompt=consent"

    ' Open default browser
    Shell "explorer.exe """ & authUrl & """"

    Dim authCode As String
    authCode = InputBox( _
        "Steps:" & vbNewLine & _
        "  1. Complete the authorization in your browser." & vbNewLine & _
        "  2. Copy the code that Google shows you." & vbNewLine & _
        "  3. Paste it below and click OK.", _
        "Google Authorization – Paste Code Here")

    If Trim(authCode) = "" Then
        MsgBox "Authorization cancelled. Sync will not work until authorized.", vbExclamation
        Exit Sub
    End If

    ExchangeCodeForTokens Trim(authCode)
End Sub

' ============================================================
' ClearTokens
' Revokes in-memory and persisted tokens, forcing re-auth on
' the next sync call.
' ============================================================
Public Sub ClearTokens()
    m_AccessToken  = ""
    m_RefreshToken = ""
    m_TokenExpiry  = CDate(0)
    SaveRefreshToken ""
    LogMessage "Tokens cleared – re-authorization required."
End Sub

' ----------------------------------------------------------
' Private helpers
' ----------------------------------------------------------

Private Sub RefreshAccessToken()
    Dim body As String
    body = "client_id="     & GOOGLE_CLIENT_ID & _
           "&client_secret=" & GOOGLE_CLIENT_SECRET & _
           "&refresh_token=" & m_RefreshToken & _
           "&grant_type=refresh_token"

    Dim response As String
    response = PostForm(OAUTH_TOKEN_URL, body)

    m_AccessToken = ExtractJsonValue(response, "access_token")
    If m_AccessToken = "" Then
        Err.Raise vbObjectError + 1001, "RefreshAccessToken", _
                  "Failed to refresh token. Response: " & response
    End If

    Dim expiresIn As Long
    expiresIn = CLng(ExtractJsonValue(response, "expires_in"))
    m_TokenExpiry = Now() + expiresIn / 86400

    LogMessage "Access token refreshed (expires in " & expiresIn & "s)."
End Sub

Private Sub ExchangeCodeForTokens(authCode As String)
    Dim body As String
    body = "client_id="     & GOOGLE_CLIENT_ID & _
           "&client_secret=" & GOOGLE_CLIENT_SECRET & _
           "&code="          & authCode & _
           "&redirect_uri=urn:ietf:wg:oauth:2.0:oob" & _
           "&grant_type=authorization_code"

    Dim response As String
    response = PostForm(OAUTH_TOKEN_URL, body)

    m_AccessToken  = ExtractJsonValue(response, "access_token")
    m_RefreshToken = ExtractJsonValue(response, "refresh_token")

    If m_AccessToken = "" Or m_RefreshToken = "" Then
        Err.Raise vbObjectError + 1002, "ExchangeCodeForTokens", _
                  "Token exchange failed. Response: " & response
    End If

    Dim expiresIn As Long
    expiresIn = CLng(ExtractJsonValue(response, "expires_in"))
    m_TokenExpiry = Now() + expiresIn / 86400

    SaveRefreshToken m_RefreshToken
    LogMessage "Authorization successful – tokens obtained and persisted."
    MsgBox "Authorization successful! You can now use sync.", vbInformation
End Sub

' Persist the refresh token in the hidden config sheet
Private Sub SaveRefreshToken(token As String)
    Dim ws As Worksheet
    Set ws = GetOrCreateHiddenSheet(TOKEN_STORAGE_SHEET)
    ws.Range(TOKEN_CELL).Value = token
End Sub

' Load the refresh token from the hidden config sheet
Private Function LoadRefreshToken() As String
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(TOKEN_STORAGE_SHEET)
    On Error GoTo 0

    If ws Is Nothing Then
        LoadRefreshToken = ""
    Else
        LoadRefreshToken = ws.Range(TOKEN_CELL).Value
    End If
End Function

' Minimal HTTP POST with application/x-www-form-urlencoded body
Private Function PostForm(url As String, body As String) As String
    Dim http As Object
    Set http = CreateObject("MSXML2.XMLHTTP.6.0")
    http.Open "POST", url, False
    http.setRequestHeader "Content-Type", "application/x-www-form-urlencoded"
    http.send body
    PostForm = http.responseText
End Function
