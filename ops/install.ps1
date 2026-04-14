param(
  [string]$Distro = "",
  [string]$WslRepoPath = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Normalize-FileSystemPath([string]$PathValue) {
  $p = ($PathValue ?? "").Trim()
  $prefix = "Microsoft.PowerShell.Core\FileSystem::"
  if ($p.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $p.Substring($prefix.Length)
  }
  return $p
}

$repoRoot = Normalize-FileSystemPath (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Get-DefaultDistro() {
  try {
    $out = & wsl.exe -l -q 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) {
      foreach ($line in $out) {
        $d = ($line ?? "").ToString().Trim()
        if ($d.Length -gt 0) { return $d }
      }
    }
  } catch {}
  return ""
}

function Sync-Repo-ToWslCache([string]$RepoWinPath, [string]$DistroName) {
  $repoWinPath = Normalize-FileSystemPath $RepoWinPath
  if (-not (Test-Path -LiteralPath $repoWinPath)) {
    throw "Repo path not found: $repoWinPath"
  }

  $target = "~/.cache/rc_simulator/repo"
  if ($DryRun) {
    Write-Output ("[dry-run] Sync repo to WSL cache: " + $target)
    return $target
  }

  if ($DistroName.Trim().Length -eq 0) {
    $DistroName = Get-DefaultDistro
  }

  if ($DistroName.Trim().Length -eq 0) {
    throw "WSL distro not specified and none could be inferred. Pass -Distro <name>."
  }

  Write-Output ("Syncing repo into WSL cache (" + $DistroName + "): " + $target)

  # Stream a tarball into WSL to avoid UNC/provider-path issues and to work from any location
  # (USB drive, network share, etc.). The shortcut will always run from the cached copy.
  $wslExtract = "mkdir -p ~/.cache/rc_simulator/repo && tar -x -f - -C ~/.cache/rc_simulator/repo"
  $tarArgs = @(
    "-c",
    "-f",
    "-",
    "--exclude=.venv",
    "--exclude=venv",
    "--exclude=__pycache__",
    "--exclude=*.egg-info",
    "--exclude=.pytest_cache",
    "--exclude=.ruff_cache",
    "--exclude=.mypy_cache",
    "-C",
    $repoWinPath,
    "."
  )

  # Use cmd.exe to avoid PowerShell pipeline quirks with native executables.
  $tarCmd = "tar " + ($tarArgs | ForEach-Object { '"' + ($_ -replace '"','\"') + '"' } | Join-String -Separator " ")
  $wslCmd = "wsl -d " + ('"' + ($DistroName -replace '"','\"') + '"') + " -e bash -lc " + ('"' + ($wslExtract -replace '"','\"') + '"')
  cmd.exe /c ($tarCmd + " | " + $wslCmd) | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to sync repo into WSL cache (tar|wsl pipeline)."
  }

  return $target
}

function Run-Step([string]$Label, [scriptblock]$Action) {
  if ($DryRun) {
    Write-Output ("[dry-run] " + $Label)
    return
  }
  Write-Output $Label
  & $Action
}

# Windows installer focuses on the Windows UX: create desktop shortcut that launches via WSL.
$shortcutScript = ""
if ($WslRepoPath.Trim().Length -gt 0) {
  $candidate = Join-Path $PSScriptRoot "install_shortcut.ps1"
  if (Test-Path -LiteralPath $candidate) {
    $shortcutScript = $candidate
  }
}
if ($shortcutScript.Trim().Length -eq 0) {
  $shortcutScript = Join-Path $repoRoot "ops\windows\install_shortcut.ps1"
}
$shortcutScript = Normalize-FileSystemPath $shortcutScript
if (-not (Test-Path -LiteralPath $shortcutScript)) {
  throw "Missing script: $shortcutScript"
}

Run-Step "Installing Windows shortcut (via WSL)..." {
  $args = @{}
  $d = $Distro
  if ($d.Trim().Length -eq 0) {
    $d = Get-DefaultDistro
  }
  if ($d.Trim().Length -gt 0) {
    $args["Distro"] = $d
  }

  $repoForShortcut = $WslRepoPath
  if ($repoForShortcut.Trim().Length -eq 0) {
    $repoForShortcut = Sync-Repo-ToWslCache -RepoWinPath $repoRoot -DistroName $d
  }
  $args["WslRepoPath"] = $repoForShortcut

  $scriptPath = (Get-Item -LiteralPath $shortcutScript -ErrorAction Stop).FullName
  & $scriptPath @args
}

Write-Output "Done."

