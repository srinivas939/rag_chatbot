@echo off
setlocal
cd /d "%~dp0"
title RAG Document Chatbot

rem ---- find Python ----
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY (
    python --version >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo.
    echo  Python was not found on this computer.
    echo  Install Python 3.10 or newer from https://www.python.org/downloads/
    echo  and tick the box "Add Python to PATH" during installation.
    echo  Then double-click run.bat again.
    echo.
    pause
    exit /b 1
)

rem ---- first run: create environment and install packages ----
if not exist ".venv\Scripts\python.exe" (
    echo Creating a private Python environment...
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
)
if not exist ".venv\.installed" (
    echo Installing packages. This only happens once and takes a few minutes...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :fail
    echo done> ".venv\.installed"
)

rem ---- skip Streamlit's first-run email question ----
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

echo.
echo Starting the chatbot. Your browser will open in a moment.
echo Keep this window open while you use it. Close it to stop the app.
echo.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
exit /b 0

:fail
echo.
echo  Something went wrong during setup. Check your internet connection and
echo  run run.bat again. If it keeps failing, delete the ".venv" folder first.
echo.
pause
exit /b 1
