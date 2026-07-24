@echo off
REM Windows double-click launcher for the MYOB -> Xero migration dashboard.
REM Double-click in Explorer; first run sets up a virtualenv and installs
REM dependencies (~30s), subsequent runs start in a few seconds.

setlocal
cd /d "%~dp0"

echo ============================================================
echo   MYOB -^> Xero migration -- Dashboard launcher (Windows)
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python 3.10+ not found.
        echo Install from https://www.python.org/downloads/ and try again.
        pause
        exit /b 1
    )
    set "PY=py"
) else (
    set "PY=python"
)
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo Using %PY% (%%v)

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

start "" "%URL%"

streamlit run dashboard.py ^
    --server.port %PORT% ^
    --server.headless true ^
    --browser.gatherUsageStats false

endlocal
