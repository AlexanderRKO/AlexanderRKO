@echo off
REM Windows double-click launcher for the MYOB -> Xero migration dashboard.
REM Double-click in Explorer; first run sets up a virtualenv and installs
REM dependencies (~30s), subsequent runs start in a few seconds.

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   MYOB -^> Xero migration -- Dashboard launcher (Windows)
echo ============================================================
echo.

REM ------------------------------------------------------------ Python
REM Find a working Python 3.10+ interpreter. Three gotchas to handle:
REM   1. The Microsoft Store python.exe stub responds to `where` even
REM      when no real Python is installed -- it opens the Store when
REM      you actually run it. Verify with `import sys`, not just
REM      `where`, to catch this.
REM   2. The `py` launcher (shipped with the python.org installer)
REM      handles version selection cleanly, so prefer it.
REM   3. If Python was installed without "Add to PATH" ticked, neither
REM      `py` nor `python` is on PATH. Search the default install
REM      locations directly as a fallback so the launcher Just Works.

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul && set "PY=python"

REM Fallback: scan common install locations. Newest first.
if not defined PY (
    for %%V in (314 313 312 311 310) do (
        for %%D in (
            "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            "%ProgramFiles%\Python%%V\python.exe"
            "%ProgramFiles(x86)%\Python%%V\python.exe"
            "C:\Python%%V\python.exe"
        ) do (
            if not defined PY if exist %%D (
                %%D -c "import sys" >nul 2>nul && set "PY=%%~D"
            )
        )
    )
)

if not defined PY (
    echo ============================================================
    echo   ERROR: Python 3.10 or later not found on this PC
    echo ============================================================
    echo.
    echo This launcher just checked:
    echo   * the `py` launcher                            ^(not on PATH^)
    echo   * `python` on PATH                             ^(not found^)
    echo   * default install locations under              ^(not found^)
    echo       %LOCALAPPDATA%\Programs\Python\
    echo       %ProgramFiles%\Python*\
    echo.
    echo What to do:
    echo.
    echo   1. Open    https://www.python.org/downloads/
    echo   2. Download the latest Python 3 Windows installer
    echo      ^(the big yellow button^).
    echo   3. Run the installer. On the FIRST screen, before you click
    echo      "Install Now", TICK the box that says:
    echo.
    echo            [x] Add python.exe to PATH
    echo.
    echo   4. After install finishes, close THIS window AND any open
    echo      Explorer / File Explorer windows, then double-click
    echo      "Start Migration Dashboard.bat" again. ^(Explorer caches
    echo      the PATH at startup -- new processes won't see the
    echo      updated PATH until Explorer is restarted or you log out
    echo      and back in.^)
    echo.
    echo Already installed Python and still seeing this?
    echo   * In CMD ^(Start menu -^> type "cmd"^), run:    python --version
    echo     If that works but this launcher doesn't, your Explorer
    echo     has a stale PATH -- log out and back in.
    echo   * If `python --version` fails too, re-run the python.org
    echo     installer, choose "Modify", and tick both
    echo     "Add python.exe to PATH" and "py launcher".
    echo   * DO NOT use the Microsoft Store Python -- it leaves a
    echo     stub that confuses launchers like this one.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo Using %PY% ^(%%v^)

REM ------------------------------------------------------------ venv
if not exist .venv (
    echo First-run setup: creating virtual environment...
    %PY% -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing / verifying dependencies (quietly)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

set "PORT=8501"
set "URL=http://localhost:%PORT%"

echo.
echo Starting dashboard at %URL%
echo (Close this window to stop the dashboard.)
echo.

REM Open the browser ~3s after Streamlit binds, in a backgrounded shell
REM so it doesn't block the streamlit run. Firing it immediately races
REM the server and lands on "site can't be reached".
start "" /min cmd /c "timeout /t 3 /nobreak >nul & start """" %URL%"

streamlit run dashboard.py ^
    --server.port %PORT% ^
    --server.headless true ^
    --browser.gatherUsageStats false

endlocal
