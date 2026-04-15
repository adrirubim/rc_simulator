param(
  [string]$Distro = "",
  [string]$ShortcutName = "RC Simulator.lnk",
  [string]$WslRepoPath = ""
)

$ErrorActionPreference = "Stop"

$repoWin = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
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
    $k = ($c ?? "").Trim().ToLowerInvariant()
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
exec .venv/bin/python -m rc_simulator
"@.Trim()

$distroArg = ""
if ($Distro.Trim().Length -gt 0) {
  $distroArg = "-d `"$Distro`" "
}

# Use bash -lc to ensure a consistent shell.
$args = "$distroArg-e bash -lc " + ('"' + ($bashCommand -replace '"','\"') + '"')

$shortcutPath = Pick-DesktopPath -Name $ShortcutName

$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($shortcutPath)
$sc.TargetPath = $wsl
$sc.Arguments = $args
$sc.WorkingDirectory = (Split-Path -Parent $shortcutPath)
$sc.WindowStyle = 1
$sc.Description = "Launch RC Simulator via WSL"

# Windows shortcuts don't support SVG icons. If an .ico is present, use it.
$iconPath = Join-Path $repoWin "assets\\icons\\rc-simulator.ico"
if (Test-Path -LiteralPath $iconPath) {
  $sc.IconLocation = "$iconPath,0"
}
$sc.Save()

Write-Output "Created shortcut: $shortcutPath"

