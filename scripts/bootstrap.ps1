param(
  [switch]$InstallModels,
  [switch]$IncludeGated,
  [switch]$SkipSpecialists,
  [switch]$SkipWSLProvision,
  [switch]$SkipModelSmoke,
  [ValidateSet("core", "workstation", "full")][string]$Profile = "workstation",
  [string]$Distro = "Ubuntu-24.04"
)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\common.ps1" -Distro $Distro
$Root = $SoaiRoot
Set-Location $Root

function Assert-Native([string]$Step) {
  if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}

function Find-Python312 {
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe")
  )
  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }
  foreach ($name in @("py", "python")) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if (-not $command) { continue }
    try {
      if ($name -eq "py") {
        $resolved = (& py -3.12 -c "import sys; print(sys.executable)").Trim()
      } else {
        $resolved = (& $command.Source -c "import sys; print(sys.executable)").Trim()
      }
      if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $resolved)) { return $resolved }
    } catch { continue }
  }
  return $null
}

Write-Host "[1/10] Checking Windows + WSL substrate..."
if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
  throw "WSL2 is required. Run 'wsl --install -d $Distro', reboot, then rerun Install.ps1."
}
& wsl -d $Distro --status | Out-Null
Assert-Native "WSL $Distro status"
$linuxPath = Get-SoaiWslRoot

Write-Host "[2/10] Preparing native Windows control-plane Python..."
$python = Find-Python312
if (-not $python) {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "Python 3.12 and winget are unavailable. Install Python 3.12, then rerun."
  }
  & winget install --id Python.Python.3.12 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
  Assert-Native "Python 3.12 installation"
  $python = Find-Python312
}
if (-not $python) { throw "Python 3.12 installation completed but python.exe could not be located." }
& $python -m pip install --user --upgrade uv
Assert-Native "uv installation"
New-Item -ItemType Directory -Force -Path $SoaiKernelHome | Out-Null
$env:UV_PROJECT_ENVIRONMENT = $SoaiKernelEnv
& $python -m uv sync --extra dev --extra tools --extra windows
Assert-Native "Windows kernel environment sync"

Write-Host "[3/10] Verifying the actual workstation..."
& $SoaiKernelPython scripts/verify_host.py --strict-target --min-free-disk-gb 50
Assert-Native "host preflight"
& $SoaiKernelPython scripts/configure_infra.py
Assert-Native "infrastructure configuration"

if (-not $SkipWSLProvision) {
  Write-Host "[4/10] Provisioning WSL build, media, Docker and sandbox dependencies..."
  & powershell -ExecutionPolicy Bypass -File "$Root\scripts\provision_wsl.ps1" -Distro $Distro
  Assert-Native "WSL provisioning"
} else { Write-Host "[4/10] WSL base provisioning skipped." }

Write-Host "[5/10] Creating a WSL-native control-tools environment..."
& wsl -d $Distro bash -lc "cd '$linuxPath' && source scripts/runtime_env.sh && export PATH=\"`$HOME/.local/bin:`$PATH\" && (command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh); export PATH=\"`$HOME/.local/bin:`$PATH\"; export UV_PROJECT_ENVIRONMENT=\"`$SOAI_ENV_DIR/kernel\"; uv sync --extra dev --extra tools --link-mode copy"
Assert-Native "WSL control-tools environment"
if ($InstallModels) {
  & wsl -d $Distro bash -lc "cd '$linuxPath' && ./scripts/verify_storage.sh '$linuxPath' '$Profile'"
  Assert-Native "WSL-native model storage preflight"
  & wsl -d $Distro bash -lc "cd '$linuxPath' && source scripts/runtime_env.sh && \"`$SOAI_ENV_DIR/kernel/bin/python\" scripts/check_release_radar.py --state-dir \"`$SOAI_STATE_DIR\""
  Assert-Native "official release radar"
  & wsl -d $Distro bash -lc "cd '$linuxPath' && source scripts/runtime_env.sh && \"`$SOAI_ENV_DIR/kernel/bin/python\" scripts/verify_sources.py --profile '$Profile' --state-dir \"`$SOAI_STATE_DIR\""
  Assert-Native "upstream model source audit"
}

Write-Host "[6/10] Installing replaceable WSL runtimes and building llama.cpp for CUDA..."
& wsl -d $Distro bash -lc "cd '$linuxPath' && ./scripts/install_wsl_runtimes.sh '$linuxPath'"
Assert-Native "runtime installation"

if (-not $SkipSpecialists) {
  Write-Host "[7/10] Installing isolated specialist dependency islands..."
  & wsl -d $Distro bash -lc "cd '$linuxPath' && ./scripts/install_specialists.sh '$linuxPath' --profile '$Profile'"
  Assert-Native "specialist installation"
} else { Write-Host "[7/10] Specialist installation skipped." }

if ($InstallModels) {
  Write-Host "[8/10] Syncing the '$Profile' model profile to WSL-native storage..."
  $gated = if ($IncludeGated) { "--include-gated" } else { "" }
  & wsl -d $Distro bash -lc "cd '$linuxPath' && source scripts/runtime_env.sh && \"`$SOAI_ENV_DIR/kernel/bin/python\" scripts/sync_models.py --profile '$Profile' --model-dir \"`$SOAI_MODEL_DIR\" --state-dir \"`$SOAI_STATE_DIR\" $gated"
  Assert-Native "model synchronization"

  Write-Host "[9/10] Converting/quantizing cognition models and smoke-testing inference..."
  $skipSmoke = if ($SkipModelSmoke) { "SOAI_SKIP_LLAMA_SMOKE=1" } else { "SOAI_SKIP_LLAMA_SMOKE=0" }
  & wsl -d $Distro bash -lc "cd '$linuxPath' && source scripts/runtime_env.sh && $skipSmoke ./scripts/prepare_llama_models.sh '$linuxPath'"
  Assert-Native "Qwen GGUF preparation"
  if (-not $SkipSpecialists) {
    & wsl -d $Distro bash -lc "cd '$linuxPath' && source scripts/runtime_env.sh && \"`$SOAI_ENV_DIR/kernel/bin/python\" scripts/prewarm_specialists.py --strict --profile '$Profile'"
    Assert-Native "specialist prewarm"
  }
} else {
  Write-Host "[8/10] Model downloads skipped. Rerun with -InstallModels when ready."
  Write-Host "[9/10] Model conversion/smoke tests skipped."
}

Write-Host "[10/10] Validating kernel contracts, tests and installation health..."
& $SoaiKernelPython -m sovereign_ai.cli preflight
Assert-Native "kernel preflight"
& $SoaiKernelPython -m pytest -q
Assert-Native "kernel tests"
$strict = if ($InstallModels) { "--strict" } else { "" }
& wsl -d $Distro bash -lc "cd '$linuxPath' && source scripts/runtime_env.sh && \"`$SOAI_ENV_DIR/kernel/bin/python\" scripts/doctor.py $strict"
Assert-Native "installation doctor"
Write-Host "Bootstrap complete. Run .\Run.ps1 -Distro $Distro to start the local stack."
