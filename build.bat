@echo off
echo ============================================
echo  PromptVault - Build Desktop App
echo ============================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Python nicht gefunden.
    pause & exit /b 1
)

echo [1/3] Abhaengigkeiten installieren...
pip install customtkinter pillow pyinstaller --quiet

echo [2/3] Icon generieren...
python create_icon.py

echo [3/3] Desktop-App bauen...
python -m PyInstaller --noconfirm --onefile --windowed ^
    --collect-data customtkinter ^
    --name "PromptVault" ^
    --icon icon.ico ^
    main.py

echo.
echo ============================================
echo  Fertig!  dist\PromptVault.exe
echo ============================================
pause
