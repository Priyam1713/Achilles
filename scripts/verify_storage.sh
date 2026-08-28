#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
PROFILE="${2:-core}"
source "$ROOT/scripts/runtime_env.sh"

case "$PROFILE" in
  core) required_gb=150 ;;
  workstation) required_gb=500 ;;
  full) required_gb=700 ;;
  *) echo "Unknown install profile: $PROFILE" >&2; exit 2 ;;
esac

case "$SOAI_DATA_HOME" in
  /mnt/*)
    echo "Refusing heavyweight storage on Windows-mounted path $SOAI_DATA_HOME." >&2
    echo "Use WSL-native ext4 storage (default: ~/.local/share/sovereign-ai)." >&2
    exit 2
    ;;
esac

available_kb="$(df -Pk "$SOAI_DATA_HOME" | awk 'NR==2 {print $4}')"
available_gb="$((available_kb / 1024 / 1024))"

# A sparse WSL2 VHDX reports the *virtual* filesystem capacity here. That number can be
# hundreds of GiB larger than the free space on the Windows volume that physically stores
# ext4.vhdx. Trusting only `df` can therefore green-light a download that fills the host
# drive. Resolve this distro's BasePath through the Lxss registry and gate on the smaller
# of the virtual and physical free-space figures.
host_available_gb=""
host_backing_path=""
if [[ -n "${WSL_DISTRO_NAME:-}" ]] && command -v powershell.exe >/dev/null 2>&1; then
  if [[ ! "$WSL_DISTRO_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "Refusing unexpected WSL distro name while resolving backing storage: $WSL_DISTRO_NAME" >&2
    exit 2
  fi
  host_backing_path="$({
    powershell.exe -NoProfile -NonInteractive -Command \
      "(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss\*' | Where-Object DistributionName -eq '$WSL_DISTRO_NAME').BasePath"
  } 2>/dev/null | tr -d '\r' | head -n 1)"
  if [[ "$host_backing_path" =~ ^([A-Za-z]): ]]; then
    backing_drive="${BASH_REMATCH[1]}"
    host_available_bytes="$({
      powershell.exe -NoProfile -NonInteractive -Command \
        "(Get-PSDrive -Name '$backing_drive').Free"
    } 2>/dev/null | tr -d '\r[:space:]')"
    if [[ "$host_available_bytes" =~ ^[0-9]+$ ]]; then
      host_available_gb="$((host_available_bytes / 1024 / 1024 / 1024))"
    fi
  fi

  if [[ -z "$host_available_gb" ]]; then
    echo "Unable to verify the Windows volume backing this WSL2 distro." >&2
    echo "Refusing a heavyweight download because df reports virtual VHDX capacity, not host capacity." >&2
    exit 2
  fi
fi

effective_available_gb="$available_gb"
if [[ -n "$host_available_gb" ]] && ((host_available_gb < effective_available_gb)); then
  effective_available_gb="$host_available_gb"
fi

if ((effective_available_gb < required_gb)); then
  echo "Insufficient physical storage: ${effective_available_gb}GiB effective free; ${required_gb}GiB required for $PROFILE." >&2
  echo "WSL virtual free: ${available_gb}GiB${host_available_gb:+; Windows backing free: ${host_available_gb}GiB at $host_backing_path}." >&2
  exit 2
fi
echo "Storage OK: ${effective_available_gb}GiB effective free at $SOAI_DATA_HOME (${required_gb}GiB required for $PROFILE)."
if [[ -n "$host_available_gb" ]]; then
  echo "  WSL virtual free: ${available_gb}GiB; Windows backing free: ${host_available_gb}GiB at $host_backing_path."
fi
