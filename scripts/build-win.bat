@echo off
setlocal EnableExtensions DisableDelayedExpansion

rem Build RC Simulator Windows executable using PyInstaller.
rem - Installs PyInstaller into .venv if missing
rem - Builds from rc-simulator.spec
rem - Outputs into dist\

for %%I in ("%~dp0..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%" >nul

set "PY_EXE="
set "PY_ARGS="
if exist ".venv\Scripts\python.exe" (
  set "PY_EXE=.venv\Scripts\python.exe"
) else (
  py -3 -c "import sys" >nul 2>&1
  if errorlevel 1 (
    set "PY_EXE=python"
  ) else (
    set "PY_EXE=py"
    set "PY_ARGS=-3"
  )
)

echo Using Python: %PY_EXE% %PY_ARGS%

call %PY_EXE% %PY_ARGS% -m pip --version >nul 2>&1
if errorlevel 1 (
  echo pip not found. Attempting ensurepip...
  call %PY_EXE% %PY_ARGS% -m ensurepip --upgrade >nul 2>&1
  call %PY_EXE% %PY_ARGS% -m pip --version >nul 2>&1
  if errorlevel 1 (
    echo ERROR: pip is not available for %PY_EXE% %PY_ARGS%.
    echo        Activate your venv or install pip, then retry.
    popd >nul
    exit /b 1
  )
)

call %PY_EXE% %PY_ARGS% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
  echo PyInstaller not found in this environment. Installing...
  call %PY_EXE% %PY_ARGS% -m pip install --upgrade pip
  if errorlevel 1 (
    echo ERROR: Failed to upgrade pip.
    popd >nul
    exit /b 1
  )
  rem Install build deps from pyproject.toml (source of truth).
  call %PY_EXE% %PY_ARGS% -m pip install "%REPO_ROOT%[winbuild]"
  if errorlevel 1 (
    echo ERROR: Failed to install build dependencies (.[winbuild]).
    popd >nul
    exit /b 1
  )
)

if not exist "rc-simulator.spec" (
  echo ERROR: rc-simulator.spec not found in repo root.
  popd >nul
  exit /b 1
)

echo Building...
call %PY_EXE% %PY_ARGS% -m PyInstaller rc-simulator.spec --clean
if errorlevel 1 (
  echo ERROR: Build failed.
  popd >nul
  exit /b 1
)

echo Build complete! Check the /dist folder for rc-simulator.exe
popd >nul
exit /b 0

