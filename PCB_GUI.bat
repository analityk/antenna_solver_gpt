@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Brak .venv\Scripts\pythonw.exe. Zainstaluj srodowisko projektu.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m antenna_lab.pcb.gui
