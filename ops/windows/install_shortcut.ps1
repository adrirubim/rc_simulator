param(
  [string]$Distro = "",
  [string]$ShortcutName = "RC Simulator.lnk",
  [string]$WslRepoPath = ""
)

$ErrorActionPreference = "Stop"

function Normalize-FileSystemPath([string]$PathValue) {
  $p = ([string]$PathValue).Trim()
  $prefix = "Microsoft.PowerShell.Core\FileSystem::"
  if ($p.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $p.Substring($prefix.Length)
  }
  return $p
}

$repoWin = Normalize-FileSystemPath (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not (Test-Path -LiteralPath $repoWin)) {
  throw "Repo path not found: $repoWin"
}

$wsl = (Get-Command wsl.exe -ErrorAction Stop).Source

function Get-DesktopCandidates() {
  $candidates = New-Object System.Collections.Generic.List[string]

  # Most reliable (respects redirection, incl. OneDrive Known Folder Move).
  try {
    $dd = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
    if ($dd) { [void]$candidates.Add($dd) }
  } catch {}

  # Common fallback when Desktop is redirected.
  try {
    $od = $env:OneDrive
    if ($od) {
      $p = Join-Path $od "Desktop"
      [void]$candidates.Add($p)
    }
  } catch {}

  # Classic local desktop.
  try {
    $p = Join-Path $env:USERPROFILE "Desktop"
    [void]$candidates.Add($p)
  } catch {}

  # De-dup while preserving order.
  $seen = @{}
  $out = @()
  foreach ($c in $candidates) {
    # PowerShell 5.1 compatibility: no null-coalescing operator (??).
    $v = ""
    if ($null -ne $c) { $v = [string]$c }
    $k = $v.Trim().ToLowerInvariant()
    if ($k.Length -eq 0) { continue }
    if ($seen.ContainsKey($k)) { continue }
    $seen[$k] = $true
    $out += $c
  }
  return $out
}

function Pick-DesktopPath([string]$Name) {
  $candidates = Get-DesktopCandidates
  foreach ($d in $candidates) {
    try {
      if (-not (Test-Path -LiteralPath $d)) { continue }
      # Best-effort write test to avoid silent failures on redirected/locked folders.
      $probe = Join-Path $d (".rc_simulator_write_probe_" + [Guid]::NewGuid().ToString("N") + ".tmp")
      Set-Content -LiteralPath $probe -Value "ok" -Encoding ASCII -ErrorAction Stop
      Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
      return (Join-Path $d $Name)
    } catch {
      continue
    }
  }
  $list = ($candidates | ForEach-Object { "- " + $_ }) -join "`n"
  throw "Unable to find a writable Desktop folder. Tried:`n$list"
}

