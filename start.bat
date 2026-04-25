@echo off
echo PromptVault wird gestartet...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Python wurde nicht gefunden. Bitte installiere Python von https://python.org
    pause
    exit /b 1
)

python -c "import customtkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installiere customtkinter...
    pip install customtkinter
)

python main.py
