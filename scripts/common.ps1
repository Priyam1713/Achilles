param([string]$Distro = "Ubuntu-24.04")

$Script:SoaiRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Script:SoaiKernelHome = Join-Path $env:LOCALAPPDATA "sovereign-ai"
$Script:SoaiKernelEnv = Join-Path $Script:SoaiKernelHome "kernel-env"
$Script:SoaiKernelPython = Join-Path $Script:SoaiKernelEnv "Scripts\python.exe"
$Script:SoaiDistro = $Distro

function Get-SoaiWslRoot {
  $root = [System.IO.Path]::GetFullPath($Script:SoaiRoot)
  if ($root -notmatch '^([A-Za-z]):\\(.*)$') {
    throw "Repository must be on a local Windows drive for WSL translation: $root"
  }
  $drive = $Matches[1].ToLowerInvariant()
  $tail = $Matches[2].Replace('\', '/')
  return "/mnt/$drive/$tail"
}

function Invoke-SoaiWsl([string]$Command) {
  & wsl -d $Script:SoaiDistro bash -lc $Command
  if ($LASTEXITCODE -ne 0) { throw "WSL command failed with exit code $LASTEXITCODE" }
}

function Get-SoaiWslDataUnc {
  $user = (& wsl -d $Script:SoaiDistro -- id -un).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $user) { throw "Could not determine the WSL user." }
  return "\\wsl.localhost\$Script:SoaiDistro\home\$user\.local\share\sovereign-ai"
}

function Assert-SoaiKernelEnvironment {
  if (-not (Test-Path -LiteralPath $Script:SoaiKernelPython)) {
    throw "Kernel environment is missing. Run .\Install.ps1 first."
  }
}
