@echo off
REM ============================================
REM  finance-agentic-workflow - Launcher
REM  finwf CLI (installed in .venv via pip install -e .)
REM  Run without args for help.
REM ============================================
cd /d "%~dp0"

set "EXE=.venv\Scripts\finwf.exe"
if not exist "%EXE%" (
    echo Installing package into .venv (first run)...
    python -m venv .venv 2>nul
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -e . || goto :error
)

if "%~1"=="" (
    "%EXE%" --help
    echo.
    echo Run e.g.:  run.bat analyze --help
) else (
    "%EXE%" %*
)
pause
goto :eof

:error
echo Setup failed. Make sure Python 3.10+ is installed and on PATH.
pause
exit /b 1
