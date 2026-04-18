@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install from https://www.python.org/downloads/ first.
  exit /b 1
)

echo Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat

echo Installing Python dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Ensuring Google Chrome is available to Playwright...
python -m playwright install chrome
if errorlevel 1 exit /b 1

echo.
echo Setup complete.
echo Next: run.bat "^<paste-your-sales-nav-search-url^>"
endlocal