function Get-WslRepoPath([string]$RepoWin, [string]$Distro, [string]$ExplicitWslPath) {
  if ($ExplicitWslPath.Trim().Length -gt 0) {
    return $ExplicitWslPath.Trim()
  }

  # If running from a WSL UNC path, convert it deterministically to a Linux path.
  # Example: \\wsl.localhost\Ubuntu\var\www\rc_simulator -> /var/www/rc_simulator
  if ($RepoWin.StartsWith("\\wsl.localhost\", [System.StringComparison]::OrdinalIgnoreCase)) {
    $prefix = "\\wsl.localhost\"
    $rest = $RepoWin.Substring($prefix.Length)
    $parts = $rest.Split("\", 2, [System.StringSplitOptions]::None)
    if ($parts.Length -ge 2) {
      $uncDistro = $parts[0]
      $pathPart = $parts[1].Replace("\", "/")
      if ($Distro.Trim().Length -eq 0) {
        $Distro = $uncDistro
      }
      return "/" + $pathPart.TrimStart("/")
    }
  }

  # Fallback: ask WSL to translate the Windows path (works for local drive paths).
  $distroArg = ""
  if ($Distro.Trim().Length -gt 0) {
    $distroArg = "-d `"$Distro`" "
  }
  $cmd = "wsl " + $distroArg + "-e bash -lc " + '"' + ("wslpath -a " + ('"' + ($RepoWin -replace '"','\"') + '"')) + '"'
  $out = cmd.exe /c $cmd 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $out) {
    throw "Unable to determine WSL path for repo. RepoWin=$RepoWin Distro=$Distro"
  }
  return ($out | Select-Object -First 1).Trim()
}

$wslRepoPath = Get-WslRepoPath -RepoWin $repoWin -Distro $Distro -ExplicitWslPath $WslRepoPath

$bashCommand = @"
set -euo pipefail
cd "$wslRepoPath"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -e . >/dev/null
test -x .venv/bin/rc-simulator
"@.Trim()

$wslArgs = @()
if ($Distro.Trim().Length -gt 0) {
  $wslArgs += @("-d", $Distro)
}
$wslArgs += @("-e", "bash", "-lc", $bashCommand)

try {
  Write-Output "Preparing WSL venv (editable install)..."
  & $wsl @wslArgs | Out-Null
} catch {
  throw "Failed to prepare WSL environment. Try running the shortcut once, or run: wsl -e bash -lc `"$bashCommand`""
}

$distroArg = ""
if ($Distro.Trim().Length -gt 0) {
  $distroArg = "-d `"$Distro`" "
}

$shortcutPath = Pick-DesktopPath -Name $ShortcutName
$runnerCmd = Join-Path $repoWin "ops\\windows\\run_rc_simulator.cmd"
if (-not (Test-Path -LiteralPath $runnerCmd)) {
  throw "Missing runner script: $runnerCmd"
}

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($shortcutPath)
$cmdExe = (Get-Command cmd.exe -ErrorAction Stop).Source
$sc.TargetPath = $cmdExe
# Shortcuts require an executable target; run the wrapper via cmd.exe /c.
$d = ""
if ($null -ne $Distro) { $d = [string]$Distro }
$w = ""
if ($null -ne $wslRepoPath) { $w = [string]$wslRepoPath }
# Use /k so the console stays open and errors are visible.

# cmd.exe is unreliable with UNC targets (\\wsl.localhost\...). Cache the runner script locally.
try {
  $cacheDir = Join-Path $env:LOCALAPPDATA "rc_simulator"
  New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
  $cachedRunner = Join-Path $cacheDir "run_rc_simulator.cmd"
  Copy-Item -LiteralPath $runnerCmd -Destination $cachedRunner -Force
  # Persist args for the runner (avoids cmd.exe quoting edge cases).
  $cfg = Join-Path $cacheDir "runner.env"
  Set-Content -LiteralPath $cfg -Value @(
    "DISTRO=$d"
    "WSL_REPO_PATH=$w"
  ) -Encoding ASCII -Force
} catch {
  $cachedRunner = $runnerCmd
}

# cmd.exe parsing is extremely picky when the command starts with a quoted path.
# Keep the shortcut arguments minimal and load args from runner.env.
$runnerEsc = ($cachedRunner -replace '"','\"')
$sc.Arguments = '/k ""' + $runnerEsc + '""'
$sc.WorkingDirectory = (Split-Path -Parent $shortcutPath)
$sc.WindowStyle = 1
$sc.Description = "Launch RC Simulator via WSL (with log on failure)"

# Windows shortcuts don't support SVG icons. If an .ico is present, use it.
$iconPath = Join-Path $repoWin "src\\rc_simulator\\resources\\icons\\rc-simulator.ico"
if (-not (Test-Path -LiteralPath $iconPath)) {
  $iconPath = Join-Path $repoWin "assets\\icons\\rc-simulator.ico"
}
if (Test-Path -LiteralPath $iconPath) {
  # Shortcuts can fail to resolve icons from UNC/WSL paths.
  # Copy the icon to a local Windows folder and point the shortcut there.
  try {
    $cacheDir = Join-Path $env:LOCALAPPDATA "rc_simulator"
    New-Item -ItemType Directory -Force -Path $cacheDir | Out-Null
    $cachedIcon = Join-Path $cacheDir "rc-simulator.ico"
    Copy-Item -LiteralPath $iconPath -Destination $cachedIcon -Force
    $sc.IconLocation = "$cachedIcon,0"
  } catch {
    # Best-effort fallback.
    $sc.IconLocation = "$iconPath,0"
  }
}
$sc.Save()

Write-Output "Created shortcut: $shortcutPath"

