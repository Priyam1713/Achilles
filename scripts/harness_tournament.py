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
import hashlib
import inspect
import json
import platform
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from harness_swe_tasks import SOFTWARE_ENGINEERING_TASKS  # noqa: E402
from harness_tasks import MICRO_TASKS, HarnessTask  # noqa: E402
from router_metrics import snapshot, summarise  # noqa: E402

if TYPE_CHECKING:
    from sovereign_ai.kernel.app import SovereignKernel

SUITES: dict[str, list[HarnessTask]] = {
    "micro": MICRO_TASKS,
    "software-engineering": SOFTWARE_ENGINEERING_TASKS,
    "all": [*MICRO_TASKS, *SOFTWARE_ENGINEERING_TASKS],
}


async def run_held_out_verification(
    kernel: SovereignKernel,
    loop_name: str,
    task: HarnessTask,
    solution_workspace: Path,
    workspace_root: Path,
    attempt: int,
) -> dict[str, Any]:
    """Run candidate code without importing it into this coordinator process.

    The verifier directory does not exist until the agent loop is done.  A copy of the
    solution and the trusted verifier are then handed to the normal hardened execution
    broker with sync-back disabled.  Registering the directory read-only makes that
    invariant explicit at the policy boundary as well as in the backend call.
    """
    verification = task.verification
    if verification is None:
        raise ValueError(f"task {task.id} has no held-out verifier")

    verification_root = workspace_root.parent / f"{workspace_root.name}-verification"
    verifier_workspace = verification_root / loop_name / f"{task.id}-{attempt}"
    if verifier_workspace.exists():
        shutil.rmtree(verifier_workspace)
    verifier_workspace.mkdir(parents=True)
    shutil.copytree(solution_workspace, verifier_workspace / "solution", symlinks=True)
    (verifier_workspace / "verify.py").write_text(verification.script, encoding="utf-8")
    kernel.workspaces.add(
        verifier_workspace,
        label=f"held-out verifier: {loop_name}/{task.id}/{attempt}",
        writable=False,
    )

    try:
        result = await asyncio.wait_for(
            kernel.execution.run_approved(
                verification.argv,
                cwd=str(verifier_workspace),
                approved=True,
                mutates_state=False,
            ),
            timeout=verification.timeout_seconds,
        )
    except TimeoutError:
        return {
            "available": True,
            "passed": False,
            "outcome": "timeout",
            "returncode": None,
            "backend": None,
            "stdout": "",
            "stderr": f"held-out verifier exceeded {verification.timeout_seconds:g}s",
        }
    except Exception as exc:
        return {
            "available": False,
            "passed": False,
            "outcome": "unavailable",
            "returncode": None,
            "backend": None,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }
    finally:
        # The artefact stays on disk for audit, but it no longer remains an approved
        # workspace after the trusted verification command has returned.
        kernel.workspaces.remove(verifier_workspace)

    return {
        "available": True,
        "passed": result.returncode == 0,
        "outcome": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "backend": result.backend,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }


async def run_task(
    kernel: SovereignKernel,
    loop_name: str,
    task: HarnessTask,
    workspace_root: Path,
    capability: str = "coding",
    mode: str = "smart",
    metrics_url: str | None = None,
    metrics_model: str | None = None,
    attempt: int = 1,
) -> dict[str, Any]:
    # Scoped by loop_name as well as task.id: two loops running the same task must not
    # share a workspace, or the second loop's setup() collides with the first loop's
    # leftover files (a real FileExistsError hit live the first time this ran two loops
    # back to back).
    # Attempts get their own workspace: a repeat that inherits the previous attempt's files
    # is not a repeat, it is a continuation, and it would quietly make later attempts easier.
    workspace = workspace_root / loop_name / f"{task.id}-{attempt}"
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
    # Token cost is read from the router's own counters rather than inferred from wall time
    # or step counts. Every harness talks to the same server, so this measures all of them
    # on one scale -- including the subprocess ones whose internals we cannot see.
    before = snapshot(metrics_url, metrics_model) if metrics_url and metrics_model else None
    started = time.perf_counter()
    while True:
        try:
            step = await loop.next_step(state)
        except Exception as exc:
            steps.append({"kind": "harness_error", "payload": {"error": f"{type(exc).__name__}: {exc}"}})
            break
        steps.append({"kind": step.kind, "payload": step.payload})
        observation = step.payload.get("observation") if step.kind == "observation" else None
        if isinstance(observation, dict) and (
            observation.get("denied") is True
            or "denied" in str(observation.get("error", "")).casefold()
        ):
            denied_attempts += 1
        if step.done:
            break
    elapsed = time.perf_counter() - started
    tokens: dict[str, Any] = {"available": False}
    if before is not None:
        after = snapshot(metrics_url, metrics_model)
        tokens = summarise(after.since(before))

    final_summary = ""
    if steps and steps[-1]["kind"] == "done":
        final_summary = str(steps[-1]["payload"].get("summary", ""))
    verification_result: dict[str, Any] = {"available": False, "outcome": "not_required"}
    if task.verification is None:
        passed, detail = task.check(workspace, final_summary)
    else:
        verification_result = await run_held_out_verification(
            kernel, loop_name, task, workspace, workspace_root, attempt
        )
        passed = bool(verification_result["passed"])
        evidence = verification_result["stdout"] or verification_result["stderr"]
        detail = evidence.strip() or f"held-out verification {verification_result['outcome']}"

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
        "attempt": attempt,
        "tokens": tokens,
        "passed": passed,
        "detail": detail,
        "outcome": steps[-1]["kind"] if steps else "no_steps",
        "steps_taken": len(steps),
        "denied_attempts": denied_attempts,
        "wall_time_s": round(elapsed, 2),
        "final_summary": final_summary[:300],
        "verification": verification_result,
    }


