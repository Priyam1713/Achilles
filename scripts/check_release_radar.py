from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]


def probe(client: httpx.Client, item: dict[str, Any]) -> dict[str, Any]:
    kind = item["kind"]
    result: dict[str, Any] = {
        "kind": kind,
        "lifecycle": item["lifecycle"],
        "expected": item["expected"],
        "official_url": item["official_url"],
    }
    if kind == "huggingface_model":
        response = client.get(f"https://huggingface.co/api/models/{item['repository']}")
        result["available"] = response.status_code == 200
        result["http_status"] = response.status_code
        if result["available"]:
            payload = response.json()
            result.update(
                revision=payload.get("sha"),
                last_modified=payload.get("lastModified"),
                private=bool(payload.get("private")),
                gated=bool(payload.get("gated")),
                license=(payload.get("cardData") or {}).get("license"),
            )
    elif kind == "github_repository":
        repository = item["repository"]
        metadata = client.get(f"https://api.github.com/repos/{repository}")
        metadata.raise_for_status()
        branch = item.get("branch") or metadata.json()["default_branch"]
        commit = client.get(f"https://api.github.com/repos/{repository}/commits/{branch}")
        commit.raise_for_status()
        payload = commit.json()
        result.update(
            available=True,
            revision=payload["sha"],
            branch=branch,
            version=(payload.get("commit") or {}).get("message", "").splitlines()[0],
        )
    elif kind == "npm_package":
        package = quote(item["package"], safe="")
        response = client.get(f"https://registry.npmjs.org/{package}/latest")
        response.raise_for_status()
        payload = response.json()
        result.update(
            available=True,
            revision=payload.get("gitHead"),
            version=payload.get("version"),
            license=payload.get("license"),
        )
    elif kind == "web_page":
        response = client.get(item["url"])
        response.raise_for_status()
        content = response.content
        expected_text = item.get("contains")
        result.update(
            available=not expected_text or expected_text in response.text,
            revision=hashlib.sha256(content).hexdigest(),
            last_modified=response.headers.get("last-modified"),
        )
    else:
        raise ValueError(f"Unsupported release-radar source kind: {kind}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check official release sources without changing the install manifest"
    )
    parser.add_argument("--config", default=ROOT / "configs/release-radar.yaml", type=Path)
    parser.add_argument("--state-dir", default=os.getenv("SOAI_STATE_DIR", ROOT / "state"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    state_dir = Path(args.state_dir).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    output = state_dir / "release-radar.json"
    previous = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    previous_sources = previous.get("sources", {})
    results: dict[str, Any] = {}
    changes: list[dict[str, Any]] = []
    failures: dict[str, str] = {}

    headers = {
        "user-agent": "local-sovereign-ai-release-radar/1.0",
        "accept": "application/json, text/html;q=0.9, */*;q=0.8",
    }
    with httpx.Client(headers=headers, follow_redirects=True, timeout=20) as client:
        for item in config["sources"]:
            source_id = item["id"]
            try:
                result = probe(client, item)
                results[source_id] = result
                old = previous_sources.get(source_id, {})
                old_marker = (old.get("available"), old.get("revision"), old.get("version"))
                new_marker = (
                    result.get("available"),
                    result.get("revision"),
                    result.get("version"),
                )
                if old and old_marker != new_marker:
                    changes.append({"id": source_id, "before": old_marker, "after": new_marker})
                status = "AVAILABLE" if result.get("available") else "PENDING"
                marker = result.get("version") or str(result.get("revision") or "")[:12]
                print(f"{status:9} {source_id}: {marker}")
                if item["expected"] == "present" and not result.get("available"):
                    failures[source_id] = "expected official source is unavailable"
            except Exception as exc:
                failures[source_id] = f"{type(exc).__name__}: {exc}"
                results[source_id] = {
                    "kind": item["kind"],
                    "lifecycle": item["lifecycle"],
                    "expected": item["expected"],
                    "official_url": item["official_url"],
                    "available": False,
                    "error": failures[source_id],
                }
                print(f"ERROR     {source_id}: {failures[source_id]}")

    report = {
        "generated_at": time.time(),
        "policy": config["policy"],
        "sources": results,
        "changes": changes,
        "failures": failures,
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Release radar: {output} ({len(changes)} change(s), {len(failures)} failure(s))")
    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
