from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from harness_swe_tasks import SOFTWARE_ENGINEERING_TASKS
from harness_tasks import MICRO_TASKS, TASKS
from harness_tournament import (
    _git_provenance,
    campaign_cells,
    execution_compatibility_sha256,
    finalise_task_outcome,
    paired_analysis,
    run_held_out_verification,
    select_tasks,
    summarise_results,
    terminal_diagnostics,
)
from router_metrics import warm_model

from sovereign_ai.execution import openshell as openshell_module
from sovereign_ai.execution.base import ExecutionResult
from sovereign_ai.execution.docker import DockerBackend
from sovereign_ai.execution.openshell import OpenShellBackend


def test_versioned_suites_are_disjoint_and_historical_alias_is_stable():
    assert TASKS is MICRO_TASKS
    assert len(MICRO_TASKS) == 12
    assert len(SOFTWARE_ENGINEERING_TASKS) == 12
    micro_ids = {task.id for task in MICRO_TASKS}
    swe_ids = {task.id for task in SOFTWARE_ENGINEERING_TASKS}
    assert not micro_ids.intersection(swe_ids)
    assert all(task.verification is None for task in MICRO_TASKS)
    assert all(task.verification is not None for task in SOFTWARE_ENGINEERING_TASKS)
    for task in SOFTWARE_ENGINEERING_TASKS:
        compile(task.verification.script, f"{task.id}-verify.py", "exec")


def test_suite_selection_preserves_manifest_order_and_rejects_unknown_tasks():
    selected = select_tasks(
        "software-engineering",
        task_ids=["swe-safe-join", "swe-empty-mean"],
    )
    assert [task.id for task in selected] == ["swe-empty-mean", "swe-safe-join"]
    assert [task.id for task in select_tasks("software-engineering", categories=["security"])] == [
        "swe-safe-join"
    ]

    try:
        select_tasks("micro", task_ids=["swe-safe-join"])
    except ValueError as exc:
        assert "not in suite" in str(exc)
    else:
        raise AssertionError("cross-suite task selection should fail")


def test_campaign_cells_counterbalance_loop_position_deterministically():
    tasks = SOFTWARE_ENGINEERING_TASKS[:2]
    cells = campaign_cells(["native", "pi", "goose"], tasks, repeats=2)
    assert [(loop, task.id, attempt) for loop, task, attempt in cells] == [
        ("native", tasks[0].id, 1),
        ("pi", tasks[0].id, 1),
        ("goose", tasks[0].id, 1),
        ("pi", tasks[1].id, 1),
        ("goose", tasks[1].id, 1),
        ("native", tasks[1].id, 1),
        ("pi", tasks[0].id, 2),
        ("goose", tasks[0].id, 2),
        ("native", tasks[0].id, 2),
        ("goose", tasks[1].id, 2),
        ("native", tasks[1].id, 2),
        ("pi", tasks[1].id, 2),
    ]


