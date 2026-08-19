#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
cd "$ROOT"
source "$ROOT/scripts/runtime_env.sh"
LLAMA="${LLAMA_CPP_DIR:-$SOAI_RUNTIME_DIR/llama.cpp}"
SERVER="$LLAMA/build/bin/llama-server"
QUANT="$LLAMA/build/bin/llama-quantize"
[[ -x "$SERVER" ]] || { echo "llama-server is not built at $SERVER" >&2; exit 1; }
[[ -x "$QUANT" ]] || { echo "llama-quantize is not built at $QUANT" >&2; exit 1; }

quant_if_needed() {
  local id="$1" quant_list="$2"
  local src="$SOAI_MODEL_DIR/$id/hf"
  local out="$SOAI_MODEL_DIR/$id/gguf"
  [[ -d "$src" ]] || { echo "Skipping $id: $src not downloaded"; return; }
  mkdir -p "$out"
  local f16="$out/$id-F16.gguf"
  local need=0
  for q in $quant_list; do [[ -f "$out/$id-$q.gguf" ]] || need=1; done
  [[ "$need" == 1 ]] || { echo "$id quantizations already present"; return; }
  CONV_PY="${SOAI_CONVERT_PY:-$(cat "$SOAI_STATE_DIR/llama-convert-python.txt" 2>/dev/null || command -v python3)}"
  "$CONV_PY" "$LLAMA/convert_hf_to_gguf.py" "$src" --outfile "$f16" --outtype f16
  for q in $quant_list; do
    [[ -f "$out/$id-$q.gguf" ]] || "$QUANT" "$f16" "$out/$id-$q.gguf" "$q"
  done
  [[ "${KEEP_INTERMEDIATE_F16:-0}" == 1 ]] || rm -f "$f16"
}

# Qwen3.5-9B: resident text/tool loop brain. Vision is routed elsewhere if the local mmproj path is not benchmark-clean.
quant_if_needed qwen35-9b "Q6_K"

# Qwen3.8 is synced as a pre-quantized, revision-locked artifact. Avoiding a local
# BF16 -> GGUF conversion saves roughly 50+ GB of transient disk and many build hours.
QWEN38_DIR="$SOAI_MODEL_DIR/qwen38-27b/gguf"
QWEN38="$QWEN38_DIR/Qwen3.8-27B-UD-Q4_K_M.gguf"
MM="$QWEN38_DIR/mmproj-F16.gguf"
MTP="$QWEN38_DIR/MTP/mtp-Qwen3.8-27B-Q4_0.gguf"
for artifact in "$QWEN38" "$MM" "$MTP"; do
  [[ -f "$artifact" ]] || { echo "Missing synced Qwen3.8 artifact: $artifact" >&2; exit 1; }
done

cat > "$SOAI_STATE_DIR/llama-models.ini" <<EOF2
version = 1

[*]
c = 16384
jinja = true
n-gpu-layers = auto
fit = true
fit-target = 1800
flash-attn = on
cache-type-k = q8_0
cache-type-v = q8_0
stop-timeout = 30
dedup-cache-models = true

[qwen35-9b]
model = $SOAI_MODEL_DIR/qwen35-9b/gguf/qwen35-9b-Q6_K.gguf
no-mmproj = true
c = 32768
load-on-startup = true

[qwen38-27b]
model = $QWEN38
mmproj = $MM
c = 16384
load-on-startup = false

[qwen38-27b-mtp-candidate]
model = $QWEN38
mmproj = $MM
model-draft = $MTP
spec-type = draft-mtp
spec-draft-n-max = 2
c = 16384
load-on-startup = false
EOF2

echo "Generated $SOAI_STATE_DIR/llama-models.ini"

# Actual router/model smoke test: each preset must load and emit a response.
if [[ "${SOAI_SKIP_LLAMA_SMOKE:-0}" != 1 ]]; then "$ROOT/scripts/llama_smoke.sh" "$ROOT"; fi

# After verified GGUF conversion and load, discard duplicate raw brain weights unless explicitly retained.
if [[ "${KEEP_QWEN_HF:-0}" != 1 ]]; then
  rm -rf "$SOAI_MODEL_DIR/qwen35-9b/hf"
  echo "Removed duplicate raw Qwen3.5 HF snapshot after successful GGUF smoke test."
fi
