param([string]$Distro = "")
$ErrorActionPreference = "Stop"

function Invoke-WSLRoot([string[]]$CommandArgs) {
  if ($Distro) { & wsl -d $Distro -u root -- @CommandArgs } else { & wsl -u root -- @CommandArgs }
  if ($LASTEXITCODE -ne 0) { throw "WSL root command failed: $($CommandArgs -join ' ')" }
}
function Invoke-WSLUser([string[]]$CommandArgs) {
  if ($Distro) { & wsl -d $Distro -- @CommandArgs } else { & wsl -- @CommandArgs }
  if ($LASTEXITCODE -ne 0) { throw "WSL user command failed: $($CommandArgs -join ' ')" }
}

$wslUser = if ($Distro) { (& wsl -d $Distro sh -lc "id -un").Trim() } else { (& wsl sh -lc "id -un").Trim() }
if (-not $wslUser) { throw "Could not determine default WSL user." }

Write-Host "Configuring WSL2 systemd for persistent local runtimes..."
Invoke-WSLRoot -CommandArgs @("sh","-lc","printf '[boot]\nsystemd=true\n' > /etc/wsl.conf")

# A shutdown is required for a newly enabled systemd setting to take effect. This is safe here:
# bootstrap has not started any inference process yet.
$systemdReady = $false
try {
  if ($Distro) { & wsl -d $Distro sh -lc "systemctl is-system-running >/dev/null 2>&1 || systemctl is-system-running | grep -Eq 'running|degraded'" }
  else { & wsl sh -lc "systemctl is-system-running >/dev/null 2>&1 || systemctl is-system-running | grep -Eq 'running|degraded'" }
  $systemdReady = ($LASTEXITCODE -eq 0)
} catch { $systemdReady = $false }
if (-not $systemdReady) {
  Write-Host "Restarting WSL once so systemd becomes active..."
  & wsl --shutdown
  Start-Sleep -Seconds 2
  if ($Distro) { & wsl -d $Distro sh -lc "true" } else { & wsl sh -lc "true" }
}

Write-Host "Installing base build/media packages..."
Invoke-WSLRoot -CommandArgs @("apt-get", "update")
Invoke-WSLRoot -CommandArgs @("apt-get","install","-y","build-essential","cmake","ninja-build","git","git-lfs","curl","wget","jq","ffmpeg","sox","libsndfile1","libgl1","libglib2.0-0","pkg-config","python3","python3-venv","python3-dev","ca-certificates","gnupg","ripgrep")

# DeepSeek Harness currently requires Node ^22.19 or >=24 and pins pnpm 11.7.
# Install the current Node 24 line in WSL instead of Ubuntu's older archive package.
Invoke-WSLRoot -CommandArgs @("sh","-lc","curl -fsSL https://deb.nodesource.com/setup_24.x | bash -")
Invoke-WSLRoot -CommandArgs @("apt-get","install","-y","nodejs")
Invoke-WSLRoot -CommandArgs @("npm","install","--global","pnpm@11.7.0")

# OpenShell's supported local driver needs a current Docker/Podman runtime. Prefer an already
# usable Docker engine; otherwise install current Docker Engine from Docker's official installer.
$dockerOk = $false
try {
  if ($Distro) { & wsl -d $Distro sh -lc "docker version >/dev/null 2>&1" } else { & wsl sh -lc "docker version >/dev/null 2>&1" }
  $dockerOk = ($LASTEXITCODE -eq 0)
} catch { $dockerOk = $false }
if (-not $dockerOk) {
  Write-Host "Installing current Docker Engine inside WSL for the hardened execution plane..."
  Invoke-WSLRoot -CommandArgs @("sh","-lc","curl -fsSL https://get.docker.com | sh")
  Invoke-WSLRoot -CommandArgs @("systemctl","enable","--now","docker")
  Invoke-WSLRoot -CommandArgs @("usermod","-aG","docker",$wslUser)
  try { Invoke-WSLRoot -CommandArgs @("loginctl","enable-linger",$wslUser) } catch { Write-Warning "Could not enable user lingering; OpenShell will be rechecked at runtime." }
  # New WSL invocations pick up the updated docker group membership.
  Start-Sleep -Seconds 1
}

Invoke-WSLUser -CommandArgs @("sh","-lc","docker version >/dev/null 2>&1")
Write-Host "WSL base + Docker execution substrate provisioned for user '$wslUser'."