def test_every_initial_swe_fixture_fails_its_held_out_contract(tmp_path):
    """A benchmark that passes before any work is performed is not an evaluation."""
    for task in SOFTWARE_ENGINEERING_TASKS:
        verifier_root = tmp_path / task.id
        solution = verifier_root / "solution"
        solution.mkdir(parents=True)
        task.setup(solution)
        verifier = verifier_root / "verify.py"
        verifier.write_text(task.verification.script, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-I", str(verifier), str(solution)],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert result.returncode != 0, f"{task.id} passed without a candidate change"


def test_every_gold_control_passes_its_held_out_contract(tmp_path):
    for task in SOFTWARE_ENGINEERING_TASKS:
        verifier_root = tmp_path / task.id
        solution = verifier_root / "solution"
        solution.mkdir(parents=True)
        task.setup(solution)
        assert task.verification.gold_patch is not None
        task.verification.gold_patch(solution)
        verifier = verifier_root / "verify.py"
        verifier.write_text(task.verification.script, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-I", str(verifier), str(solution)],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, f"{task.id} gold failed: {result.stderr}"


def test_held_out_verifier_rejects_forbidden_candidate_files(tmp_path):
    task = SOFTWARE_ENGINEERING_TASKS[0]
    workspace_root = tmp_path / "workspaces"
    solution = workspace_root / "native" / f"{task.id}-1"
    solution.mkdir(parents=True)
    task.setup(solution)
    (solution / "README.md").write_text("candidate-controlled tests\n", encoding="utf-8")

    class Workspaces:
        def add(self, *args, **kwargs):
            raise AssertionError("forbidden candidates must not reach execution")

        def remove(self, *args, **kwargs):
            raise AssertionError("workspace was never registered")

    class Execution:
        async def run_approved(self, *args, **kwargs):
            raise AssertionError("forbidden candidates must not execute")

    class Kernel:
        workspaces = Workspaces()
        execution = Execution()

    result = asyncio.run(
        run_held_out_verification(Kernel(), "native", task, solution, workspace_root, 1)
    )
    assert result["outcome"] == "forbidden_changes"
    assert result["forbidden_files"] == ["README.md"]


def test_held_out_verifier_is_staged_afterward_and_never_synced_back(tmp_path):
    task = SOFTWARE_ENGINEERING_TASKS[0]
    workspace_root = tmp_path / "workspaces"
    solution = workspace_root / "native" / f"{task.id}-1"
    solution.mkdir(parents=True)
    task.setup(solution)

    class Workspaces:
        def __init__(self):
            self.added = []
            self.removed = []

        def add(self, path, **kwargs):
            self.added.append((Path(path), kwargs))

        def remove(self, path):
            self.removed.append(Path(path))

    class Execution:
        def __init__(self):
            self.calls = []

        async def run_approved(self, argv, cwd, **kwargs):
            self.calls.append((tuple(argv), Path(cwd), kwargs))
            assert (Path(cwd) / "verify.py").exists()
            assert (Path(cwd) / "solution" / "stats.py").exists()
            return ExecutionResult(0, "contract passed\n", "", "fake-hardened")

    class Kernel:
        workspaces = Workspaces()
        execution = Execution()

    kernel = Kernel()
    result = asyncio.run(
        run_held_out_verification(kernel, "native", task, solution, workspace_root, 1)
    )

    assert result["passed"] is True
    assert result["backend"] == "fake-hardened"
    assert not (solution / "verify.py").exists()
    verifier_workspace, registration = kernel.workspaces.added[0]
    assert registration["writable"] is False
    assert kernel.workspaces.removed == [verifier_workspace]
    _, called_cwd, options = kernel.execution.calls[0]
    assert called_cwd == verifier_workspace
    assert options == {"approved": True, "mutates_state": False}


def test_result_summary_keeps_categories_outcomes_and_latency_distribution():
    results = [
        {
            "loop": "native",
            "category": "bug_fix",
            "passed": True,
            "outcome": "done",
            "denied_attempts": 0,
            "wall_time_s": 1.0,
            "tokens": {"total_tokens": 100, "generated_tokens": 10},
        },
        {
            "loop": "native",
            "category": "security",
            "passed": False,
            "outcome": "harness_timeout",
            "denied_attempts": 1,
            "wall_time_s": 3.0,
            "tokens": {"total_tokens": 300, "generated_tokens": 20},
        },
    ]
    summary = summarise_results(results)["native"]
    assert summary["pass_rate"] == 0.5
    assert summary["median_wall_time_s"] == 2.0
    assert summary["total_tokens"] == 400
    assert summary["median_tokens"] == 200.0
    assert summary["generated_tokens"] == 30
    assert summary["by_category"]["bug_fix"] == {"passed": 1, "total": 1}
    assert summary["outcomes"] == {"done": 1, "harness_timeout": 1}


def test_result_summary_tolerates_an_unavailable_router_counter():
    results = [
        {
            "loop": "native",
            "category": "bug_fix",
            "passed": False,
            "outcome": "harness_timeout",
            "denied_attempts": 0,
            "wall_time_s": 180.0,
            "tokens": {"available": False},
        },
        {
            "loop": "native",
            "category": "bug_fix",
            "passed": True,
            "outcome": "done",
            "denied_attempts": 0,
            "wall_time_s": 20.0,
            "tokens": {"total_tokens": 120, "generated_tokens": 12},
        },
    ]
    summary = summarise_results(results)["native"]
    assert summary["token_accounted_attempts"] == 1
    assert summary["total_tokens"] == 120
    assert summary["median_tokens"] == 120
    assert summary["generated_tokens"] == 12


def test_execution_compatibility_ignores_only_router_lifecycle_fields():
    original = {
        "sha256": "old-wrapper-hash",
        "tool_schema_sha256": "tools",
        "inference": {
            "gguf_sha256": "model",
            "router_model_record": {
                "created": 1,
                "status": {
                    "value": "loaded",
                    "args": [
                        "llama-server",
                        "--port",
                        "45331",
                        "--ctx-size",
                        "32768",
                    ],
                },
            },
        },
    }
    lifecycle_change = json.loads(json.dumps(original))
    lifecycle_change["sha256"] = "new-wrapper-hash"
    lifecycle_change["inference"]["router_model_record"]["created"] = 2
    lifecycle_change["inference"]["router_model_record"]["status"]["value"] = "unloaded"
    lifecycle_change["inference"]["router_model_record"]["status"]["args"][2] = "45999"
    assert execution_compatibility_sha256(original) == execution_compatibility_sha256(
        lifecycle_change
    )

    lifecycle_change["inference"]["router_model_record"]["status"]["args"][-1] = "65536"
    assert execution_compatibility_sha256(original) != execution_compatibility_sha256(
        lifecycle_change
    )


def test_paired_analysis_uses_identical_cells_and_exact_mcnemar():
    results = []
    native = [True, True, True, False]
    prime = [True, False, False, False]
    for attempt, (native_pass, prime_pass) in enumerate(zip(native, prime, strict=True), 1):
        for loop, passed in (("native", native_pass), ("prime", prime_pass)):
            results.append(
                {
                    "loop": loop,
                    "task_id": "paired-task",
                    "attempt": attempt,
                    "passed": passed,
                }
            )
    pair = paired_analysis(results, bootstrap_samples=1_000)["pairs"]["native__vs__prime"]
    assert pair["pass_matrix"] == {
        "both_pass": 1,
        "left_only_pass": 2,
        "right_only_pass": 0,
        "both_fail": 1,
    }
    assert pair["pass_rate_delta"] == 0.5
    assert pair["exact_mcnemar_p"] == 0.5


def test_wsl_paths_bypass_legacy_argument_translation(monkeypatch):
    calls = []

    def fake_check_output(argv, **kwargs):
        calls.append((argv, kwargs))
        return "/mnt/d/repo\n"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    windows_path = r"D:\repo\file.txt"
    assert OpenShellBackend()._wsl_path(windows_path) == "/mnt/d/repo"
    assert DockerBackend()._wsl_path(Path(windows_path)) == "/mnt/d/repo"
    assert all(call[0][:4] == ["wsl", "--exec", "wslpath", "-a"] for call in calls)


def test_docker_backend_availability_requires_local_execution_image(monkeypatch):
    backend = DockerBackend()
    backend._windows_wsl = True
    monkeypatch.setattr(backend, "_native_docker_healthy", lambda: True)
    monkeypatch.setattr(backend, "_wsl_docker_ok", lambda: True)

    inspected = []

    def fake_check_call(argv, **kwargs):
        inspected.append((argv, kwargs))
        if argv[:3] == ["docker", "image", "inspect"]:
            raise subprocess.CalledProcessError(1, argv)
        return 0

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)
    assert backend.available() is True
    assert [call[0][:4] for call in inspected] == [
        ["docker", "image", "inspect", "soai-exec:latest"],
        ["wsl", "docker", "image", "inspect"],
    ]


def test_openshell_requires_authenticated_status_not_only_zero_exit(monkeypatch):
    backend = OpenShellBackend()
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *args, **kwargs: "Connection: Connected\nAuthentication: Failed\n",
    )
    assert backend._sync_status_ok() is False

    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *args, **kwargs: "Connection: Connected\nAuthentication: Authenticated\n",
    )
    assert backend._sync_status_ok() is True


