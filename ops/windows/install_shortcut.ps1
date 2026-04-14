param(
  [string]$Distro = "",
  [string]$ShortcutName = "RC Simulator.lnk"
)

$ErrorActionPreference = "Stop"

$repoWin = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not (Test-Path -LiteralPath $repoWin)) {
  throw "Repo path not found: $repoWin"
}

$wsl = (Get-Command wsl.exe -ErrorAction Stop).Source

$repoWinForWsl = $repoWin

$bashCommand = @"
set -euo pipefail
REPO_WIN="$repoWinForWsl"
cd "$(wslpath -a "$REPO_WIN")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -e . >/dev/null
exec .venv/bin/python -m rc_simulator
"@.Trim()

$distroArg = ""
if ($Distro.Trim().Length -gt 0) {
  $distroArg = "-d `"$Distro`" "
}

# Use bash -lc to ensure a consistent shell.
$args = "$distroArg-e bash -lc " + ('"' + ($bashCommand -replace '"','\"') + '"')

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop $ShortcutName

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($shortcutPath)
$sc.TargetPath = $wsl
$sc.Arguments = $args
$sc.WorkingDirectory = $repoWin
$sc.WindowStyle = 1
$sc.Description = "Launch RC Simulator via WSL"

# Windows shortcuts don't support SVG icons. If an .ico is present, use it.
$iconPath = Join-Path $repoWin "assets\\icons\\rc-simulator.ico"
if (Test-Path -LiteralPath $iconPath) {
  $sc.IconLocation = "$iconPath,0"
}
$sc.Save()

Write-Output "Created shortcut: $shortcutPath"

