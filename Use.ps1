param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Task,
  [Parameter(Mandatory = $true)]
  [string]$Workspace,
  [int]$MaxSteps = 12,
  [string]$Distro = "Ubuntu-24.04"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
. "$Root\scripts\common.ps1" -Distro $Distro
Assert-SoaiKernelEnvironment
Set-Location $Root

function Test-AchillesRouter {
  try {
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:18080/v1/models" -TimeoutSec 3
    return @($response.data | ForEach-Object { $_.id }) -contains "qwen35-9b"
  } catch {
    return $false
  }
}

if (-not (Test-AchillesRouter)) {
  $occupied = (Test-NetConnection -ComputerName 127.0.0.1 -Port 18080 -WarningAction SilentlyContinue).TcpTestSucceeded
  if ($occupied) {
    throw "Port 18080 is occupied by a service that is not the Achilles llama.cpp router."
  }

  $linuxPath = Get-SoaiWslRoot
  $statePath = Join-Path (Get-SoaiWslDataUnc) "state"
  $routerProcess = Start-Process -FilePath "wsl.exe" `
    -ArgumentList @("-d", $Distro, "--", "$linuxPath/scripts/start_llama_router.sh", $linuxPath) `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $statePath "llama-router.stdout.log") `
    -RedirectStandardError (Join-Path $statePath "llama-router.stderr.log")
  if ($null -eq $routerProcess) { throw "Failed to launch the llama.cpp router." }
  $routerProcess.Dispose()

  for ($attempt = 0; $attempt -lt 60 -and -not (Test-AchillesRouter); $attempt++) {
    Start-Sleep -Seconds 1
  }
  if (-not (Test-AchillesRouter)) {
    throw "The llama.cpp router did not become ready. Check llama-router.stderr.log in the WSL state directory."
  }
}

$workspacePath = (Resolve-Path -LiteralPath $Workspace).Path
$subject = "achilles-dev"

& $SoaiKernelPython -m sovereign_ai.cli workspace add $workspacePath | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not authorize workspace $workspacePath." }

& $SoaiKernelPython -m sovereign_ai.cli grant $subject write workspace --ttl-seconds 3600 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not issue the temporary workspace grant." }

& $SoaiKernelPython -m sovereign_ai.cli run $Task --workspace $workspacePath --max-steps $MaxSteps --subject $subject --capability coding --mode smart
if ($LASTEXITCODE -ne 0) { throw "The agent run did not complete successfully." }
