param([switch]$NoSearch, [string]$Distro = "Ubuntu-24.04")
$ErrorActionPreference = "Stop"
& "$PSScriptRoot\scripts\start.ps1" -NoSearch:$NoSearch -Distro $Distro
