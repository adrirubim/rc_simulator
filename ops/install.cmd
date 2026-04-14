@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "LOG_FILE=%TEMP%\rc_simulator_install.log"
set "DISTRO="
set "WSL_REPO_PATH="
set "BOOT_DIR=%TEMP%\rc_simulator_installer"
set "BOOT_OPS=%BOOT_DIR%\ops"

REM If launched from a UNC path (e.g. \\wsl.localhost\...), cmd.exe won't use it as CWD.
REM pushd maps UNC to a temporary drive letter so relative paths and COM behave predictably.
pushd "%SCRIPT_DIR%" >nul 2>&1
if not "%ERRORLEVEL%"=="0" (
  echo [rc-simulator] ERROR: cannot access script directory: %SCRIPT_DIR%
  echo [rc-simulator] Tip: copy the repo to a local folder (e.g. C:\src\rc_simulator) and retry.
  pause
  exit /b 2
)

REM Best-effort: infer WSL distro from UNC path if present (\\wsl.localhost\<Distro>\...).
echo %SCRIPT_DIR% | findstr /I /B "\\\\wsl.localhost\\" >nul
if "%ERRORLEVEL%"=="0" (
  for /f "tokens=4 delims=\\" %%D in ("%SCRIPT_DIR%") do set "DISTRO=%%D"
  REM Convert UNC path to a Linux path and strip trailing \ops\
  set "UNC_AFTER_DISTRO=%SCRIPT_DIR%"
  for /f "tokens=1,* delims=\\" %%A in ("%UNC_AFTER_DISTRO%") do set "UNC_AFTER_DISTRO=%%B"
  for /f "tokens=1,* delims=\\" %%A in ("%UNC_AFTER_DISTRO%") do set "UNC_AFTER_DISTRO=%%B"
  for /f "tokens=1,* delims=\\" %%A in ("%UNC_AFTER_DISTRO%") do set "UNC_AFTER_DISTRO=%%B"
  for /f "tokens=1,* delims=\\" %%A in ("%UNC_AFTER_DISTRO%") do set "UNC_AFTER_DISTRO=%%B"
  set "UNC_AFTER_DISTRO=%UNC_AFTER_DISTRO:\=/%"
  REM UNC_AFTER_DISTRO is like var/www/rc_simulator/ops/
  if not "%UNC_AFTER_DISTRO%"=="" (
    if "%UNC_AFTER_DISTRO:~-4%"=="ops/" set "UNC_AFTER_DISTRO=%UNC_AFTER_DISTRO:~0,-4%"
  )
  set "WSL_REPO_PATH=/%UNC_AFTER_DISTRO%"
)

echo [rc-simulator] Running installer...> "%LOG_FILE%"
echo [rc-simulator] Log: %LOG_FILE%
echo.

REM Bootstrap to local temp folder to avoid UNC/provider-path issues.
if not exist "%BOOT_OPS%" mkdir "%BOOT_OPS%" >nul 2>&1
copy /y "install.ps1" "%BOOT_OPS%\install.ps1" >nul 2>&1
copy /y "windows\install_shortcut.ps1" "%BOOT_OPS%\install_shortcut.ps1" >nul 2>&1

if not "%DISTRO%"=="" (
  if not "%WSL_REPO_PATH%"=="" (
    powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%BOOT_OPS%\install.ps1" -Distro "%DISTRO%" -WslRepoPath "%WSL_REPO_PATH%" >> "%LOG_FILE%" 2>&1
  ) else (
    powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%BOOT_OPS%\install.ps1" -Distro "%DISTRO%" >> "%LOG_FILE%" 2>&1
  )
) else (
  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%BOOT_OPS%\install.ps1" >> "%LOG_FILE%" 2>&1
)
set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
  echo.
  echo [rc-simulator] INSTALL FAILED (exit code %EXITCODE%).
  echo [rc-simulator] See log: %LOG_FILE%
  echo.
  type "%LOG_FILE%"
  echo.
  popd >nul 2>&1
  start "" notepad "%LOG_FILE%" >nul 2>&1
  pause
  exit /b %EXITCODE%
)

echo.
echo [rc-simulator] Done. See log: %LOG_FILE%
echo.
popd >nul 2>&1
REM On success, surface evidence (double click can look like "it closed and did nothing").
start "" notepad "%LOG_FILE%" >nul 2>&1
start "" explorer.exe "%USERPROFILE%\Desktop" >nul 2>&1
timeout /t 2 >nul
exit /b 0

endlocal

