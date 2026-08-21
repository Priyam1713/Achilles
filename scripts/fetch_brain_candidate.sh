#!/usr/bin/env bash
# Fetch a benchmark-candidate artifact from Hugging Face at an immutable revision.
#
# Deliberately curl-based rather than huggingface_hub:
#   * the xet backend buffers a whole artifact in RAM before writing, which thrashes a
#     25 GB WSL VM on an ~19 GB file;
#   * with xet disabled the hub client still stalled on this link, while plain HTTP
#     sustained ~1.6 MB/s;
#   * `curl -C -` resumes, which matters when a download is measured in hours.
#
# A benchmark candidate is NOT an installed model. Nothing here touches configs/models.yaml
# or the install profiles. Artifacts land under $SOAI_MODEL_DIR/<slug>/gguf and are recorded
# in a per-candidate source lock so a measurement can always be traced to exact bytes.
#
# Usage:
#   ./scripts/fetch_brain_candidate.sh <slug> <repo> <revision> <file> [<file>...]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/scripts/runtime_env.sh"

if (($# < 4)); then
  sed -n '2,17p' "${BASH_SOURCE[0]}" >&2
  exit 2
fi

SLUG="$1"; REPO="$2"; REV="$3"; shift 3

case "$REV" in
  *[!0-9a-f]* | "") echo "Refusing a non-immutable revision: '$REV' (want a full commit sha)" >&2; exit 2 ;;
esac
[[ ${#REV} -eq 40 ]] || { echo "Revision must be a 40-char sha, got ${#REV} chars" >&2; exit 2; }

DEST="$SOAI_MODEL_DIR/$SLUG/gguf"
mkdir -p "$DEST"
LOCK="$SOAI_MODEL_DIR/$SLUG/source-lock.json"

base="https://huggingface.co/$REPO/resolve/$REV"
auth=()
[[ -n "${HF_TOKEN:-}" ]] && auth=(-H "Authorization: Bearer $HF_TOKEN")

entries=()
for file in "$@"; do
  out="$DEST/$(basename "$file")"
  url="$base/$file"

  expected=$(curl -sIL --max-time 60 "${auth[@]}" "$url" \
    | tr -d '\r' | awk 'tolower($1)=="x-linked-size:"{v=$2} END{print v}')
  if [[ -z "$expected" ]]; then
    expected=$(curl -sIL --max-time 60 "${auth[@]}" "$url" \
      | tr -d '\r' | awk 'tolower($1)=="content-length:"{v=$2} END{print v}')
  fi
  [[ -n "$expected" ]] || { echo "Could not resolve size for $file" >&2; exit 1; }

  have=0
  [[ -f "$out" ]] && have=$(stat -c%s "$out")
  if [[ "$have" == "$expected" ]]; then
    echo "present  $(basename "$file") ($((expected / 1024 / 1024)) MiB)"
  else
    echo "fetching $(basename "$file") -- $((expected / 1024 / 1024)) MiB, resuming from $((have / 1024 / 1024)) MiB"
    # Retry around transient CDN resets; -C - resumes rather than restarting.
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
      if curl -fL --progress-bar -C - --retry 5 --retry-delay 5 \
              --connect-timeout 30 --speed-limit 1024 --speed-time 120 \
              "${auth[@]}" -o "$out" "$url"; then
        break
      fi
      echo "  attempt $attempt interrupted; resuming in $((attempt * 5))s" >&2
      sleep "$((attempt * 5))"
    done
    got=$(stat -c%s "$out" 2>/dev/null || echo 0)
    if [[ "$got" != "$expected" ]]; then
      echo "Size mismatch for $file: got $got, expected $expected" >&2
      exit 1
    fi
  fi

  # Provenance: a benchmark number is only meaningful against known bytes.
  echo "  hashing $(basename "$file")..."
  sha=$(sha256sum "$out" | cut -d' ' -f1)
  entries+=("{\"file\":\"$file\",\"path\":\"$out\",\"bytes\":$expected,\"sha256\":\"$sha\"}")
done

printf '{\n  "slug": "%s",\n  "repo": "%s",\n  "revision": "%s",\n  "resolved_at": %s,\n  "artifacts": [%s]\n}\n' \
  "$SLUG" "$REPO" "$REV" "$(date +%s)" \
  "$(IFS=,; echo "${entries[*]}")" > "$LOCK"

echo "lock: $LOCK"
