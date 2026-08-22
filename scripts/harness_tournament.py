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
import shutil
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
    kernel: SovereignKernel,
    loop_name: str,
    task: HarnessTask,
    workspace_root: Path,
    capability: str = "coding",
    mode: str = "smart",
) -> dict[str, Any]:
    # Scoped by loop_name as well as task.id: two loops running the same task must not
    # share a workspace, or the second loop's setup() collides with the first loop's
    # leftover files (a real FileExistsError hit live the first time this ran two loops
    # back to back).
    workspace = workspace_root / loop_name / task.id
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    task.setup(workspace)
    kernel.workspaces.add(workspace, writable=True)

    agent_profile_id = f"tournament-{loop_name}-{task.id}"
    for action, scope in task.grants():
        kernel.capability_grants.issue(
            agent_profile_id, action, scope, "harness_tournament", ttl_seconds=300
        )

    loop = kernel.agent_loops.get(loop_name)
    state: dict[str, Any] = {
        "run_id": f"tournament-{task.id}-{uuid.uuid4().hex[:8]}",
        "task": task.objective_template.format(workspace=workspace),
        "workspace": str(workspace),
        "max_steps": task.max_steps,
        "approved": False,  # never auto-approve -- an "operator intervention" is a real cost
        "agent_profile_id": agent_profile_id,
        # Which brain runs the tournament is a first-class variable, not a constant. The
        # first real run of this script was recorded inconclusive precisely because three
        # of four tasks timed out on `qwen38-27b`, which F-005 already measured at 6.36
        # tok/s under offload -- a harness comparison run on a model too slow to finish
        # measures the model, not the harness.
        "capability": capability,
        "mode": mode,
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

    # A harness that timed out or crashed accomplished nothing, and must not be able to
    # score a pass on a "don't do the thing" task simply because it never got far enough to
    # do anything. Caught for real: an OpenCode run hit its 300s timeout with empty output
    # and still passed `mutation-without-authorization`, because the protected file was
    # untouched -- a false pass that would have flattered a harness for hanging (F-055).
    terminal = steps[-1]["kind"] if steps else "no_steps"
    if terminal in {"harness_timeout", "harness_error", "no_steps"} and passed:
        passed = False
        detail = f"post-condition held but the harness did not finish ({terminal}): {detail}"



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
    kernel: SovereignKernel,
    loop_names: list[str],
    tasks: list[HarnessTask],
    workspace_root: Path,
    capability: str = "coding",
    mode: str = "smart",
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
            result = await run_task(
                kernel, loop_name, task, workspace_root, capability, mode
            )
            status = "PASS" if result["passed"] else "FAIL"
            print(f"{status} ({result['wall_time_s']}s, {result['steps_taken']} steps): {result['detail'][:100]}")
            results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="append", dest="loops", help="repeatable; defaults to every registered loop")
    parser.add_argument("--config-root", default=str(REPO / "configs"))
    parser.add_argument("--state-dir", default=None)
    parser.add_argument(
        "--goose-tools",
        action="store_true",
        help=(
            "Enable Goose's real MCP tool bridge (FIXES.md F-045) instead of the "
            "zero-tool default, for a genuine tool-enabled comparison against native. "
            "Requires the 'harness' extra (mcp) to be installed."
        ),
    )
    parser.add_argument(
        "--capability",
        default="coding",
        help="Capability the native loop routes by (e.g. tool_routing for the fast brain)",
    )
    parser.add_argument("--mode", default="smart", help="Routing mode: fast, smart or deep")
    parser.add_argument(
        "--goose-model",
        default=None,
        help="Override the model id GooseAgentLoop asks the router for, so both loops "
        "can be compared on the same brain rather than on whatever each defaulted to",
    )
    args = parser.parse_args()

    kernel = SovereignKernel.build(args.config_root)
    state_dir = Path(args.state_dir) if args.state_dir else kernel.config.state_dir
    workspace_root = state_dir / "harness-tournament-workspaces"
    workspace_root.mkdir(parents=True, exist_ok=True)

    if args.goose_tools:
        try:
            goose_loop = kernel.agent_loops.get("goose")
        except KeyError:
            print("--goose-tools requested but no 'goose' loop is registered; ignoring.")
        else:
            goose_loop.enable_tools = True

    if args.goose_model:
        try:
            kernel.agent_loops.get("goose").model = args.goose_model
        except KeyError:
            print("--goose-model requested but no 'goose' loop is registered; ignoring.")

    loop_names = args.loops or kernel.agent_loops.names()
    print(f"loops: {loop_names}")
    print(f"tasks: {[t.id for t in TASKS]}")
    print()

    print(f"brain: capability={args.capability} mode={args.mode}"
          f"{' goose_model=' + args.goose_model if args.goose_model else ''}")
    results = asyncio.run(
        run_tournament(
            kernel, loop_names, TASKS, workspace_root, args.capability, args.mode
        )
    )

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
