param(
  [switch]$WithoutGatedModels,
  [switch]$SkipModelSmoke,
  [ValidateSet("core", "workstation", "full")][string]$Profile = "workstation",
  [string]$Distro = "Ubuntu-24.04"
)
$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process Bypass -Force
if ($WithoutGatedModels) {
  & "$PSScriptRoot\scripts\bootstrap.ps1" -InstallModels -SkipModelSmoke:$SkipModelSmoke -Profile $Profile -Distro $Distro
} else {
  & "$PSScriptRoot\scripts\bootstrap.ps1" -InstallModels -IncludeGated -SkipModelSmoke:$SkipModelSmoke -Profile $Profile -Distro $Distro
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Installation complete. Start with .\Run.ps1"
