"""Replay the same tasks through every registered `AgentLoop` and score the result.

Answers `knowledge/research.md` experiment 11: "Replay the same coding tasks through
Hermes, DeepSeek Harness, LongHorizon/GSD where appropriate, and Grok Build. Score
completed post-conditions, unsafe attempts, recovery, tokens, wall time, and operator
interventions." As of this fix, `native` (FIXES.md F-027) is the only registered
`AgentLoop` on this workstation -- `D-015` picked Goose as the external harness to add
next, but building it requires a Rust/Cargo toolchain this workstation does not have
(confirmed absent on both the WSL and Windows sides). This script does not wait on that:
it establishes the scoring framework and records `native`'s own real baseline now, so a
future harness has something concrete to be compared against the moment it can be
registered, rather than the tournament starting from zero once it arrives.

Like every other benchmark script in this project, this produces *evidence*, never a
promotion: nothing here changes `configs/`, a route, or which loop the kernel uses.

Usage (inside WSL, with a live inference backend already running):

    source scripts/runtime_env.sh
    python3 scripts/harness_tournament.py --loop native
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from harness_tasks import TASKS, HarnessTask  # noqa: E402

from sovereign_ai.kernel.app import SovereignKernel  # noqa: E402


async def run_task(
    kernel: SovereignKernel, loop_name: str, task: HarnessTask, workspace_root: Path
) -> dict[str, Any]:
    workspace = workspace_root / task.id
    workspace.mkdir(parents=True, exist_ok=True)
    task.setup(workspace)
    kernel.workspaces.add(workspace, writable=True)

    agent_profile_id = f"tournament-{task.id}"
    if task.requires_capability_grant:
        kernel.capability_grants.issue(
            agent_profile_id, "execute", "workspace", "harness_tournament", ttl_seconds=300
        )

    loop = kernel.agent_loops.get(loop_name)
    state: dict[str, Any] = {
        "run_id": f"tournament-{task.id}-{uuid.uuid4().hex[:8]}",
        "task": task.objective_template.format(workspace=workspace),
        "workspace": str(workspace),
        "max_steps": task.max_steps,
        "approved": False,  # never auto-approve -- an "operator intervention" is a real cost
        "agent_profile_id": agent_profile_id,
    }

    steps: list[dict[str, Any]] = []
    denied_attempts = 0
    started = time.perf_counter()
    while True:
        try:
            step = await loop.next_step(state)
        except Exception as exc:
            steps.append({"kind": "harness_error", "payload": {"error": f"{type(exc).__name__}: {exc}"}})
            break
        steps.append({"kind": step.kind, "payload": step.payload})
        observation = step.payload.get("observation") if step.kind == "observation" else None
        if isinstance(observation, dict) and "denied" in str(observation.get("error", "")):
            denied_attempts += 1
        if step.done:
            break
    elapsed = time.perf_counter() - started

    final_summary = ""
    if steps and steps[-1]["kind"] == "done":
        final_summary = str(steps[-1]["payload"].get("summary", ""))
    passed, detail = task.check(workspace, final_summary)

    return {
        "task_id": task.id,
        "category": task.category,
        "loop": loop_name,
        "passed": passed,
        "detail": detail,
        "outcome": steps[-1]["kind"] if steps else "no_steps",
        "steps_taken": len(steps),
        "denied_attempts": denied_attempts,
        "wall_time_s": round(elapsed, 2),
        "final_summary": final_summary[:300],
    }


async def run_tournament(
    kernel: SovereignKernel, loop_names: list[str], tasks: list[HarnessTask], workspace_root: Path
) -> list[dict[str, Any]]:
    results = []
    for loop_name in loop_names:
        try:
            kernel.agent_loops.get(loop_name)
        except KeyError:
            print(f"  SKIP {loop_name}: not registered on this kernel")
            continue
        for task in tasks:
            print(f"  {loop_name} / {task.id}...", end=" ", flush=True)
            result = await run_task(kernel, loop_name, task, workspace_root)
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{status} ({result['wall_time_s']}s, {result['steps_taken']} steps): {result['detail'][:100]}")
            results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="append", dest="loops", help="repeatable; defaults to every registered loop")
    parser.add_argument("--config-root", default=str(REPO / "configs"))
    parser.add_argument("--state-dir", default=None)
    args = parser.parse_args()

    kernel = SovereignKernel.build(args.config_root)
    state_dir = Path(args.state_dir) if args.state_dir else kernel.config.state_dir
    workspace_root = state_dir / "harness-tournament-workspaces"
    workspace_root.mkdir(parents=True, exist_ok=True)

    loop_names = args.loops or kernel.agent_loops.names()
    print(f"loops: {loop_names}")
    print(f"tasks: {[t.id for t in TASKS]}")
    print()

    results = asyncio.run(run_tournament(kernel, loop_names, TASKS, workspace_root))

    by_loop: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_loop.setdefault(r["loop"], []).append(r)

    summary = {}
    for loop_name, loop_results in by_loop.items():
        passed = sum(1 for r in loop_results if r["passed"])
        summary[loop_name] = {
            "passed": passed,
            "total": len(loop_results),
            "total_denied_attempts": sum(r["denied_attempts"] for r in loop_results),
            "total_wall_time_s": round(sum(r["wall_time_s"] for r in loop_results), 2),
        }

    report = {
        "generated_at": time.time(),
        "loops": loop_names,
        "summary": summary,
        "results": results,
    }
    out = state_dir / "harness-tournament.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    for loop_name, s in summary.items():
        print(
            f"{loop_name}: {s['passed']}/{s['total']} passed, "
            f"{s['total_denied_attempts']} denied attempt(s), {s['total_wall_time_s']}s total"
        )
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
