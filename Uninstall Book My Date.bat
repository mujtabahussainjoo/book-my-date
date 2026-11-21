@echo off
setlocal
pushd "%~dp0" >nul 2>nul
py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0uninstaller\uninstall.py" --all --purge --yes --force %*
    if errorlevel 1 pause
    popd
    exit /b
)
python -c "import sys" >nul 2>nul
if not errorlevel 1 (
    python "%~dp0uninstaller\uninstall.py" --all --purge --yes --force %*
    if errorlevel 1 pause
    popd
    exit /b
)
echo Python 3.9 or newer is required. Install it from python.org, then run this launcher again.
pause
popd
exit /b 1
