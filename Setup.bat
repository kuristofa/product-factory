@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo   AI-powered Product Production Factory  -  ONE-TIME SETUP
echo   (Run this once. After this, use Start.bat every day.)
echo ============================================================
echo.

where py >nul 2>&1
if errorlevel 1 (
  echo [X] Python is not installed.
  echo     Install Python 3.11 or newer from https://www.python.org/downloads/
  echo     During install, TICK "Add Python to PATH". Then run Setup.bat again.
  echo.
  pause
  exit /b 1
)

echo [1/3] Creating the app environment...
py -3.11 -m venv .venv 2>nul || py -m venv .venv
call .\.venv\Scripts\activate.bat

echo [2/3] Installing the app (this can take a couple of minutes)...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q

echo [3/3] Checking Claude Code (the AI engine)...
where claude >nul 2>&1
if errorlevel 1 (
  echo.
  echo   [!] Claude Code is not installed yet. To finish setup:
  echo       1^) Install Node.js ^(LTS^) from https://nodejs.org
  echo       2^) Open a NEW terminal and run:  npm install -g @anthropic-ai/claude-code
  echo       3^) Then run:  claude    and sign in with your Claude Max account
  echo.
) else (
  echo   [OK] Claude Code is installed.
  echo        If you have not signed in yet, open a terminal and run:  claude
  echo.
)

echo ============================================================
echo   Setup finished.
echo   To use the app any time, double-click:  Start.bat
echo ============================================================
echo.
pause
