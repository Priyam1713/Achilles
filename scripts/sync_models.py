from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import yaml
from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.utils import GatedRepoError, HfHubHTTPError


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sync verified Hugging Face checkpoints from configs/models.yaml"
    )
    ap.add_argument("--config", default="configs/models.yaml")
    ap.add_argument("--model-dir", default="models")
    ap.add_argument("--state-dir", default="state")
    ap.add_argument("--profiles-config", default="configs/install-profiles.yaml")
    ap.add_argument("--profile", choices=("core", "workstation", "full"), default="core")
    ap.add_argument("--include-gated", action="store_true")
    ap.add_argument("--candidates", action="store_true")
    ap.add_argument("--only", action="append", default=[])
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    profiles = yaml.safe_load(Path(args.profiles_config).read_text(encoding="utf-8"))["profiles"]
    profile = profiles[args.profile]
    selected_ids: set[str] | None
    if profile.get("all_final"):
        selected_ids = None
    else:
        selected_ids = set(profile.get("models", []))
        parent = profile.get("extends")
        while parent:
            parent_profile = profiles[parent]
            selected_ids.update(parent_profile.get("models", []))
            parent = parent_profile.get("extends")

    model_dir = Path(args.model_dir).expanduser()
    model_dir.mkdir(parents=True, exist_ok=True)
    state_dir = Path(args.state_dir).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "model-lock.json"
    lock = json.loads(lock_path.read_text()) if lock_path.exists() else {"models": {}}

    failures = []
    skipped = []
    api = HfApi(token=os.getenv("HF_TOKEN") or None)
    for model in cfg.get("models", []):
        if model.get("status") == "excluded":
            continue
        if model.get("status") == "candidate" and not args.candidates:
            skipped.append((model["id"], "candidate-not-requested"))
            continue
        if args.only and model["id"] not in args.only:
            continue
        if selected_ids is not None and model["id"] not in selected_ids:
            skipped.append((model["id"], f"not-in-{args.profile}-profile"))
            continue
        if model.get("install_policy") in {"runtime_only", "runtime_managed", "package"}:
            skipped.append((model["id"], f"install-policy-{model.get('install_policy')}"))
            continue
        if model.get("source_type") != "huggingface":
            skipped.append((model["id"], f"owned-by-{model.get('source_type')}"))
            continue
        if not model.get("verified_source"):
            failures.append((model["id"], "source-not-verified"))
            continue
        if model.get("install_policy") == "gated" and not args.include_gated:
            skipped.append(
                (model["id"], "gated-use---include-gated-after-accepting-upstream-terms")
            )
            continue

        artifact = model.get("artifact") if model.get("install_policy") == "artifact" else None
        if artifact and (
            artifact.get("source_type") != "huggingface"
            or not artifact.get("verified_source")
        ):
            failures.append((model["id"], "artifact-source-not-verified"))
            continue

        repo_id = artifact["source"] if artifact else model["source"]
        local = model_dir / model["id"] / ("gguf" if artifact else "hf")
        allow_patterns = (
            artifact.get("allow_patterns") if artifact else model.get("allow_patterns")
        ) or None
        print(f"\n==> {model['id']} <- {repo_id}")
        try:
            upstream_info = api.model_info(repo_id=model["source"])
            info = api.model_info(repo_id=repo_id)
            revision = info.sha
            resolved = snapshot_download(
                repo_id=repo_id,
                revision=revision,
                local_dir=str(local),
                token=os.getenv("HF_TOKEN") or None,
                allow_patterns=allow_patterns,
            )
            lock["models"][model["id"]] = {
                "repo_id": repo_id,
                "revision": revision,
                "upstream_repo_id": model["source"],
                "upstream_revision": upstream_info.sha,
                "artifact": bool(artifact),
                "allow_patterns": allow_patterns,
                "local_dir": str(local.resolve()),
                "resolved_path": resolved,
                "synced_at": time.time(),
                "license_note": model.get("license_note"),
            }
            lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
        except GatedRepoError:
            failures.append((model["id"], "gated: accept upstream terms and set HF_TOKEN"))
        except HfHubHTTPError as exc:
            failures.append((model["id"], f"hub-error: {exc}"))
        except Exception as exc:
            failures.append((model["id"], repr(exc)))

    print("\n--- skipped ---")
    for x in skipped:
        print(*x, sep=": ")
    print("\n--- failures ---")
    for x in failures:
        print(*x, sep=": ")
    lock["profile"] = args.profile
    lock["updated_at"] = time.time()
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    print(f"\nprofile: {args.profile}")
    print(f"lock: {lock_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
