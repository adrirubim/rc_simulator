param(
  [string]$ShortcutName = "RC Simulator.lnk"
)

$ErrorActionPreference = "Stop"

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop $ShortcutName

if (Test-Path -LiteralPath $shortcutPath) {
  Remove-Item -LiteralPath $shortcutPath -Force
  Write-Output "Removed shortcut: $shortcutPath"
} else {
  Write-Output "Shortcut not found: $shortcutPath"
}

