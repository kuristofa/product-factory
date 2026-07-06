@echo off
cd /d "%~dp0"
if not exist ".\.venv\Scripts\activate.bat" (
  echo This computer is not set up yet.
  echo Please double-click  Setup.bat  first ^(only needed once^).
  echo.
  pause
  exit /b 1
)
call .\.venv\Scripts\activate.bat
python desktop.py
