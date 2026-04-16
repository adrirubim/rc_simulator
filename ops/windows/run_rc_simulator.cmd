@echo off
setlocal

REM Wrapper used by the Desktop shortcut.
REM Captures stdout/stderr so failures don't look like "it did nothing".

set "DISTRO=%~1"
set "WSL_REPO_PATH=%~2"

set "LOG_FILE=%TEMP%\rc_simulator_run.log"
set "DESKTOP_LOG=%USERPROFILE%\Desktop\rc_simulator_run.log"
set "CFG_FILE=%LOCALAPPDATA%\rc_simulator\runner.env"

REM If args are missing (shortcut quoting issues), load from local config.
if "%WSL_REPO_PATH%"=="" (
  if exist "%CFG_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%CFG_FILE%") do (
      if /i "%%A"=="DISTRO" set "DISTRO=%%B"
      if /i "%%A"=="WSL_REPO_PATH" set "WSL_REPO_PATH=%%B"
    )
  )
)

echo [rc-simulator] Launching...> "%LOG_FILE%"
echo [rc-simulator] Distro=%DISTRO%>> "%LOG_FILE%"
echo [rc-simulator] WslRepoPath=%WSL_REPO_PATH%>> "%LOG_FILE%"
echo.>> "%LOG_FILE%"
copy /y "%LOG_FILE%" "%DESKTOP_LOG%" >nul 2>&1

set "DISTRO_ARG="
if not "%DISTRO%"=="" set "DISTRO_ARG=-d \"%DISTRO%\" "

REM Use bash -lc for a consistent shell.
wsl %DISTRO_ARG%-e bash -lc "set -euo pipefail; cd \"%WSL_REPO_PATH%\"; bash scripts/bootstrap_venv.sh --quiet; exec .venv/bin/rc-simulator" >> "%LOG_FILE%" 2>&1
set "EXITCODE=%ERRORLEVEL%"

echo.>> "%LOG_FILE%"
echo ExitCode=%EXITCODE%>> "%LOG_FILE%"
copy /y "%LOG_FILE%" "%DESKTOP_LOG%" >nul 2>&1

if not "%EXITCODE%"=="0" (
  echo [rc-simulator] FAILED. Opening log: %LOG_FILE%
  start "" notepad "%LOG_FILE%" >nul 2>&1
  pause
  exit /b %EXITCODE%
)

exit /b 0

