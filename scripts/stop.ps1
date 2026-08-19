$ErrorActionPreference="SilentlyContinue"
$Root=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Distro="Ubuntu-24.04"
. "$PSScriptRoot\common.ps1" -Distro $Distro
Set-Location $Root
$linuxPath=Get-SoaiWslRoot
& wsl -d $Distro bash -lc "pkill -f 'llama-server.*models-preset' || true; pkill -f 'wangp_worker.py' || true; pkill -f 'specialist_worker.py' || true"
if (Get-Command docker -ErrorAction SilentlyContinue) {
  & docker compose -f infra/docker-compose.yml down *> $null
}
if ($linuxPath) { & wsl -d $Distro bash -lc "cd '$linuxPath' && docker compose -f infra/docker-compose.yml down >/dev/null 2>&1 || true" }
Write-Host "Local Sovereign AI services stopped."
