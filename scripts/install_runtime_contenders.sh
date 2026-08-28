#!/usr/bin/env bash
set -euo pipefail

# Build experimental inference engines without bloating the default workstation install.
# A contender is pinned and measurable; it is not promoted into routing by this script.

ROOT="${1:-$(pwd)}"
cd "$ROOT"
source "$ROOT/scripts/runtime_env.sh"
source "$ROOT/configs/runtime-sources.env"

for tool in git cmake python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing $tool" >&2; exit 1; }
done

checkout_pinned() {
  local url="$1" dir="$2" commit="$3"
  if [[ ! -d "$dir/.git" ]]; then
    git clone --filter=blob:none --no-checkout "$url" "$dir"
  elif ! git -C "$dir" diff --quiet || ! git -C "$dir" diff --cached --quiet; then
    echo "Refusing dirty runtime checkout: $dir" >&2
    exit 2
  fi
  git -C "$dir" fetch --depth 1 origin "$commit"
  git -C "$dir" checkout --detach --force "$commit"
  [[ "$(git -C "$dir" rev-parse HEAD)" == "$commit" ]] || {
    echo "Revision mismatch: $dir" >&2
    exit 2
  }
}

checkout_pinned "$IK_LLAMA_CPP_URL" "$SOAI_RUNTIME_DIR/ik_llama.cpp" "$IK_LLAMA_CPP_COMMIT"

# CUDA is explicitly named because a non-login WSL shell can find CMake while omitting
# /usr/local/cuda/bin from PATH. That exact mismatch caused the first live configuration
# attempt on this workstation to report "No CMAKE_CUDA_COMPILER could be found".
CUDA_COMPILER="${CUDACXX:-/usr/local/cuda/bin/nvcc}"
[[ -x "$CUDA_COMPILER" ]] || { echo "CUDA compiler not found: $CUDA_COMPILER" >&2; exit 2; }

cmake \
  -S "$SOAI_RUNTIME_DIR/ik_llama.cpp" \
  -B "$SOAI_RUNTIME_DIR/ik_llama.cpp/build-cuda" \
  -DGGML_NATIVE=ON \
  -DGGML_CUDA=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER="$CUDA_COMPILER"
cmake --build "$SOAI_RUNTIME_DIR/ik_llama.cpp/build-cuda" \
  --target llama-bench llama-server --config Release -j "$(nproc)"

SOAI_RUNTIME_DIR="$SOAI_RUNTIME_DIR" SOAI_STATE_DIR="$SOAI_STATE_DIR" python3 - <<'PY'
import json
import os
import subprocess
import time
from pathlib import Path

runtime = Path(os.environ["SOAI_RUNTIME_DIR"]) / "ik_llama.cpp"
commit = subprocess.check_output(
    ["git", "-C", runtime, "rev-parse", "HEAD"], text=True
).strip()
lock = {
    "generated_at": time.time(),
    "promotion_performed": False,
    "runtimes": {
        "ik_llama.cpp": {
            "path": str(runtime.resolve()),
            "commit": commit,
            "binaries": {
                "bench": str((runtime / "build-cuda/bin/llama-bench").resolve()),
                "server": str((runtime / "build-cuda/bin/llama-server").resolve()),
            },
        }
    },
}
out = Path(os.environ["SOAI_STATE_DIR"]) / "runtime-contender-lock.json"
out.write_text(json.dumps(lock, indent=2), encoding="utf-8")
print(f"Runtime contender lock: {out}")
PY

echo "Runtime contenders built. No route or engine was promoted."
