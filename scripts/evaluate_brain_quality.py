"""Run the quality_eval_tasks.py suite against one or more live models on this GPU.

Answers F-005/D-012's remaining open question: benchmark_brains.py measures throughput;
this measures whether the candidate can actually do the work. Results are written to
BenchmarkStore, so the scheduler's local-benchmark override (docs/ARCHITECTURE.md's
"this workstation's measurements win") can eventually use a real quality score instead of
the manifest's quality_prior placeholder -- but this script only RECORDS evidence, it never
promotes a model or changes a route, matching every other benchmark tool in this project.

Usage (inside WSL, with the llama.cpp router already running):

    source scripts/runtime_env.sh
    python3 scripts/evaluate_brain_quality.py --model-id qwen35-9b --engine-id llama_cpp
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from quality_eval_tasks import TASKS, Task  # noqa: E402

from sovereign_ai.inference.content import extract_message_content  # noqa: E402
from sovereign_ai.inference.openai_compat import OpenAICompatibleBackend  # noqa: E402


async def run_task(backend: OpenAICompatibleBackend, model_id: str, task: Task) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = await backend.chat(
            model_id,
            [{"role": "user", "content": task.prompt}],
            max_tokens=task.max_tokens,
            temperature=0,
            # These are short, well-defined tasks -- verbose chain-of-thought (Qwen3.5-
            # style thinking mode) only burns the token budget without helping, and on a
            # first live run it burned the ENTIRE budget on 4 of 5 tasks before the model
            # ever reached a final answer, scoring a harness bug as "the model failed".
            # See inference/content.py and FIXES.md F-028.
            chat_template_kwargs={"enable_thinking": False},
        )
    except Exception as exc:
        return {
            "task_id": task.id, "category": task.category, "passed": False,
            "detail": f"backend error: {type(exc).__name__}: {exc}",
            "latency_s": round(time.perf_counter() - started, 2),
        }
    latency = time.perf_counter() - started
    content = extract_message_content(response)
    passed, detail = task.check(content)
    return {
        "task_id": task.id, "category": task.category, "passed": passed,
        "detail": detail[:500], "latency_s": round(latency, 2),
        "completion_preview": content[:300],
    }


async def run_suite(base_url: str, model_id: str, tasks: list[Task]) -> list[dict[str, Any]]:
    backend = OpenAICompatibleBackend(base_url)
    results = []
    for task in tasks:
        print(f"  {task.id}...", end=" ", flush=True)
        result = await run_task(backend, model_id, task)
        print("PASS" if result["passed"] else f"FAIL ({result['detail'][:80]})")
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", required=True, help="runtime model id as the backend expects it")
    parser.add_argument("--engine-id", default="llama_cpp")
    parser.add_argument("--base-url", default="http://127.0.0.1:18080/v1")
    parser.add_argument("--capability", default="reasoning")
    parser.add_argument("--state-dir", default=str(REPO / "state"))
    parser.add_argument(
        "--record", action="store_true",
        help="also write the aggregate score into state/benchmarks.db via BenchmarkStore",
    )
    args = parser.parse_args()

    print(f"model: {args.model_id}  engine: {args.engine_id}  base_url: {args.base_url}")
    results = asyncio.run(run_suite(args.base_url, args.model_id, TASKS))

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    by_category: dict[str, list[bool]] = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r["passed"])
    avg_latency = sum(r["latency_s"] for r in results) / total if total else 0.0

    report = {
        "generated_at": time.time(),
        "model_id": args.model_id,
        "engine_id": args.engine_id,
        "score": round(passed / total, 3) if total else 0.0,
        "passed": passed,
        "total": total,
        "by_category": {
            cat: {"passed": sum(v), "total": len(v)} for cat, v in by_category.items()
        },
        "avg_latency_s": round(avg_latency, 2),
        "results": results,
    }

    state_dir = Path(args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    out = state_dir / f"quality-eval-{args.model_id}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"score: {passed}/{total} ({report['score']:.0%})  avg latency: {avg_latency:.1f}s")
    for cat, counts in report["by_category"].items():
        print(f"  {cat}: {counts['passed']}/{counts['total']}")
    print(f"report: {out}")

    if args.record:
        sys.path.insert(0, str(REPO / "src"))
        from sovereign_ai.kernel.benchmarks import BenchmarkStore

        store = BenchmarkStore(state_dir / "benchmarks.db")
        store.record(
            model_id=args.model_id,
            engine_id=args.engine_id,
            capability=args.capability,
            quality=report["score"],
            latency_ms=avg_latency * 1000,
            reliability=1.0 if passed == total else passed / total,
            metadata={"quality_eval_report": str(out), "suite_size": total},
        )
        print(f"recorded into {state_dir / 'benchmarks.db'} (capability={args.capability})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
