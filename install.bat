@echo off
setlocal

REM One-click installer for Windows (WSL-backed).
REM - Prepares .venv in the WSL repo
REM - Installs editable package (pip install -e .)
REM - Creates a Desktop shortcut named "RC Simulator"

set "REPO_DIR=%~dp0"
set "LOG_FILE=%TEMP%\rc_simulator_install.log"

echo [rc-simulator] Installing...> "%LOG_FILE%"
echo [rc-simulator] Repo=%REPO_DIR%>> "%LOG_FILE%"
echo.>> "%LOG_FILE%"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%REPO_DIR%ops\windows\install_shortcut.ps1" -ShortcutName "RC Simulator.lnk" >> "%LOG_FILE%" 2>&1
set "EXITCODE=%ERRORLEVEL%"

echo.>> "%LOG_FILE%"
echo ExitCode=%EXITCODE%>> "%LOG_FILE%"

REM Surface evidence (double click can look like "it closed and did nothing").
start "" notepad "%LOG_FILE%" >nul 2>&1

if not "%EXITCODE%"=="0" (
  echo [rc-simulator] FAILED. See log: %LOG_FILE%
  pause
  exit /b %EXITCODE%
)

echo [rc-simulator] OK. See log: %LOG_FILE%
timeout /t 2 >nul
endlocal