async def run_tournament(
    kernel: SovereignKernel,
    loop_names: list[str],
    tasks: list[HarnessTask],
    workspace_root: Path,
    capability: str = "coding",
    mode: str = "smart",
    repeats: int = 1,
    metrics_url: str | None = None,
    metrics_model: str | None = None,
) -> list[dict[str, Any]]:
    results = []
    for loop_name in loop_names:
        try:
            kernel.agent_loops.get(loop_name)
        except KeyError:
            print(f"  SKIP {loop_name}: not registered on this kernel")
            continue
        for task in tasks:
            for attempt in range(1, repeats + 1):
                label = f"  {loop_name} / {task.id}"
                if repeats > 1:
                    label += f" [{attempt}/{repeats}]"
                print(f"{label}...", end=" ", flush=True)
                result = await run_task(
                    kernel, loop_name, task, workspace_root, capability, mode,
                    metrics_url, metrics_model, attempt,
                )
                status = "PASS" if result["passed"] else "FAIL"
                cost = ""
                if result["tokens"].get("available"):
                    cost = (
                        f", {result['tokens']['total_tokens']} tok"
                        f" ({result['tokens']['generated_tokens']} gen)"
                    )
                print(
                    f"{status} ({result['wall_time_s']}s, {result['steps_taken']} steps{cost})"
                    f": {result['detail'][:80]}"
                )
                results.append(result)
    return results


def _native_model(kernel: SovereignKernel, capability: str, mode: str) -> str | None:
    """Which model the native loop will actually be routed to.

    Asked of the scheduler rather than assumed, so token accounting cannot silently attach
    to a different model than the one under test.
    """
    from sovereign_ai.kernel.types import CapabilityRequest, RoutingMode

    try:
        decision = kernel.scheduler.route(
            CapabilityRequest(capability=capability, mode=RoutingMode(mode))
        )
    except Exception:
        return None
    return decision.candidates[0].model_id if decision.candidates else None


def select_tasks(
    suite: str,
    task_ids: list[str] | None = None,
    categories: list[str] | None = None,
) -> list[HarnessTask]:
    tasks = list(SUITES[suite])
    known_ids = {task.id for task in tasks}
    unknown = sorted(set(task_ids or ()) - known_ids)
    if unknown:
        raise ValueError(f"task(s) are not in suite {suite!r}: {', '.join(unknown)}")
    if task_ids:
        selected = set(task_ids)
        tasks = [task for task in tasks if task.id in selected]
    if categories:
        selected_categories = set(categories)
        tasks = [task for task in tasks if task.category in selected_categories]
    if not tasks:
        raise ValueError("task selection is empty")
    return tasks


def _task_manifest(tasks: list[HarnessTask]) -> tuple[list[dict[str, Any]], str]:
    manifest = [
        {
            "id": task.id,
            "category": task.category,
            "max_steps": task.max_steps,
            "required_grants": task.grants(),
            "objective_sha256": hashlib.sha256(task.objective_template.encode()).hexdigest(),
            "setup_sha256": hashlib.sha256(
                inspect.getsource(task.setup).encode()
            ).hexdigest(),
            "check_sha256": hashlib.sha256(
                inspect.getsource(task.check).encode()
            ).hexdigest(),
            "verification": "held-out" if task.verification else "post-condition",
            "verification_sha256": (
                hashlib.sha256(task.verification.script.encode()).hexdigest()
                if task.verification
                else None
            ),
        }
        for task in tasks
    ]
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return manifest, hashlib.sha256(encoded).hexdigest()


def _git_provenance() -> dict[str, Any]:
    try:
        head = subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True, timeout=5
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "-C", str(REPO), "status", "--porcelain"], text=True, timeout=5
            ).strip()
        )
        return {"head": head, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"head": None, "dirty": None}


