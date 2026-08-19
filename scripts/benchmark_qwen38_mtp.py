from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

import httpx

PROMPTS = (
    "Explain why a write-ahead log helps a durable job queue. Use five concise bullets.",
    "Write a Python function that merges overlapping integer intervals, then explain its complexity.",
    "Plan a safe migration from one local SQLite schema version to the next with rollback steps.",
)


def benchmark_profile(client: httpx.Client, profile: str) -> dict[str, Any]:
    load = client.post("/models/load", json={"model": profile})
    load.raise_for_status()
    samples: list[dict[str, Any]] = []
    try:
        for prompt in PROMPTS:
            started = time.perf_counter()
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": profile,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 256,
                    "temperature": 0,
                    "seed": 42,
                },
                timeout=600,
            )
            elapsed = time.perf_counter() - started
            response.raise_for_status()
            payload = response.json()
            completion_tokens = int((payload.get("usage") or {}).get("completion_tokens") or 0)
            timings = payload.get("timings") or {}
            tokens_per_second = float(timings.get("predicted_per_second") or 0)
            if not tokens_per_second and completion_tokens:
                tokens_per_second = completion_tokens / elapsed
            samples.append(
                {
                    "elapsed_seconds": round(elapsed, 3),
                    "completion_tokens": completion_tokens,
                    "tokens_per_second": round(tokens_per_second, 3),
                }
            )
    finally:
        client.post("/models/unload", json={"model": profile})
    speeds = [sample["tokens_per_second"] for sample in samples if sample["tokens_per_second"]]
    return {
        "profile": profile,
        "samples": samples,
        "median_tokens_per_second": round(statistics.median(speeds), 3) if speeds else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B Qwen3.8 plain vs MTP on the local router")
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--state-dir", default="state")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=600) as client:
        baseline = benchmark_profile(client, "qwen38-27b")
        mtp = benchmark_profile(client, "qwen38-27b-mtp-candidate")

    baseline_speed = baseline["median_tokens_per_second"]
    mtp_speed = mtp["median_tokens_per_second"]
    speedup = mtp_speed / baseline_speed if baseline_speed else 0
    # This report is evidence, not an automatic routing mutation. A human still reviews
    # output quality, server logs and repeatability before enabling the candidate.
    report = {
        "generated_at": time.time(),
        "baseline": baseline,
        "mtp": mtp,
        "speedup": round(speedup, 3),
        "candidate_wins_speed_gate": speedup >= 1.10,
        "promotion_performed": False,
    }
    state_dir = Path(args.state_dir).expanduser()
    state_dir.mkdir(parents=True, exist_ok=True)
    output = state_dir / "qwen38-mtp-benchmark.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
