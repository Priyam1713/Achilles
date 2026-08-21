from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
import yaml

from sovereign_ai.specialists.supervisor import SpecialistSupervisor

ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT = Path(os.getenv("SOAI_MODEL_DIR", ROOT / "models")).expanduser()
STATE_ROOT = Path(os.getenv("SOAI_STATE_DIR", ROOT / "state")).expanduser()
IMPLEMENTED = {"retrieval", "qwen_asr", "voxcpm", "paddleocr", "vision", "science_general"}


def profile_models(profile: str) -> set[str] | None:
    profiles = yaml.safe_load((ROOT / "configs/install-profiles.yaml").read_text())["profiles"]
    spec = profiles[profile]
    if spec.get("all_final"):
        return None
    selected = set(spec.get("models", []))
    parent = spec.get("extends")
    while parent:
        selected.update(profiles[parent].get("models", []))
        parent = profiles[parent].get("extends")
    return selected


async def main(strict: bool, profile: str) -> int:
    models = yaml.safe_load((ROOT / "configs/models.yaml").read_text())["models"]
    selected = profile_models(profile)
    sup = SpecialistSupervisor(ROOT, STATE_ROOT)
    failures = []
    passed = []
    skipped = []
    for m in models:
        if m.get("status") != "final" or "hf_worker" not in m.get("preferred_engines", []):
            continue
        if selected is not None and m["id"] not in selected:
            continue
        worker = sup.worker_for(m["id"])
        if not worker or worker not in IMPLEMENTED:
            skipped.append((m["id"], worker or "unmapped"))
            continue
        if not (MODEL_ROOT / m["id"] / "hf").exists():
            skipped.append((m["id"], "checkpoint-not-present"))
            continue
        print(f"==> prewarm {m['id']} via {worker}")
        try:
            url = await sup.ensure(worker, timeout_s=40)
            async with httpx.AsyncClient(timeout=900) as c:
                r = await c.post(
                    url + "/invoke",
                    json={
                        "model_id": m["id"],
                        "operation": "__prewarm__",
                        "inputs": {},
                        "options": {},
                    },
                )
                r.raise_for_status()
                passed.append(m["id"])
                await c.post(url + "/unload")
        except Exception as exc:
            failures.append((m["id"], f"{type(exc).__name__}: {exc}"))
    out = {"passed": passed, "skipped": skipped, "failures": failures}
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    (STATE_ROOT / "specialist-prewarm.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 1 if strict and failures else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--profile", choices=("core", "workstation", "full"), default="core")
    a = ap.parse_args()
    raise SystemExit(asyncio.run(main(a.strict, a.profile)))
