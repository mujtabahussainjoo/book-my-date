@echo off
setlocal
pushd "%~dp0" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\windows\create_shortcuts.ps1"
if errorlevel 1 pause
popd
