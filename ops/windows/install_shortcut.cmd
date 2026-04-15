@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%TEMP%\rc_simulator_install_shortcut.log"

echo [rc-simulator] Installing shortcut...> "%LOG_FILE%"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install_shortcut.ps1" >> "%LOG_FILE%" 2>&1
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

