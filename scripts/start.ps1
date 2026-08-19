param([switch]$NoSearch, [string]$Distro = "Ubuntu-24.04")
$ErrorActionPreference="Stop"
$Root=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. "$PSScriptRoot\common.ps1" -Distro $Distro
Assert-SoaiKernelEnvironment
Set-Location $Root
& $SoaiKernelPython scripts/configure_infra.py
if ($LASTEXITCODE -ne 0) { throw "Infrastructure configuration failed." }
$linuxPath=Get-SoaiWslRoot
$wslData=Get-SoaiWslDataUnc
$env:SOVEREIGN_MODEL_DIR=Join-Path $wslData "models"
$env:SOVEREIGN_CACHE_DIR=Join-Path $wslData "cache"
$env:SOVEREIGN_RUNTIME_DIR=Join-Path $wslData "runtimes"

function Port-Up([int]$Port) {
  try { return (Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded } catch { return $false }
}

function Expected-Router {
  try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:18080/v1/models" -TimeoutSec 3
    $ids = @($response.data | ForEach-Object { $_.id })
    return ($ids -contains "qwen35-9b") -and ($ids -contains "qwen38-27b")
  } catch { return $false }
}

if ((Port-Up 18080) -and -not (Expected-Router)) {
  throw "Port 18080 is occupied by a service that is not this installation's llama.cpp router."
}
if (-not (Port-Up 18080)) {
  & wsl -d $Distro bash -lc "cd '$linuxPath' && source scripts/runtime_env.sh && nohup ./scripts/start_llama_router.sh '$linuxPath' > \"`$SOAI_STATE_DIR/llama-router.log\" 2>&1 &"
  if ($LASTEXITCODE -ne 0) { throw "Failed to launch llama.cpp router." }
  $ready = $false
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Seconds 1
    if (Expected-Router) { $ready = $true; break }
  }
  if (-not $ready) { throw "The sovereign llama.cpp router did not become ready on port 18080." }
}

if (-not (Port-Up 7867)) {
  & wsl -d $Distro bash -lc "cd '$linuxPath' && source scripts/runtime_env.sh && nohup ./scripts/start_wangp_worker.sh '$linuxPath' > \"`$SOAI_STATE_DIR/wangp-worker.log\" 2>&1 &"
  if ($LASTEXITCODE -ne 0) { Write-Warning "WanGP worker launch failed; media routes will report unavailable until repaired." }
}

if (-not $NoSearch) {
  $started=$false
  if (Get-Command docker -ErrorAction SilentlyContinue) {
    & docker version *> $null
    if ($LASTEXITCODE -eq 0) {
      & docker compose -f infra/docker-compose.yml up -d searxng | Out-Null
      if ($LASTEXITCODE -eq 0) { $started=$true }
    }
  }
  if (-not $started) {
    & wsl -d $Distro bash -lc "cd '$linuxPath' && docker version >/dev/null 2>&1 && docker compose -f infra/docker-compose.yml up -d searxng >/dev/null 2>&1"
    if ($LASTEXITCODE -ne 0) { Write-Warning "SearXNG did not start; browser/fetch adapters remain available." }
  }
}

& $SoaiKernelPython -m sovereign_ai.cli serve
