param(
  [string]$Distro = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Run-Step([string]$Label, [scriptblock]$Action) {
  if ($DryRun) {
    Write-Output ("[dry-run] " + $Label)
    return
  }
  Write-Output $Label
  & $Action
}

# Windows installer focuses on the Windows UX: create desktop shortcut that launches via WSL.
$shortcutScript = Join-Path $repoRoot "ops\windows\install_shortcut.ps1"
if (-not (Test-Path -LiteralPath $shortcutScript)) {
  throw "Missing script: $shortcutScript"
}

Run-Step "Installing Windows shortcut (via WSL)..." {
  if ($Distro.Trim().Length -gt 0) {
    powershell -NoProfile -ExecutionPolicy Bypass -File $shortcutScript -Distro $Distro
  } else {
    powershell -NoProfile -ExecutionPolicy Bypass -File $shortcutScript
  }
}

Write-Output "Done."

