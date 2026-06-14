@echo off
setlocal
cd /d "%~dp0"
where pythonw >nul 2>nul
if %ERRORLEVEL% neq 0 (echo Error: pythonw.exe not found in PATH. Please install Python. & pause & exit)
start "" pythonw profilesync-gui.pyw