def summarise_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_loop: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_loop.setdefault(result["loop"], []).append(result)

    summary: dict[str, Any] = {}
    for loop_name, loop_results in by_loop.items():
        passed = sum(1 for result in loop_results if result["passed"])
        categories: dict[str, dict[str, int]] = {}
        outcomes: dict[str, int] = {}
        for result in loop_results:
            category = categories.setdefault(result["category"], {"passed": 0, "total": 0})
            category["total"] += 1
            category["passed"] += int(result["passed"])
            outcomes[result["outcome"]] = outcomes.get(result["outcome"], 0) + 1
        summary[loop_name] = {
            "passed": passed,
            "total": len(loop_results),
            "pass_rate": round(passed / len(loop_results), 4) if loop_results else 0.0,
            "by_category": categories,
            "outcomes": outcomes,
            "total_denied_attempts": sum(r["denied_attempts"] for r in loop_results),
            "total_wall_time_s": round(sum(r["wall_time_s"] for r in loop_results), 2),
            "median_wall_time_s": round(
                statistics.median(r["wall_time_s"] for r in loop_results), 2
            ),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="append", dest="loops", help="repeatable; defaults to every registered loop")
    parser.add_argument("--config-root", default=str(REPO / "configs"))
    parser.add_argument("--state-dir", default=None)
    parser.add_argument(
        "--suite",
        choices=sorted(SUITES),
        default="micro",
        help="Versioned task family; defaults to the historical micro baseline",
    )
    parser.add_argument(
        "--task", action="append", dest="tasks", help="repeatable task id filter"
    )
    parser.add_argument(
        "--category", action="append", dest="categories", help="repeatable category filter"
    )
    parser.add_argument(
        "--list", action="store_true", help="list the selected suite's tasks and exit"
    )
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
        "--repeats",
        type=int,
        default=1,
        help="Run each task this many times. F-055 saw a harness flip on identical inputs, "
        "so a single run is an anecdote; pass rate over repeats is the honest number",
    )
    parser.add_argument(
        "--metrics-url",
        default=None,
        help="llama.cpp router base URL for token accounting (defaults to the llama_cpp "
        "engine's own base_url)",
    )
    parser.add_argument(
        "--external-model",
        default=None,
        help="Model id for every external (subprocess) loop, so all loops are compared on "
        "the same brain rather than on whatever each defaulted to",
    )
    parser.add_argument(
        "--goose-model",
        default=None,
        help="Override the model id GooseAgentLoop asks the router for, so both loops "
        "can be compared on the same brain rather than on whatever each defaulted to",
    )
    args = parser.parse_args()

    try:
        selected_tasks = select_tasks(args.suite, args.tasks, args.categories)
    except ValueError as exc:
        parser.error(str(exc))
    if args.list:
        for task in selected_tasks:
            verifier = "held-out" if task.verification else "post-condition"
            print(f"{task.id}\t{task.category}\t{verifier}\t{task.max_steps} steps")
        return 0

    from sovereign_ai.kernel.app import SovereignKernel

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

    # Every subprocess harness has its own model default, set when the kernel wired it up.
    # Comparing loops means holding the model fixed across all of them, so this overrides
    # each external loop that exposes a `model` attribute rather than only Goose.
    if args.external_model:
        for name in kernel.agent_loops.names():
            loop = kernel.agent_loops.get(name)
            if hasattr(loop, "model"):
                loop.model = args.external_model
                print(f"  {name}: model set to {args.external_model}")

    loop_names = args.loops or kernel.agent_loops.names()
    print(f"loops: {loop_names}")
    print(f"suite: {args.suite}")
    print(f"tasks: {[t.id for t in selected_tasks]}")
    print()

    print(f"brain: capability={args.capability} mode={args.mode}"
          f"{' goose_model=' + args.goose_model if args.goose_model else ''}")
    metrics_url = args.metrics_url
    if metrics_url is None:
        engine = kernel.registry.engines.get("llama_cpp")
        metrics_url = engine.base_url if engine else None
    # Token counters are per-model, so accounting needs to know which one is being driven.
    metrics_model = args.external_model or _native_model(kernel, args.capability, args.mode)
    if metrics_url and metrics_model:
        print(f"token accounting: {metrics_url} model={metrics_model}")
    else:
        print("token accounting: unavailable (no llama.cpp engine or model resolved)")

    results = asyncio.run(
        run_tournament(
            kernel, loop_names, selected_tasks, workspace_root, args.capability, args.mode,
            args.repeats, metrics_url, metrics_model,
        )
    )

    summary = summarise_results(results)
    task_manifest, task_manifest_sha256 = _task_manifest(selected_tasks)

    report = {
        "schema_version": 2,
        "generated_at": time.time(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "suite": args.suite,
        "task_manifest": task_manifest,
        "task_manifest_sha256": task_manifest_sha256,
        "execution_order": [task.id for task in selected_tasks],
        "repeats": args.repeats,
        "loops": loop_names,
        "capability": args.capability,
        "mode": args.mode,
        "metrics_url": metrics_url,
        "metrics_model": metrics_model,
        "external_model": args.external_model,
        "git": _git_provenance(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "promotion_performed": False,
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
