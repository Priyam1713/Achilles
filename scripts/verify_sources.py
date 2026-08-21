from __future__ import annotations

import argparse
import fnmatch
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]


def profile_ids(profile_name: str, profiles: dict[str, Any]) -> set[str] | None:
    profile = profiles[profile_name]
    if profile.get("all_final"):
        return None
    selected = set(profile.get("models", []))
    parent = profile.get("extends")
    while parent:
        selected.update(profiles[parent].get("models", []))
        parent = profiles[parent].get("extends")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve model sources without downloading weights"
    )
    parser.add_argument("--profile", choices=("core", "workstation", "full"), default="core")
    parser.add_argument("--state-dir", default=os.getenv("SOAI_STATE_DIR", "state"))
    args = parser.parse_args()

    models = yaml.safe_load((ROOT / "configs/models.yaml").read_text())["models"]
    profiles = yaml.safe_load((ROOT / "configs/install-profiles.yaml").read_text())["profiles"]
    selected = profile_ids(args.profile, profiles)
    targets = [
        model
        for model in models
        if model.get("status") == "final"
        and model.get("source_type") == "huggingface"
        and (selected is None or model["id"] in selected)
        and model.get("install_policy") not in {"runtime_only", "runtime_managed", "package"}
    ]

    api = HfApi(token=os.getenv("HF_TOKEN") or None)

    def resolve(model: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        artifact = model.get("artifact") if model.get("install_policy") == "artifact" else None
        source = artifact["source"] if artifact else model["source"]
        patterns = (artifact.get("allow_patterns") if artifact else model.get("allow_patterns")) or []
        upstream = api.model_info(model["source"])
        info = api.model_info(source, files_metadata=True)
        files = [
            sibling
            for sibling in (info.siblings or [])
            if not patterns
            or any(fnmatch.fnmatch(sibling.rfilename, pattern) for pattern in patterns)
        ]
        download_bytes = sum(int(sibling.size or 0) for sibling in files)
        return model["id"], {
            "source": source,
            "revision": info.sha,
            "upstream_source": model["source"],
            "upstream_revision": upstream.sha,
            "artifact": bool(artifact),
            "gated": bool(info.gated),
            "private": bool(info.private),
            "last_modified": info.last_modified.isoformat() if info.last_modified else None,
            "download_bytes": download_bytes,
            "download_gb": round(download_bytes / 10**9, 3),
            "file_count": len(files),
        }

    resolved: dict[str, Any] = {}
    failures: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(resolve, model): model for model in targets}
        for future in as_completed(futures):
            model = futures[future]
            try:
                model_id, result = future.result()
                resolved[model_id] = result
                print(
                    f"OK {model_id}: {result['source']} @ {result['revision'][:12]} "
                    f"({result['download_gb']:.2f} GB)"
                )
            except Exception as exc:
                failures[model["id"]] = f"{type(exc).__name__}: {exc}"
                print(f"FAIL {model['id']}: {failures[model['id']]}")

    total_download_bytes = sum(item["download_bytes"] for item in resolved.values())
    report = {
        "generated_at": time.time(),
        "profile": args.profile,
        "resolved": resolved,
        "failures": failures,
        "total_download_bytes": total_download_bytes,
        "total_download_gb": round(total_download_bytes / 10**9, 3),
    }
    state_dir = Path(args.state_dir).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    output = state_dir / "source-audit.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"Source audit: {output} ({len(resolved)} resolved, {len(failures)} failed, "
        f"{report['total_download_gb']:.2f} GB selected)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
