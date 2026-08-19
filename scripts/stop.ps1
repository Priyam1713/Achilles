$ErrorActionPreference="SilentlyContinue"
$Root=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Distro="Ubuntu-24.04"
. "$PSScriptRoot\common.ps1" -Distro $Distro
Set-Location $Root
$linuxPath=Get-SoaiWslRoot
& wsl -d $Distro bash -lc "source '$linuxPath/scripts/runtime_env.sh'; if [[ -f \"`$SOAI_STATE_DIR/llama-router.pid\" ]]; then pid=`$(cat \"`$SOAI_STATE_DIR/llama-router.pid\"); cmd=`$(tr '\0' ' ' < \"/proc/`$pid/cmdline\" 2>/dev/null || true); if [[ \"`$cmd\" == *\"`$SOAI_RUNTIME_DIR/llama.cpp\"* && \"`$cmd\" == *'--models-preset'* ]]; then kill \"`$pid\" || true; fi; rm -f \"`$SOAI_STATE_DIR/llama-router.pid\"; fi; pkill -f 'wangp_worker.py' || true; pkill -f 'specialist_worker.py' || true"
if (Get-Command docker -ErrorAction SilentlyContinue) {
  & docker compose -f infra/docker-compose.yml down *> $null
}
if ($linuxPath) { & wsl -d $Distro bash -lc "cd '$linuxPath' && docker compose -f infra/docker-compose.yml down >/dev/null 2>&1 || true" }
Write-Host "Local Sovereign AI services stopped."