def test_terminal_harness_error_remains_primary_over_verifier_output():
    passed, detail, error = finalise_task_outcome(
        "inference_error",
        {"error": "TimeoutError: generation exceeded its deadline"},
        False,
        "missing authorization header",
    )
    assert passed is False
    assert error == "TimeoutError: generation exceeded its deadline"
    assert detail.startswith("harness did not finish (inference_error): TimeoutError")
    assert detail.endswith("verification: missing authorization header")


def test_only_done_can_retain_a_passing_post_condition():
    passed, _, _ = finalise_task_outcome("budget_exhausted", {"steps_taken": 12}, True, "ok")
    assert passed is False


def test_terminal_diagnostics_retains_bounded_adapter_evidence():
    diagnostics = terminal_diagnostics(
        {"error": "exit 1", "stderr": "prefix-" + "x" * 7000, "stdout": "last output"}
    )
    assert diagnostics["stderr"] == "x" * 6000
    assert diagnostics["stdout"] == "last output"
    assert "error" not in diagnostics


def test_metrics_warmup_is_one_token_and_targets_openai_chat_endpoint(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"{}"

    def fake_urlopen(request, timeout):
        captured.update(request=request, timeout=timeout)
        return Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert warm_model("http://127.0.0.1:18080/v1", "qwen35-9b", timeout=7) is True
    request = captured["request"]
    assert request.full_url == "http://127.0.0.1:18080/v1/chat/completions"
    assert captured["timeout"] == 7
    payload = json.loads(request.data)
    assert payload["model"] == "qwen35-9b"
    assert payload["max_tokens"] == 1


def test_openshell_validates_tree_even_when_sync_back_is_disabled(monkeypatch, tmp_path):
    backend = OpenShellBackend()
    monkeypatch.setattr(backend, "available", lambda: True)
    validated = []

    def reject_tree(path):
        validated.append(path)
        raise ValueError("unsafe tree")

    monkeypatch.setattr(openshell_module, "validate_tree", reject_tree)
    try:
        asyncio.run(backend.run(["true"], str(tmp_path), sync_back=False))
    except ValueError as exc:
        assert str(exc) == "unsafe tree"
    else:
        raise AssertionError("unsafe read-only workspace was not rejected")
    assert validated == [tmp_path.resolve()]


def test_openshell_runs_inside_uploaded_directory_not_its_parent(monkeypatch, tmp_path):
    backend = OpenShellBackend()
    backend._windows_wsl = False
    monkeypatch.setattr(backend, "available", lambda: True)
    calls = []

    async def fake_cli(*args):
        calls.append(args)
        return 0, "", ""

    monkeypatch.setattr(backend, "_cli", fake_cli)
    result = asyncio.run(backend.run(["python3", "verify.py"], str(tmp_path), sync_back=False))

    assert result.returncode == 0
    create = calls[0]
    upload = create[create.index("--upload") + 1]
    assert upload == f"{tmp_path.resolve()}:/sandbox"
    command = create[-1]
    assert f"cd /sandbox/{tmp_path.name}" in command


def test_openshell_downloads_the_uploaded_workspace_directory(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "result.txt").write_text("before", encoding="utf-8")
    backend = OpenShellBackend()
    backend._windows_wsl = False
    monkeypatch.setattr(backend, "available", lambda: True)
    calls = []

    async def fake_cli(*args):
        calls.append(args)
        if args[:2] == ("sandbox", "download"):
            destination = Path(args[-1])
            shutil.copytree(workspace, destination, dirs_exist_ok=True)
            (destination / "result.txt").write_text("after", encoding="utf-8")
        return 0, "", ""

    monkeypatch.setattr(backend, "_cli", fake_cli)
    result = asyncio.run(backend.run(["true"], str(workspace), sync_back=True))

    assert result.returncode == 0
    assert calls[1][3] == workspace.name
    assert (workspace / "result.txt").read_text(encoding="utf-8") == "after"


def test_git_provenance_ignores_only_eol_worktree_differences(monkeypatch):
    calls = []

    class Completed:
        returncode = 0

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return Completed()

    def fake_check_output(argv, **kwargs):
        if "rev-parse" in argv:
            return "abc123\n"
        if "ls-files" in argv:
            return ""
        raise AssertionError(argv)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    assert _git_provenance() == {"head": "abc123", "dirty": False}
    assert len(calls) == 2
    assert all("--ignore-space-at-eol" in argv for argv in calls)
