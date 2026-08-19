#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
PROFILE="${2:-workstation}"
source "$ROOT/scripts/runtime_env.sh"

case "$PROFILE" in
  core) required_gb=220 ;;
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
if ((available_gb < required_gb)); then
  echo "Insufficient WSL-native disk: ${available_gb}GB free; ${required_gb}GB required for $PROFILE." >&2
  exit 2
fi
echo "Storage OK: ${available_gb}GB free at $SOAI_DATA_HOME (${required_gb}GB required for $PROFILE)."
