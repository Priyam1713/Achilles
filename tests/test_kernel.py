import asyncio
import shutil
import time
from pathlib import Path
from typing import ClassVar

import pytest
from starlette.testclient import TestClient

from sovereign_ai.api.server import create_app
from sovereign_ai.kernel.app import SovereignKernel
from sovereign_ai.kernel.config import ConfigBundle
from sovereign_ai.kernel.dispatcher import JobDispatcher, QueueFullError
from sovereign_ai.kernel.jobs import JobStore
from sovereign_ai.kernel.registry import CapabilityRegistry
from sovereign_ai.kernel.runs import RunStore
from sovereign_ai.kernel.types import ActionRequest, CapabilityRequest, RoutingMode, TrustLabel
from sovereign_ai.resources.arbiter import GPUArbiter
from sovereign_ai.resources.gpu_leases import GPULeaseStore
from sovereign_ai.transactions.manager import TransactionManager, TransactionStep

ROOT = Path(__file__).resolve().parents[1]


def kernel(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    k = SovereignKernel.build(str(ROOT / "configs"))
    return k


def test_registry_valid(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    assert k.registry.validate() == []
    assert "reasoning" in k.registry.capabilities()
    assert "computer_use" in k.registry.capabilities()
    assert k.registry.models["autonomous-driving-checkpoint"].status.value == "excluded"
    qwen = k.registry.models["qwen38-27b"]
    assert qwen.source == "Qwen/Qwen3.8-27B"
    assert qwen.artifact["source"] == "unsloth/Qwen3.8-27B-GGUF"


def test_release_radar_never_auto_promotes():
    import yaml

    radar = yaml.safe_load((ROOT / "configs/release-radar.yaml").read_text())
    assert radar["policy"]["auto_promote"] is False
    glm = next(item for item in radar["sources"] if item["id"] == "glm53-open-weights")
    assert glm["lifecycle"] == "announced"
    assert glm["expected"] == "pending"


def test_route_fast_brain(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    d = k.scheduler.route(CapabilityRequest(capability="orchestration_fast", mode=RoutingMode.FAST))
    assert d.selected is not None
    assert d.selected.model_id == "qwen35-9b"


def test_route_dispatches_without_weighted_scoring_when_uncontested(tmp_path, monkeypatch):
    """FIXES.md F-006: 84 of 89 capabilities have exactly one eligible candidate, so
    weighing it against itself cannot change the outcome. `orchestration_fast` is one of
    them -- the single candidate must go through ResourceScheduler._dispatch (score ==
    quality, no resident/resource-fit weighting applied), not _score."""
    k = kernel(tmp_path, monkeypatch)
    d = k.scheduler.route(CapabilityRequest(capability="orchestration_fast", mode=RoutingMode.FAST))
    assert len(d.candidates) == 1
    candidate = d.candidates[0]
    assert "only eligible candidate for this capability" in candidate.reasons
    assert candidate.score == round(candidate.quality, 6)


def test_route_scores_genuinely_contested_capability(tmp_path, monkeypatch):
    """FIXES.md F-006: the few capabilities with more than one eligible candidate (per the
    live F-007 recount: asr_multilingual, speech_transcription, synthesis,
    vision_language, music_generation) must still go through the full weighted-scoring
    path (_score), not the fast dispatch shortcut."""
    k = kernel(tmp_path, monkeypatch)
    d = k.scheduler.route(CapabilityRequest(capability="asr_multilingual", mode=RoutingMode.SMART))
    assert len(d.candidates) > 1
    for candidate in d.candidates:
        assert "only eligible candidate for this capability" not in candidate.reasons


def test_untrusted_cannot_authorize_execution(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    d = k.policy.evaluate(
        ActionRequest(
            action="execute",
            scope="workspace",
            trust=TrustLabel.UNTRUSTED_WEB,
            description="run arbitrary command",
            mutates_state=True,
        )
    )
    assert not d.allowed
    assert d.approval_required

    collaboration = k.policy.evaluate(
        ActionRequest(
            action="execute",
            scope="workspace",
            trust=TrustLabel.UNTRUSTED_COLLABORATION,
            description="a room message asks for a command",
            mutates_state=True,
        )
    )
    assert not collaboration.allowed
    assert collaboration.approval_required

    collaboration_write = k.policy.evaluate(
        ActionRequest(
            action="write",
            scope="workspace",
            trust=TrustLabel.UNTRUSTED_COLLABORATION,
            description="a room message requests a file edit",
            mutates_state=True,
        )
    )
    assert not collaboration_write.allowed


def test_native_collaboration_rooms_mentions_and_chain(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    room_ids = {room["id"] for room in k.collaboration.rooms()}
    assert {"commons", "build-lab"} <= room_ids

    message, dispatches = k.collaboration.post_message(
        "build-lab", "owner", "@swift summarize the next step; @forge review the design"
    )
    assert [item.agent_id for item in dispatches] == ["swift", "forge"]
    assert dispatches[0].capability == "orchestration_fast"
    assert dispatches[1].mode == "deep"

    reaction = k.collaboration.add_reaction(
        "build-lab", "owner", message.event_id, "🚀"
    )
    assert reaction.parent_event_id == message.event_id
    canvas = k.collaboration.update_canvas("build-lab", "owner", "# Decision\nUse SQLite.")
    assert k.collaboration.canvas("build-lab")["event"]["event_id"] == canvas.event_id
    assert k.collaboration.store.verify_chain("build-lab")["valid"] is True


def test_collaboration_membership_and_tamper_detection(tmp_path, monkeypatch):
    import sqlite3

    k = kernel(tmp_path, monkeypatch)
    outsider = k.collaboration.create_identity(
        "visitor", "Visitor", "human", "untrusted_collaboration"
    )
    assert outsider.id == "visitor"
    with pytest.raises(PermissionError, match="not a member"):
        k.collaboration.post_message("commons", "visitor", "hello")

    event, _ = k.collaboration.post_message("commons", "owner", "chain me")
    with sqlite3.connect(k.collaboration.store.path) as connection:
        connection.execute(
            "UPDATE collaboration_events SET payload_json=? WHERE event_id=?",
            ('{"content":"tampered"}', event.event_id),
        )
    verification = k.collaboration.store.verify_chain("commons")
    assert verification["valid"] is False
    assert verification["broken_at"] == event.event_id

    tail, _ = k.collaboration.post_message("build-lab", "owner", "protect the tail")
    with sqlite3.connect(k.collaboration.store.path) as connection:
        connection.execute(
            "DELETE FROM collaboration_events WHERE event_id=?",
            (tail.event_id,),
        )
    verification = k.collaboration.store.verify_chain("build-lab")
    assert verification["valid"] is False
    assert verification["broken_at"] == "room-head-anchor"


def test_memory_fts(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    mid = k.memory.put("semantic", "Qwen is the heavyweight reasoning brain", source="test")
    rows = k.memory.search_lexical("heavyweight reasoning")
    assert any(r["id"] == mid for r in rows)


def test_transaction_rolls_back(tmp_path):
    marks = []

    async def do1():
        marks.append("do1")
        return 1

    async def undo1():
        marks.append("undo1")

    async def do2():
        marks.append("do2")
        raise RuntimeError("boom")

    tx = TransactionManager(tmp_path)
    res = asyncio.run(
        tx.run(
            [
                TransactionStep("one", do1, undo1),
                TransactionStep("two", do2),
            ]
        )
    )
    assert not res.committed
    assert "one" in res.rolled_back
    assert marks == ["do1", "do2", "undo1"]


def test_heavy_brain_prefers_llama_on_target(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    d = k.scheduler.route(CapabilityRequest(capability="reasoning", mode=RoutingMode.DEEP))
    assert d.selected is not None
    assert d.selected.model_id == "qwen38-27b"
    assert d.selected.engine_id == "llama_cpp"


def test_tool_discovery_is_contextual(tmp_path, monkeypatch):
    from sovereign_ai.tools.registry import ToolSpec

    k = kernel(tmp_path, monkeypatch)
    k.tools.register(ToolSpec("git.diff", "inspect repository changes and diffs", ["code"]))
    k.tools.register(ToolSpec("calendar.create", "create a calendar event", ["calendar"]))
    found = k.tools.discover("inspect my code diff", ["code"], limit=1)
    assert found and found[0].id == "git.diff"


def test_local_vector_store(tmp_path):
    from sovereign_ai.memory.vector import LocalVectorStore

    v = LocalVectorStore(tmp_path / "vec.db")
    v.put("a", [1, 0], "alpha")
    v.put("b", [0, 1], "beta")
    assert v.search_vector([0.9, 0.1], limit=1)[0]["id"] == "a"


def test_workspace_registry_rejects_unregistered(tmp_path):
    from sovereign_ai.execution.workspaces import WorkspaceRegistry

    reg = WorkspaceRegistry(tmp_path / "workspaces.json")
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(PermissionError):
        reg.require(project, require_write=True)
    reg.add(project, writable=True)
    assert reg.require(project / "nested", require_write=True)["path"] == str(project.resolve())


def test_staged_reconcile_commits_and_deletes(tmp_path):
    from sovereign_ai.execution.staging import reconcile_workspace, snapshot_tree

    workspace = tmp_path / "workspace"
    staged = tmp_path / "staged"
    workspace.mkdir()
    staged.mkdir()
    (workspace / "keep.txt").write_text("old")
    (workspace / "delete.txt").write_text("bye")
    before = snapshot_tree(workspace)
    (staged / "keep.txt").write_text("new")
    (staged / "created.txt").write_text("hello")
    stats = reconcile_workspace(workspace, staged, before)
    assert (workspace / "keep.txt").read_text() == "new"
    assert not (workspace / "delete.txt").exists()
    assert (workspace / "created.txt").read_text() == "hello"
    assert stats == {"created": 1, "modified": 1, "deleted": 1}


def test_staged_reconcile_refuses_concurrent_host_edit(tmp_path):
    from sovereign_ai.execution.staging import reconcile_workspace, snapshot_tree

    workspace = tmp_path / "workspace"
    staged = tmp_path / "staged"
    workspace.mkdir()
    staged.mkdir()
    (workspace / "x.txt").write_text("before")
    before = snapshot_tree(workspace)
    (staged / "x.txt").write_text("sandbox")
    (workspace / "x.txt").write_text("outside-change")
    with pytest.raises(
        RuntimeError, match="concurrent", check=lambda exc: "concurrent" in str(exc).lower()
    ):
        reconcile_workspace(workspace, staged, before)
    assert (workspace / "x.txt").read_text() == "outside-change"


def test_staging_rejects_escaping_symlink(tmp_path):
    import os

    from sovereign_ai.execution.staging import validate_tree

    root = tmp_path / "root"
    root.mkdir()
    try:
        os.symlink("../escape", root / "bad")
    except (OSError, NotImplementedError):
        return  # Windows without developer-mode symlink privileges.
    with pytest.raises(ValueError, match="symlink"):
        validate_tree(root)


def test_residency_coordinator_is_part_of_kernel(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    assert k.residency.llama_router_url.endswith(":18080")


def test_job_store_lifecycle_and_recovery(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    first = store.create("chat", {"request": {"capability": "reasoning"}})
    assert first.status == "queued"
    store.mark_running(first.id)
    assert store.get(first.id).status == "running"
    store.finish(first.id, "succeeded", result={"answer": "ok"})
    completed = store.get(first.id)
    assert completed.status == "succeeded"
    assert completed.result == {"answer": "ok"}

    interrupted = store.create("media", {"settings": {"prompt": "x"}})
    assert store.recover_interrupted() == 1
    assert store.get(interrupted.id).status == "interrupted"


def test_job_store_cancellation_request(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    job = store.create("specialist", {"operation": "ocr"})
    cancelled = store.request_cancel(job.id)
    assert cancelled is not None
    assert cancelled.cancellation_requested is True


def test_api_exposes_status_and_durable_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    paths = {route.path for route in app.routes}
    assert {"/health", "/status", "/jobs", "/jobs/{job_id}"} <= paths
    assert {
        "/collaboration/status",
        "/collaboration/rooms",
        "/collaboration/rooms/{room_id}/messages",
        "/collaboration/rooms/{room_id}/canvas",
        "/collaboration/rooms/{room_id}/verify",
    } <= paths

def api_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    client = TestClient(app, base_url="http://127.0.0.1")
    client.headers["Authorization"] = f"Bearer {app.state.session_token}"
    return client


def test_mutating_endpoints_require_session_token(tmp_path, monkeypatch):
    """FIXES.md F-004: no mutation endpoint should be reachable without the session token."""
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    client = TestClient(app, base_url="http://127.0.0.1")

    unauthenticated = client.post(
        "/collaboration/rooms", json={"id": "no-auth", "name": "No Auth", "owner_id": "owner"}
    )
    assert unauthenticated.status_code == 401

    wrong_token = client.post(
        "/collaboration/rooms",
        json={"id": "no-auth", "name": "No Auth", "owner_id": "owner"},
        headers={"Authorization": "Bearer not-the-real-token"},
    )
    assert wrong_token.status_code == 401

    authenticated = client.post(
        "/collaboration/rooms",
        json={"id": "auth-room", "name": "Auth Room", "owner_id": "owner"},
        headers={"Authorization": f"Bearer {app.state.session_token}"},
    )
    assert authenticated.status_code == 201

    # Read-only routes remain open; only mutation requires the token.
    assert client.get("/collaboration/rooms").status_code == 200


def test_loopback_only_middleware_rejects_foreign_host(tmp_path, monkeypatch):
    """FIXES.md F-004/F-019: a Host header that does not match this installation must be
    refused before it reaches any route, mutating or not."""
    client = api_client(tmp_path, monkeypatch)
    rebound = client.get("/health", headers={"Host": "attacker.example.com"})
    assert rebound.status_code == 400

    genuine = client.get("/health")
    assert genuine.status_code == 200


def test_create_collaboration_identity_is_not_upsert(tmp_path, monkeypatch):
    """FIXES.md F-003: creation must fail closed on a duplicate id, not silently redefine
    an existing identity's kind/trust/agent configuration."""
    client = api_client(tmp_path, monkeypatch)
    payload = {"id": "duplicate-visitor", "display_name": "Visitor", "kind": "human"}

    first = client.post("/collaboration/identities", json=payload)
    assert first.status_code == 201

    second = client.post(
        "/collaboration/identities",
        json={**payload, "display_name": "Someone Else Entirely"},
    )
    assert second.status_code == 409

    unchanged = client.get("/collaboration/identities").json()
    names = {item["id"]: item["display_name"] for item in unchanged["identities"]}
    assert names["duplicate-visitor"] == "Visitor"

    updated = client.put(
        "/collaboration/identities/duplicate-visitor",
        json={"display_name": "Corrected Name", "kind": "human"},
    )
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Corrected Name"


def test_add_collaboration_member_requires_requester_to_already_belong(tmp_path, monkeypatch):
    """FIXES.md F-002: adding a member must be authorized by an existing member, not open
    to any caller who merely holds the session token."""
    client = api_client(tmp_path, monkeypatch)
    client.post(
        "/collaboration/identities",
        json={"id": "outsider", "display_name": "Outsider", "kind": "human"},
    ).raise_for_status()
    client.post(
        "/collaboration/identities",
        json={"id": "newcomer", "display_name": "Newcomer", "kind": "human"},
    ).raise_for_status()

    denied = client.post(
        "/collaboration/rooms/commons/members/newcomer",
        json={"requester_id": "outsider"},
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/collaboration/rooms/commons/members/newcomer",
        json={"requester_id": "owner"},
    )
    assert allowed.status_code == 204

def test_local_model_overlay_merges_without_touching_the_shared_manifest(tmp_path):
    """configs/models.local.yaml lets one operator route a model (e.g. one accepted under
    a non-default licence for personal use only, per knowledge/research.md invariant 8)
    without editing configs/models.yaml -- the file every community install shares."""
    configs = tmp_path / "configs"
    shutil.copytree(ROOT / "configs", configs)
    # Never trust an incidental real overlay on the machine running this test; the test
    # must be deterministic regardless of what one operator has personally accepted.
    (configs / "models.local.yaml").unlink(missing_ok=True)

    baseline = ConfigBundle(configs)
    baseline_ids = {m["id"] for m in baseline.models["models"]}
    assert "test-only-local-model" not in baseline_ids

    (configs / "models.local.yaml").write_text(
        """
models:
  - id: test-only-local-model
    name: Test-Only Local Model
    source: example/test-only-local-model
    source_type: huggingface
    source_reviewed: true
    status: candidate
    install_policy: local
    capabilities: [reasoning]
    preferred_engines: [llama_cpp]
    quality_prior: 0.5
""",
        encoding="utf-8",
    )
    overlaid = ConfigBundle(configs)
    overlaid_ids = {m["id"] for m in overlaid.models["models"]}
    assert "test-only-local-model" in overlaid_ids
    assert overlaid_ids - baseline_ids == {"test-only-local-model"}

    registry = CapabilityRegistry(overlaid)
    assert registry.validate() == []
    assert "test-only-local-model" in [m.id for m in registry.models_for("reasoning")]

    # No install profile references the local-only id, so a profile-based install can never
    # pull it in -- routing to it requires an explicit capability request.
    for profile in overlaid.install_profiles["profiles"].values():
        assert "test-only-local-model" not in profile.get("models", [])



def test_run_store_tracks_attempt_history(tmp_path):
    """FIXES.md F-010: a retry is a new Run, not a rewrite of the last attempt."""
    runs = RunStore(tmp_path / "runs.db")
    assert runs.next_attempt("job-1") == 1

    first = runs.create("job-1", 1, {"x": 1})
    assert first.attempt == 1
    runs.mark_running(first.id)
    runs.finish(first.id, "failed", error="boom")

    assert runs.next_attempt("job-1") == 2
    second = runs.create("job-1", 2, {"x": 1})
    runs.mark_running(second.id)
    runs.finish(second.id, "succeeded", result={"ok": True})

    history = runs.list_for_job("job-1")
    assert [r.attempt for r in history] == [1, 2]
    assert history[0].status == "failed" and history[0].error == "boom"
    assert history[1].status == "succeeded" and history[1].result == {"ok": True}


def test_run_store_recovers_interrupted(tmp_path):
    runs = RunStore(tmp_path / "runs.db")
    run = runs.create("job-1", 1, {})
    runs.mark_running(run.id)
    assert runs.recover_interrupted() == 1
    assert runs.get(run.id).status == "interrupted"


def test_dispatcher_bounds_concurrency(tmp_path):
    """FIXES.md F-010: submissions beyond max_concurrency queue instead of spawning
    unbounded in-process tasks."""
    jobs = JobStore(tmp_path / "jobs.db")
    runs = RunStore(tmp_path / "runs.db")
    peak = 0
    concurrent = 0
    release = asyncio.Event()

    async def slow_executor(job, run):
        nonlocal peak, concurrent
        concurrent += 1
        peak = max(peak, concurrent)
        await release.wait()
        concurrent -= 1
        return {"ok": True}

    async def drive():
        dispatcher = JobDispatcher(jobs, runs, slow_executor, max_concurrency=2, queue_max=10)
        dispatcher.start()
        for _ in range(4):
            dispatcher.submit(jobs.create("chat", {}))
        await asyncio.sleep(0.05)
        assert dispatcher.active_count == 2
        release.set()
        await asyncio.sleep(0.05)
        await dispatcher.shutdown()

    asyncio.run(drive())
    assert peak == 2


def test_dispatcher_retry_creates_a_new_run_not_a_rewrite(tmp_path):
    jobs = JobStore(tmp_path / "jobs.db")
    runs = RunStore(tmp_path / "runs.db")
    attempts: list[int] = []

    async def flaky_executor(job, run):
        attempts.append(run.attempt)
        if run.attempt == 1:
            raise RuntimeError("first attempt fails")
        return {"ok": True}

    async def drive():
        dispatcher = JobDispatcher(jobs, runs, flaky_executor, max_concurrency=1, queue_max=10)
        dispatcher.start()
        job = jobs.create("chat", {})
        dispatcher.submit(job)
        await asyncio.sleep(0.05)
        dispatcher.submit(jobs.get(job.id))
        await asyncio.sleep(0.05)
        await dispatcher.shutdown()
        return job.id

    job_id = asyncio.run(drive())
    assert attempts == [1, 2]
    history = runs.list_for_job(job_id)
    assert [r.attempt for r in history] == [1, 2]
    assert history[0].status == "failed"
    assert history[1].status == "succeeded"
    assert jobs.get(job_id).status == "succeeded"


def test_dispatcher_cancel_stops_the_active_run(tmp_path):
    jobs = JobStore(tmp_path / "jobs.db")
    runs = RunStore(tmp_path / "runs.db")
    started = asyncio.Event()

    async def blocking_executor(job, run):
        started.set()
        await asyncio.sleep(10)
        return {"ok": True}

    async def drive():
        dispatcher = JobDispatcher(jobs, runs, blocking_executor, max_concurrency=1, queue_max=10)
        dispatcher.start()
        job = jobs.create("chat", {})
        dispatcher.submit(job)
        await started.wait()
        cancelled = dispatcher.cancel(job.id)
        await asyncio.sleep(0.05)
        await dispatcher.shutdown()
        return job.id, cancelled

    job_id, cancelled = asyncio.run(drive())
    assert cancelled is True
    assert jobs.get(job_id).status == "cancelled"


def test_dispatcher_queue_full_fails_closed(tmp_path):
    """FIXES.md F-010: backpressure is explicit, not an unboundedly growing backlog."""
    jobs = JobStore(tmp_path / "jobs.db")
    runs = RunStore(tmp_path / "runs.db")

    async def never_finishes(job, run):
        await asyncio.sleep(10)

    async def drive():
        dispatcher = JobDispatcher(jobs, runs, never_finishes, max_concurrency=1, queue_max=1)
        dispatcher.start()
        dispatcher.submit(jobs.create("chat", {}))  # picked up by the one worker
        await asyncio.sleep(0.02)  # let the worker actually dequeue it
        dispatcher.submit(jobs.create("chat", {}))  # fills the one queue slot
        overflow = jobs.create("chat", {})
        with pytest.raises(QueueFullError):
            dispatcher.submit(overflow)
        await dispatcher.shutdown()
        return overflow.id

    job_id = asyncio.run(drive())
    record = jobs.get(job_id)
    assert record.status == "failed"
    assert "queue is full" in (record.error or "")


def test_job_submission_uses_bounded_dispatcher_and_exposes_run_history(tmp_path, monkeypatch):
    """`with TestClient(...)` matters here, not just style: a bare `TestClient(app)` never
    runs the FastAPI lifespan, so `dispatcher.start()` never fires and no worker ever
    consumes the queue. A Run row is created synchronously at submission time regardless
    (that alone doesn't prove a worker exists), so this test also waits for the job to
    reach a terminal status -- proof a worker actually picked it up and ran the executor,
    not merely that admission succeeded. There is no real inference backend in this test
    environment, so the terminal status is `failed`; that is expected and is not what is
    being asserted."""
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {app.state.session_token}"
        submission = {
            "kind": "chat",
            "payload": {
                "request": {"capability": "reasoning", "mode": "fast"},
                "messages": [{"role": "user", "content": "hi"}],
            },
        }
        response = client.post("/jobs", json=submission)
        assert response.status_code == 202
        job_id = response.json()["id"]

        job = None
        for _ in range(40):
            job = client.get(f"/jobs/{job_id}").json()
            if job["status"] != "queued":
                break
            time.sleep(0.05)
        assert job["status"] in ("running", "succeeded", "failed")

        runs_response = client.get(f"/jobs/{job_id}/runs")
        assert runs_response.status_code == 200
        attempts = runs_response.json()["runs"]
        assert len(attempts) == 1
        assert attempts[0]["attempt"] == 1
        assert attempts[0]["job_id"] == job_id


def test_gpu_lease_store_serializes_exclusive_leases(tmp_path):
    """FIXES.md F-011: an exclusive lease held by one holder blocks a second exclusive
    acquire until it is released, purely via the durable store -- no shared in-memory
    object involved."""
    store = GPULeaseStore(tmp_path / "gpu-leases.db")
    first = store.try_acquire("owner-a", exclusive=True, ttl_seconds=60)
    assert first is not None
    assert store.try_acquire("owner-b", exclusive=True, ttl_seconds=60) is None
    store.release(first.id)
    second = store.try_acquire("owner-b", exclusive=True, ttl_seconds=60)
    assert second is not None


def test_gpu_lease_store_reaps_leases_from_dead_processes(tmp_path):
    """A crashed holder must not wedge the GPU forever. An in-memory semaphore cannot
    distinguish 'still running' from 'crashed'; this store checks the recorded PID."""
    import sqlite3

    store = GPULeaseStore(tmp_path / "gpu-leases.db")
    dead_pid = 999_999_999  # astronomically unlikely to be a real running process
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "INSERT INTO gpu_leases(id,owner,exclusive,pid,acquired_at,expires_at) VALUES(?,?,?,?,?,?)",
            ("orphan", "dead-owner", 1, dead_pid, time.time(), time.time() + 3600),
        )
    # A naive TTL check alone would not reap this -- it has an hour left. Only the
    # liveness check does.
    assert store.try_acquire("owner-b", exclusive=True, ttl_seconds=60) is not None


def test_gpu_lease_store_reaps_expired_ttl(tmp_path):
    store = GPULeaseStore(tmp_path / "gpu-leases.db")
    lease = store.try_acquire("owner-a", exclusive=True, ttl_seconds=0.01)
    assert lease is not None
    time.sleep(0.05)
    assert store.active() == []


def test_arbiter_lease_is_durable_across_separate_arbiter_instances(tmp_path):
    """The actual claim of FIXES.md F-011: two independent GPUArbiter objects (standing in
    for two kernel processes) sharing only a state directory must still serialize an
    exclusive lease. Two separate in-process asyncio.Semaphores could never do this on
    their own -- proving the durable store, not the semaphore, is what makes this true."""
    arbiter_a = GPUArbiter(max_heavy_jobs=1, state_dir=tmp_path, ttl_seconds=10)
    arbiter_b = GPUArbiter(max_heavy_jobs=1, state_dir=tmp_path, ttl_seconds=10)
    events: list[str] = []
    second_acquired = asyncio.Event()

    async def hold_from_b():
        async with arbiter_b.lease("process-b", exclusive=True):
            events.append("b-acquired")
            second_acquired.set()

    async def drive():
        task = None
        async with arbiter_a.lease("process-a", exclusive=True):
            events.append("a-acquired")
            task = asyncio.create_task(hold_from_b())
            await asyncio.sleep(0.1)
            assert not second_acquired.is_set(), "b acquired while a still held the lease"
            events.append("a-releasing")
            # exiting this `async with` block is what actually releases a's lease; b must
            # not be able to proceed until that happens, which is why we await it below
            # rather than inside this block.
        await task
        return events

    result = asyncio.run(drive())
    assert result.index("a-acquired") < result.index("a-releasing") < result.index("b-acquired")


def test_migration_runner_applies_in_order_and_is_idempotent(tmp_path):
    from sovereign_ai.kernel.migrations import Migration, MigrationRunner

    db_path = tmp_path / "example.db"
    migrations = [
        Migration(1, "create_widgets", "CREATE TABLE IF NOT EXISTS widgets(id TEXT PRIMARY KEY);"),
        Migration(2, "add_widget_name", "ALTER TABLE widgets ADD COLUMN name TEXT;"),
    ]
    runner = MigrationRunner(db_path, migrations)
    assert runner.current_version() == 0
    assert runner.apply_pending() == [1, 2]
    assert runner.current_version() == 2
    # Re-running is a no-op, not a re-application (ALTER TABLE ADD COLUMN twice would error).
    assert runner.apply_pending() == []

    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute("INSERT INTO widgets(id, name) VALUES('w1','hello')")
        row = connection.execute("SELECT name FROM widgets WHERE id='w1'").fetchone()
    assert row == ("hello",)


def test_migration_runner_rejects_non_contiguous_or_duplicate_versions(tmp_path):
    from sovereign_ai.kernel.migrations import Migration, MigrationRunner

    with pytest.raises(ValueError, match="contiguous"):
        MigrationRunner(tmp_path / "a.db", [Migration(1, "one", "SELECT 1;"), Migration(3, "three", "SELECT 1;")])
    with pytest.raises(ValueError, match="duplicate"):
        MigrationRunner(tmp_path / "b.db", [Migration(1, "one", "SELECT 1;"), Migration(1, "one-again", "SELECT 1;")])


def test_backup_and_restore_round_trip(tmp_path):
    from sovereign_ai.kernel.backup import backup_database, restore_database

    runs = RunStore(tmp_path / "runs.db")
    runs.create("job-1", 1, {"note": "before backup"})

    snapshot = backup_database(runs.path, tmp_path / "backups")
    assert snapshot.exists()

    # Simulate damage to the live database after the backup was taken.
    runs.create("job-1", 2, {"note": "after backup, should not survive restore"})
    assert len(runs.list_for_job("job-1")) == 2

    restore_database(snapshot, runs.path)
    restored = RunStore(runs.path)
    history = restored.list_for_job("job-1")
    assert len(history) == 1
    assert history[0].request == {"note": "before backup"}


class _FakeInference:
    """Scripted inference broker for NativeAgentLoop tests: returns each of `replies` in
    order as the model's message content, without needing a live backend."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.calls = 0

    async def chat(self, request, messages, model_overrides=None):
        self.calls += 1
        content = self._replies.pop(0) if self._replies else '{"tool": "done", "summary": "out of script"}'
        return {"result": {"choices": [{"message": {"content": content}}]}}


def test_native_agent_loop_reads_a_file_then_finishes(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("the answer is 42", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    fake = _FakeInference(
        [
            f'{{"tool": "read_file", "args": {{"path": "{(workspace / "notes.txt").as_posix()}"}}}}',
            '{"tool": "done", "summary": "the answer is 42"}',
        ]
    )
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events)
    state = {"run_id": "test-run-1", "task": "find the answer", "workspace": str(workspace)}

    async def drive():
        steps = []
        while True:
            step = await loop.next_step(state)
            steps.append(step)
            if step.done:
                return steps

    steps = asyncio.run(drive())
    assert fake.calls == 2
    assert steps[0].kind == "observation"
    assert "42" in steps[0].payload["observation"]["content"]
    assert steps[-1].kind == "done"
    assert steps[-1].payload["summary"] == "the answer is 42"

    # Every step is independently auditable, not just trusted because the loop finished.
    events = list(k.events.read_stream("agent-loop:test-run-1"))
    assert [e["event_type"] for e in events] == ["agent.step.tool_call", "agent.step.done"]
    assert all(e["trust"] == "untrusted_model_output" for e in events)


def test_native_agent_loop_denies_unapproved_mutation(tmp_path, monkeypatch):
    """FIXES.md's own security stance, exercised through the loop: untrusted model output
    cannot authorize a mutating action without explicit approval."""
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)

    fake = _FakeInference(
        [
            '{"tool": "run_command", "args": {"argv": ["rm", "-rf", "everything"], "mutates_state": true}}',
            '{"tool": "done", "summary": "gave up after denial"}',
        ]
    )
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events)
    state = {
        "run_id": "test-run-2",
        "task": "delete everything",
        "workspace": str(workspace),
        "approved": False,
    }

    async def drive():
        first = await loop.next_step(state)
        second = await loop.next_step(state)
        return first, second

    first, second = asyncio.run(drive())
    assert first.kind == "observation"
    assert "denied" in first.payload["observation"]["error"].lower()
    assert second.kind == "done"


def test_native_agent_loop_respects_step_budget(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)

    # The model never calls "done" -- the loop's own budget must stop it regardless.
    fake = _FakeInference([f'{{"tool": "list_directory", "args": {{"path": "{workspace.as_posix()}"}}}}'] * 20)
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events)
    state = {"run_id": "test-run-3", "task": "loop forever", "workspace": str(workspace), "max_steps": 3}

    async def drive():
        steps = []
        while True:
            step = await loop.next_step(state)
            steps.append(step)
            if step.done:
                return steps

    steps = asyncio.run(drive())
    # max_steps=3 real attempts, then one budget_exhausted marker step.
    assert len(steps) == 4
    assert [s.kind for s in steps[:3]] == ["observation"] * 3
    assert steps[-1].kind == "budget_exhausted"
    assert steps[-1].payload["steps_taken"] == 3


def test_native_agent_loop_handles_unparsable_reply_without_crashing(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)

    fake = _FakeInference(["Sure! I'll help with that.", '{"tool": "done", "summary": "recovered"}'])
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events)
    state = {"run_id": "test-run-4", "task": "anything", "workspace": str(workspace)}

    async def drive():
        first = await loop.next_step(state)
        second = await loop.next_step(state)
        return first, second

    first, second = asyncio.run(drive())
    assert first.kind == "unparsable"
    assert not first.done
    assert second.kind == "done"


def test_agent_job_end_to_end_through_dispatcher(tmp_path, monkeypatch):
    """The full path: POST /jobs {kind: agent} -> dispatcher -> job_executor._run_agent_loop
    -> NativeAgentLoop, using the kernel's real (fake-inference-swapped) loop registration.

    Uses `with TestClient(...) as client` deliberately: a bare `TestClient(app)` never runs
    the FastAPI `lifespan`, so `dispatcher.start()` never fires and no worker ever consumes
    the queue -- a job would sit at `queued` forever. Discovered by this test the first time
    it was written with a bare client, which is exactly why it exists.
    """
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {app.state.session_token}"
        kernel_obj = app.state.kernel
        workspace = tmp_path / "agent-ws"
        workspace.mkdir()
        kernel_obj.workspaces.add(workspace, writable=False)
        fake = _FakeInference(['{"tool": "done", "summary": "task complete"}'])
        kernel_obj.agent_loops.register(
            "native", NativeAgentLoop(fake, kernel_obj.execution, kernel_obj.workspaces, kernel_obj.events)
        )

        submission = {
            "kind": "agent",
            "payload": {"task": "say hello", "workspace": str(workspace), "max_steps": 5},
        }
        response = client.post("/jobs", json=submission)
        assert response.status_code == 202
        job_id = response.json()["id"]

        job = None
        for _ in range(40):
            job = client.get(f"/jobs/{job_id}").json()
            if job["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.05)
        assert job["status"] == "succeeded"
        assert job["result"]["final"]["summary"] == "task complete"


def test_quality_eval_task_checkers_are_actually_discriminating():
    """The checkers in scripts/quality_eval_tasks.py are what makes this a graded eval
    rather than a vibe check -- they must correctly pass a genuinely correct answer and
    fail a genuinely wrong one, independent of any live model."""
    from quality_eval_tasks import TASKS

    by_id = {t.id: t for t in TASKS}

    correct_palindrome = "```python\ndef is_palindrome(s: str) -> bool:\n    cleaned = ''.join(c.lower() for c in s if c.isalnum())\n    return cleaned == cleaned[::-1]\n```"
    passed, _ = by_id["coding-palindrome"].check(correct_palindrome)
    assert passed
    wrong_palindrome = "```python\ndef is_palindrome(s: str) -> bool:\n    return True\n```"
    passed, _ = by_id["coding-palindrome"].check(wrong_palindrome)
    assert not passed

    correct_fix = "```python\ndef sum_range(a: int, b: int) -> int:\n    total = 0\n    for i in range(a, b + 1):\n        total += i\n    return total\n```"
    passed, _ = by_id["coding-fix-off-by-one"].check(correct_fix)
    assert passed
    still_buggy = "```python\ndef sum_range(a: int, b: int) -> int:\n    total = 0\n    for i in range(a, b):\n        total += i\n    return total\n```"
    passed, _ = by_id["coding-fix-off-by-one"].check(still_buggy)
    assert not passed

    task = by_id["reasoning-multi-step"]
    passed, detail = task.check(f"Working shown here.\nFinal answer: {(84 - 3) * 12 * 0.85:.0f}")
    assert passed, detail
    passed, _ = task.check("Working shown here.\nFinal answer: 999999")
    assert not passed

    bullets_task = by_id["instruction-following-bullets"]
    passed, _ = bullets_task.check("- one\n- two\n- three")
    assert passed
    passed, _ = bullets_task.check("- one\n- two")
    assert not passed
    passed, _ = bullets_task.check("Here are some points:\n- one\n- two\n- three\n- four")
    assert not passed


def test_quality_eval_task_suite_covers_multiple_categories():
    from quality_eval_tasks import TASKS

    categories = {t.category for t in TASKS}
    assert {"coding", "reasoning", "instruction_following"} <= categories
    assert len({t.id for t in TASKS}) == len(TASKS), "task ids must be unique"


def test_extract_message_content_falls_back_to_reasoning_content():
    """FIXES.md F-028: a thinking-mode model whose generation was cut off by max_tokens
    before it finished reasoning leaves `content` empty but `reasoning_content` populated.
    Treating that as 'no output' is the actual bug that was found live; this locks the fix."""
    from sovereign_ai.inference.content import extract_message_content

    with_content = {"choices": [{"message": {"content": "25", "reasoning_content": "..."}}]}
    assert extract_message_content(with_content) == "25"

    cut_off_mid_thought = {
        "choices": [{"message": {"content": "", "reasoning_content": "Let me think... 12+13="}}]
    }
    assert extract_message_content(cut_off_mid_thought) == "Let me think... 12+13="

    truly_empty = {"choices": [{"message": {"content": "", "reasoning_content": ""}}]}
    assert extract_message_content(truly_empty) == ""

    no_choices = {"choices": []}
    assert extract_message_content(no_choices) == ""

    no_reasoning_field_at_all = {"choices": [{"message": {"content": "plain answer"}}]}
    assert extract_message_content(no_reasoning_field_at_all) == "plain answer"


class _FakeSpecialists:
    """Scripted specialist broker for SpecialistVectorRetriever/MemoryIndexer tests."""

    def __init__(self, embeddings: dict[str, list[float]], rerank_order: list[int] | None = None):
        self.embeddings = embeddings
        self.rerank_order = rerank_order
        self.embed_calls: list[list[str]] = []
        self.rerank_calls: list[tuple] = []

    async def invoke(self, request, operation, inputs, options=None, timeout_s=300.0):
        if operation == "embed":
            texts = inputs["texts"]
            self.embed_calls.append(texts)
            return {"result": [self.embeddings[t] for t in texts]}
        if operation == "rerank":
            candidates = inputs["candidates"]
            self.rerank_calls.append((inputs["query"], candidates))
            order = self.rerank_order if self.rerank_order is not None else list(range(len(candidates)))
            return {
                "result": [
                    {"index": i, "score": 1.0 - position * 0.1, "candidate": candidates[i]}
                    for position, i in enumerate(order)
                ]
            }
        raise ValueError(f"unexpected operation: {operation}")


def test_specialist_vector_retriever_two_stage_embed_then_rerank(tmp_path):
    """FIXES.md: closes the embedding -> rerank -> context gap named in
    docs/IMPLEMENTATION_STATUS.md. Proves reranking actually changes result order rather
    than merely passing first-stage vector similarity through unchanged."""
    from sovereign_ai.memory.retrieval_adapter import SpecialistVectorRetriever
    from sovereign_ai.memory.vector import LocalVectorStore

    store = LocalVectorStore(tmp_path / "vec.db")
    # First-stage vector similarity would rank these a, b, c (closest to [1,0] first).
    store.put("a", [1.0, 0.0], content="alpha content", source="test")
    store.put("b", [0.9, 0.1], content="beta content", source="test")
    store.put("c", [0.8, 0.2], content="gamma content", source="test")

    fake = _FakeSpecialists(embeddings={"find alpha": [1.0, 0.0]}, rerank_order=[2, 0, 1])
    retriever = SpecialistVectorRetriever(fake, store, first_stage_multiplier=4)

    async def drive():
        return await retriever.search("find alpha", limit=3)

    results = asyncio.run(drive())
    assert fake.embed_calls == [["find alpha"]]
    assert len(fake.rerank_calls) == 1
    # The reranker's order [2, 0, 1] must win over vector similarity's [a, b, c] order.
    assert [r["content"] for r in results] == ["gamma content", "alpha content", "beta content"]
    assert results[0]["score"] == 1.0


def test_specialist_vector_retriever_returns_empty_when_index_is_empty(tmp_path):
    from sovereign_ai.memory.retrieval_adapter import SpecialistVectorRetriever
    from sovereign_ai.memory.vector import LocalVectorStore

    store = LocalVectorStore(tmp_path / "vec.db")
    fake = _FakeSpecialists(embeddings={"anything": [1.0, 0.0]})
    retriever = SpecialistVectorRetriever(fake, store)

    async def drive():
        return await retriever.search("anything", limit=5)

    results = asyncio.run(drive())
    assert results == []
    # No candidates to rerank -- must not call the reranker with an empty list.
    assert fake.rerank_calls == []


def test_memory_indexer_embeds_and_stores_into_vector_store(tmp_path):
    from sovereign_ai.memory.retrieval_adapter import MemoryIndexer
    from sovereign_ai.memory.vector import LocalVectorStore

    store = LocalVectorStore(tmp_path / "vec.db")
    fake = _FakeSpecialists(embeddings={"remember this": [0.0, 1.0]})
    indexer = MemoryIndexer(fake, store)

    async def drive():
        await indexer.index("mem-1", "remember this", source="test", trust="trusted_local")

    asyncio.run(drive())
    hits = store.search_vector([0.0, 1.0], limit=5)
    assert len(hits) == 1
    assert hits[0]["id"] == "mem-1"
    assert hits[0]["content"] == "remember this"
    assert hits[0]["source"] == "test"


def test_context_builder_uses_wired_vector_retriever_from_kernel(tmp_path, monkeypatch):
    """The actual defect this closes: ContextBuilder's text_vector slot existed but
    kernel/app.py never passed anything into it, so context assembly was lexical-only
    regardless of what retrieval models were installed."""
    k = kernel(tmp_path, monkeypatch)
    from sovereign_ai.memory.retrieval_adapter import SpecialistVectorRetriever

    assert isinstance(k.context.text_vector, SpecialistVectorRetriever)
    assert k.context.text_vector.specialists is k.specialists
    assert k.context.text_vector.vector_store is k.vector_store
    assert k.memory_indexer.vector_store is k.vector_store


def test_local_vector_store_delete_removes_row(tmp_path):
    """FIXES.md F-008: supersession must be able to purge the old vector, not just
    add a new one alongside it forever."""
    from sovereign_ai.memory.vector import LocalVectorStore

    v = LocalVectorStore(tmp_path / "vec.db")
    v.put("a", [1, 0], "alpha")
    v.put("b", [0, 1], "beta")
    v.delete("a")
    hits = v.search_vector([1, 0], limit=5)
    assert [h["id"] for h in hits] == ["b"]


def test_local_vector_store_search_ranks_by_cosine_similarity_at_scale(tmp_path):
    """Correctness check on the vectorized (numpy) scoring path, not just the two-row
    smoke test above: with many stored vectors of mixed norm, the nearest neighbour by
    cosine similarity must still win, proving the batched matrix-vector product wasn't
    a silent behavior change (FIXES.md F-008)."""
    import random

    from sovereign_ai.memory.vector import LocalVectorStore

    rng = random.Random(7)
    v = LocalVectorStore(tmp_path / "vec.db")
    for i in range(500):
        vec = [rng.uniform(-1, 1) for _ in range(16)]
        v.put(f"noise-{i}", vec, f"noise {i}")
    target = [1.0] + [0.0] * 15
    v.put("target", [5.0] + [0.0] * 15, "the target, scaled up so norm alone can't win")
    hits = v.search_vector(target, limit=3)
    assert hits[0]["id"] == "target"
    assert hits[0]["score"] > 0.999


def test_memory_store_put_with_supersedes_retires_old_memory_from_fts(tmp_path):
    """FIXES.md F-008: 'the FTS table has no delete or update path, so it desynchronizes
    on the first supersession' -- a superseded memory must stop surfacing in lexical
    search, while its row stays in `memories` for provenance/audit."""
    from sovereign_ai.memory.store import MemoryStore

    store = MemoryStore(tmp_path / "mem.db")
    old_id = store.put("fact", "the sky is green", source="test")
    assert store.search_lexical("green")

    new_id = store.put("fact", "the sky is blue", source="test", supersedes=old_id)
    hits = store.search_lexical("green")
    assert hits == []
    assert [h["id"] for h in store.search_lexical("blue")] == [new_id]

    with store._connect() as con:
        row = con.execute("SELECT id, supersedes FROM memories WHERE id=?", (old_id,)).fetchone()
    assert row is not None and row["id"] == old_id


def test_memory_indexer_supersedes_purges_old_vector(tmp_path):
    from sovereign_ai.memory.retrieval_adapter import MemoryIndexer
    from sovereign_ai.memory.vector import LocalVectorStore

    store = LocalVectorStore(tmp_path / "vec.db")
    fake = _FakeSpecialists(
        embeddings={"the sky is green": [1.0, 0.0], "the sky is blue": [0.0, 1.0]}
    )
    indexer = MemoryIndexer(fake, store)

    async def drive():
        await indexer.index("mem-old", "the sky is green")
        await indexer.index("mem-new", "the sky is blue", supersedes="mem-old")

    asyncio.run(drive())
    hits = store.search_vector([1.0, 0.0], limit=5)
    assert [h["id"] for h in hits] == ["mem-new"]


# --- Tier 5: persistent-agency domain -------------------------------------------------


def test_agent_profile_store_create_get_list_and_ceiling(tmp_path):
    from sovereign_ai.kernel.agent_profiles import AgentProfileAlreadyExists, AgentProfileStore

    store = AgentProfileStore(tmp_path / "profiles.db")
    profile = store.create(
        "swift", "Swift", "fast-orchestrator", authority_ceiling=["execute:workspace"]
    )
    assert profile.status == "active"
    assert store.get("swift") == profile
    assert [p.id for p in store.list()] == ["swift"]
    assert store.has_ceiling("swift", "execute:workspace")
    assert not store.has_ceiling("swift", "delete:host")
    assert not store.has_ceiling("unknown-profile", "execute:workspace")

    with pytest.raises(AgentProfileAlreadyExists):
        store.create("swift", "Swift Duplicate", "role")

    retired = store.set_status("swift", "retired")
    assert retired.status == "retired"


def test_approval_request_store_lifecycle(tmp_path):
    from sovereign_ai.kernel.approvals import ApprovalRequestStore

    store = ApprovalRequestStore(tmp_path / "approvals.db")
    req = store.create("swift", "execute", "host", "high", "needs a human")
    assert req.status == "pending"
    assert [r.id for r in store.list_pending()] == [req.id]

    resolved = store.resolve(req.id, "owner", True, "looks fine")
    assert resolved.status == "approved"
    assert resolved.resolver_id == "owner"
    assert store.list_pending() == []

    with pytest.raises(ValueError, match="already"):
        store.resolve(req.id, "owner", True, "again")

    with pytest.raises(ValueError, match="Unknown"):
        store.resolve("does-not-exist", "owner", True, "n/a")


def test_approval_request_store_expires_and_cannot_be_resolved_after(tmp_path):
    from sovereign_ai.kernel.approvals import ApprovalRequestStore

    store = ApprovalRequestStore(tmp_path / "approvals.db")
    req = store.create("swift", "execute", "host", "high", "stale test", ttl_seconds=-1)
    assert store.list_pending() == []  # expire_stale() runs inside list_pending()

    with pytest.raises(ValueError, match="expired"):
        store.resolve(req.id, "owner", True, "too late")


def test_capability_grant_store_issue_is_active_and_revoke(tmp_path):
    from sovereign_ai.kernel.capability_grants import CapabilityGrantStore

    store = CapabilityGrantStore(tmp_path / "grants.db")
    assert not store.is_active("swift", "execute", "workspace")

    grant = store.issue("swift", "execute", "workspace", "policy", ttl_seconds=3600)
    assert store.is_active("swift", "execute", "workspace")
    assert not store.is_active("swift", "execute", "host"), "scope must not leak across grants"
    assert [g.id for g in store.active_for_subject("swift")] == [grant.id]

    store.revoke(grant.id)
    assert not store.is_active("swift", "execute", "workspace")


def test_capability_grant_store_expires_by_ttl(tmp_path):
    from sovereign_ai.kernel.capability_grants import CapabilityGrantStore

    store = CapabilityGrantStore(tmp_path / "grants.db")
    store.issue("swift", "execute", "workspace", "policy", ttl_seconds=-1)
    assert not store.is_active("swift", "execute", "workspace")


def test_workspace_lease_store_exclusive_write_conflict(tmp_path):
    from sovereign_ai.resources.workspace_leases import WorkspaceLeaseStore

    store = WorkspaceLeaseStore(tmp_path / "leases.db")
    write_lease = store.try_acquire("/repo", "run-1", writable=True, ttl_seconds=60)
    assert write_lease is not None
    assert store.is_leased(write_lease.id, "run-1")

    # A second writable lease on the same root must not be granted while one is held.
    assert store.try_acquire("/repo", "run-2", writable=True, ttl_seconds=60) is None
    # Nor may a read-only lease be granted while a write lease is active.
    assert store.try_acquire("/repo", "run-2", writable=False, ttl_seconds=60) is None

    store.release(write_lease.id)
    assert store.try_acquire("/repo", "run-2", writable=True, ttl_seconds=60) is not None


def test_workspace_lease_store_multiple_readers_allowed(tmp_path):
    from sovereign_ai.resources.workspace_leases import WorkspaceLeaseStore

    store = WorkspaceLeaseStore(tmp_path / "leases.db")
    first = store.try_acquire("/repo", "run-1", writable=False, ttl_seconds=60)
    second = store.try_acquire("/repo", "run-2", writable=False, ttl_seconds=60)
    assert first is not None
    assert second is not None


def test_workspace_lease_store_reaps_expired(tmp_path):
    from sovereign_ai.resources.workspace_leases import WorkspaceLeaseStore

    store = WorkspaceLeaseStore(tmp_path / "leases.db")
    store.try_acquire("/repo", "run-1", writable=True, ttl_seconds=-1)
    assert store.active() == []


class _FakeConfig:
    """Minimal stand-in for ConfigBundle, just enough for PolicyEngine.__init__."""

    policies: ClassVar[dict] = {
        "defaults": {"fail_closed": True},
        "risk_rules": [
            {"match": {"action": "read", "scope": "workspace"}, "risk": "low", "approval": False},
            {"match": {"action": "execute", "scope": "workspace"}, "risk": "medium", "approval": False},
        ],
    }


def test_roster_service_rejects_grant_outside_authority_ceiling(tmp_path):
    from sovereign_ai.kernel.agent_profiles import AgentProfileStore
    from sovereign_ai.kernel.approvals import ApprovalRequestStore
    from sovereign_ai.kernel.capability_grants import CapabilityGrantStore
    from sovereign_ai.kernel.delegations import DelegationStore
    from sovereign_ai.kernel.jobs import JobStore
    from sovereign_ai.kernel.policy import PolicyEngine
    from sovereign_ai.kernel.roster import RosterService

    profiles = AgentProfileStore(tmp_path / "profiles.db")
    profiles.create("swift", "Swift", "role", authority_ceiling=["execute:workspace"])
    roster = RosterService(
        profiles,
        DelegationStore(tmp_path / "delegations.db"),
        CapabilityGrantStore(tmp_path / "grants.db"),
        ApprovalRequestStore(tmp_path / "approvals.db"),
        JobStore(tmp_path / "jobs.db"),
        PolicyEngine(_FakeConfig()),
    )
    with pytest.raises(PermissionError, match="authority ceiling"):
        roster.propose_delegation(
            "swift", "delete the host", [{"action": "delete", "scope": "host"}]
        )


def _roster_with_fake_policy(tmp_path):
    from sovereign_ai.kernel.agent_profiles import AgentProfileStore
    from sovereign_ai.kernel.approvals import ApprovalRequestStore
    from sovereign_ai.kernel.capability_grants import CapabilityGrantStore
    from sovereign_ai.kernel.delegations import DelegationStore
    from sovereign_ai.kernel.jobs import JobStore
    from sovereign_ai.kernel.policy import PolicyEngine
    from sovereign_ai.kernel.roster import RosterService

    profiles = AgentProfileStore(tmp_path / "profiles.db")
    profiles.create(
        "swift", "Swift", "role", authority_ceiling=["read:workspace", "execute:workspace"]
    )
    roster = RosterService(
        profiles,
        DelegationStore(tmp_path / "delegations.db"),
        CapabilityGrantStore(tmp_path / "grants.db"),
        ApprovalRequestStore(tmp_path / "approvals.db"),
        JobStore(tmp_path / "jobs.db"),
        PolicyEngine(_FakeConfig()),
    )
    return roster


def test_roster_service_grants_immediately_when_policy_does_not_require_approval(tmp_path):
    roster = _roster_with_fake_policy(tmp_path)
    delegation, job = roster.propose_delegation(
        "swift",
        "read the repo",
        [{"action": "read", "scope": "workspace", "mutates_state": False, "uses_credentials": False}],
    )
    assert delegation.status == "approved"
    assert job is not None
    assert job.request["delegation_id"] == delegation.id
    assert roster.grants.is_active("swift", "read", "workspace")


def test_roster_service_awaits_approval_when_policy_requires_it(tmp_path):
    """FIXES.md Tier 5: this is the safety property the whole domain exists for -- an
    agent-to-agent delegation requesting `execute` must not silently become authority.
    Untrusted-collaboration trust plus an execute action forces PolicyEngine's
    approval_required gate regardless of the (permissive, in this fake config) risk rule
    for execute:workspace."""
    roster = _roster_with_fake_policy(tmp_path)
    delegation, job = roster.propose_delegation(
        "swift", "run a command", [{"action": "execute", "scope": "workspace"}]
    )
    assert delegation.status == "awaiting_approval"
    assert job is None
    assert not roster.grants.is_active("swift", "execute", "workspace")

    pending = roster.approvals.list_pending()
    assert len(pending) == 1
    assert pending[0].subject_id == "swift"
    assert pending[0].evidence["delegation_id"] == delegation.id

    approval, resolved_job = roster.resolve_approval(pending[0].id, "owner", True, "approved by owner")
    assert approval.status == "approved"
    assert resolved_job is not None
    assert resolved_job.request["delegation_id"] == delegation.id
    assert roster.grants.is_active("swift", "execute", "workspace")
    assert roster.delegations.get(delegation.id).status == "approved"


def test_roster_service_denial_rejects_delegation_without_a_job(tmp_path):
    roster = _roster_with_fake_policy(tmp_path)
    delegation, job = roster.propose_delegation(
        "swift", "run a command", [{"action": "execute", "scope": "workspace"}]
    )
    assert job is None

    pending = roster.approvals.list_pending()
    approval, resolved_job = roster.resolve_approval(pending[0].id, "owner", False, "too risky")
    assert approval.status == "denied"
    assert resolved_job is None
    assert not roster.grants.is_active("swift", "execute", "workspace")
    assert roster.delegations.get(delegation.id).status == "rejected"


def test_roster_service_denial_revokes_grants_already_issued_by_the_same_delegation(tmp_path):
    """A delegation requesting two grants -- one policy allows immediately, one it holds
    for approval -- must not partially proceed if the approval is denied. The already-
    issued grant is tagged with this delegation's id specifically so revocation is precise
    (an unrelated grant sharing the same action/scope must never be touched by this)."""
    roster = _roster_with_fake_policy(tmp_path)
    delegation, job = roster.propose_delegation(
        "swift",
        "read then execute",
        [
            {"action": "read", "scope": "workspace", "mutates_state": False, "uses_credentials": False},
            {"action": "execute", "scope": "workspace"},
        ],
    )
    assert job is None
    assert delegation.status == "awaiting_approval"
    assert roster.grants.is_active("swift", "read", "workspace"), "the ungated grant should issue immediately"

    pending = roster.approvals.list_pending()
    assert len(pending) == 1
    roster.resolve_approval(pending[0].id, "owner", False, "denying the execute half")

    assert not roster.grants.is_active("swift", "read", "workspace"), (
        "denial must revoke grants already issued for this same delegation's other actions"
    )
    assert not roster.grants.is_active("swift", "execute", "workspace")
    assert roster.delegations.get(delegation.id).status == "rejected"


def test_roster_wired_into_kernel(tmp_path, monkeypatch):
    """Proves this is really assembled by SovereignKernel.build, not just importable."""
    k = kernel(tmp_path, monkeypatch)
    profile = k.roster.create_profile("swift", "Swift", "role", authority_ceiling=["read:workspace"])
    assert k.agent_profiles.get("swift") == profile


def test_collaboration_identity_can_link_and_preserve_agent_profile(tmp_path, monkeypatch):
    """FIXES.md Tier 5: a collaboration identity is a room address that references an
    AgentProfile, not a second identity database. update_identity must never silently
    clear the link (it doesn't accept the field at all) -- only link_agent_profile does."""
    k = kernel(tmp_path, monkeypatch)
    k.roster.create_profile("swift", "Swift", "role")
    identity = k.collaboration.create_identity(
        "swift-bot", "Swift Bot", "agent", "trusted_local",
        agent={"capability": "orchestration_fast", "mode": "fast"},
        agent_profile_id="swift",
    )
    assert identity.agent_profile_id == "swift"

    updated = k.collaboration.update_identity(
        "swift-bot", "Swift Bot Renamed", "agent", "trusted_local",
        agent={"capability": "orchestration_fast", "mode": "fast"},
    )
    assert updated.agent_profile_id == "swift", "unrelated update must not clear the link"

    unlinked = k.collaboration.link_agent_profile("swift-bot", None)
    assert unlinked.agent_profile_id is None


def test_roster_http_delegation_immediately_granted_dispatches_a_job(tmp_path, monkeypatch):
    """End-to-end through the real API/dispatcher, real configs/policies.yaml (not the
    fake policy used by the unit tests above): create a profile, propose a delegation
    whose only requested grant is allowed without approval, and confirm a real Job gets
    created, dispatched and reaches a terminal status."""
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {app.state.session_token}"

        profile = client.post(
            "/roster/profiles",
            json={
                "id": "swift-agent",
                "display_name": "Swift",
                "role": "fast-orchestrator",
                "authority_ceiling": ["read:workspace"],
            },
        )
        assert profile.status_code == 201

        response = client.post(
            "/roster/delegations",
            json={
                "parent_subject_id": "swift-agent",
                "objective": "read the repo",
                "requested_grants": [
                    {
                        "action": "read", "scope": "workspace",
                        "mutates_state": False, "uses_credentials": False,
                    }
                ],
                "job_kind": "chat",
                "inputs": {
                    "request": {"capability": "reasoning", "mode": "fast"},
                    "messages": [{"role": "user", "content": "hi"}],
                },
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["delegation"]["status"] == "approved"
        assert body["job"] is not None
        job_id = body["job"]["id"]

        grants = client.get("/roster/grants", params={"subject_id": "swift-agent"}).json()
        assert any(g["action"] == "read" and g["scope"] == "workspace" for g in grants["grants"])

        job = None
        for _ in range(40):
            job = client.get(f"/jobs/{job_id}").json()
            if job["status"] != "queued":
                break
            time.sleep(0.05)
        assert job["status"] in ("running", "succeeded", "failed")


def test_roster_http_delegation_requiring_approval_then_resolved(tmp_path, monkeypatch):
    """Same end-to-end path, but for a requested grant real policy makes conditional on
    approval (execute, untrusted-collaboration trust, mutates_state defaulted True) --
    proves the whole ApprovalRequest round trip over HTTP, not just RosterService
    in-process."""
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {app.state.session_token}"

        client.post(
            "/roster/profiles",
            json={
                "id": "forge-agent", "display_name": "Forge", "role": "coder",
                "authority_ceiling": ["execute:workspace"],
            },
        )

        response = client.post(
            "/roster/delegations",
            json={
                "parent_subject_id": "forge-agent",
                "objective": "run the test suite",
                "requested_grants": [{"action": "execute", "scope": "workspace"}],
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["delegation"]["status"] == "awaiting_approval"
        assert body["job"] is None
        delegation_id = body["delegation"]["id"]

        pending = client.get("/roster/approvals").json()["approvals"]
        approval = next(a for a in pending if a["evidence"]["delegation_id"] == delegation_id)

        resolved = client.post(
            f"/roster/approvals/{approval['id']}/resolve",
            json={"resolver_id": "owner", "approved": True, "reason": "reviewed, looks safe"},
        )
        assert resolved.status_code == 200
        resolved_body = resolved.json()
        assert resolved_body["approval"]["status"] == "approved"
        assert resolved_body["job"] is not None

        delegation = client.get(f"/roster/delegations/{delegation_id}").json()
        assert delegation["status"] == "approved"
        assert delegation["child_job_id"] == resolved_body["job"]["id"]


def test_workspace_lease_http_layers_on_the_existing_registry(tmp_path, monkeypatch):
    """FIXES.md Tier 5: a lease must not be acquirable on a root the existing
    WorkspaceRegistry never approved -- the registry stays the permanent allow-list, the
    lease only adds a narrower, run-scoped, time-bounded question on top of it."""
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    approved = tmp_path / "approved-workspace"
    approved.mkdir()
    unapproved = tmp_path / "unapproved-workspace"
    unapproved.mkdir()

    app = create_app(str(ROOT / "configs"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {app.state.session_token}"
        app.state.kernel.workspaces.add(str(approved), writable=True)

        denied = client.post(
            "/workspaces/leases",
            json={"path": str(unapproved), "subject_id": "run-1"},
        )
        assert denied.status_code == 403

        granted = client.post(
            "/workspaces/leases", json={"path": str(approved), "subject_id": "run-1"}
        )
        assert granted.status_code == 201
        lease_id = granted.json()["id"]

        conflict = client.post(
            "/workspaces/leases", json={"path": str(approved), "subject_id": "run-2"}
        )
        assert conflict.status_code == 409

        release = client.delete(f"/workspaces/leases/{lease_id}")
        assert release.status_code == 200

        reacquired = client.post(
            "/workspaces/leases", json={"path": str(approved), "subject_id": "run-2"}
        )
        assert reacquired.status_code == 201


# --- Tier 5 continued: mailbox/presence read-models ------------------------------------


def test_collaboration_mailbox_splits_inbox_and_outbox(tmp_path, monkeypatch):
    """FIXES.md Tier 5: mailbox is a derived read-model over the existing event chain,
    not a new mutable queue. Uses the real bootstrap room/identities (build-lab, owner,
    swift, forge) already exercised by test_native_collaboration_rooms_mentions_and_chain."""
    k = kernel(tmp_path, monkeypatch)
    message, _ = k.collaboration.post_message(
        "build-lab", "owner", "@swift please take the next step"
    )

    swift_mailbox = k.collaboration.mailbox("swift")
    assert [e.event_id for e in swift_mailbox["inbox"]] == [message.event_id]
    assert swift_mailbox["outbox"] == []

    owner_mailbox = k.collaboration.mailbox("owner")
    assert [e.event_id for e in owner_mailbox["outbox"]][:1] == [message.event_id]
    assert message.event_id not in [e.event_id for e in owner_mailbox["inbox"]]

    # forge was not mentioned in this message, so it must not appear in forge's inbox.
    forge_mailbox = k.collaboration.mailbox("forge")
    assert message.event_id not in [e.event_id for e in forge_mailbox["inbox"]]


def test_collaboration_mailbox_unknown_identity_raises(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Unknown identity"):
        k.collaboration.mailbox("does-not-exist")


def test_collaboration_mailbox_excludes_rooms_not_a_member_of(tmp_path, monkeypatch):
    """A mention only reaches an identity's mailbox if it currently belongs to that room --
    matching the same membership boundary `_dispatches` already enforces for actual paging."""
    k = kernel(tmp_path, monkeypatch)
    k.collaboration.create_room("private-room", "Private Room", "just the owner")
    message, _ = k.collaboration.post_message(
        "private-room", "owner", "@swift this mention is in a room swift never joined"
    )
    swift_mailbox = k.collaboration.mailbox("swift")
    assert message.event_id not in [e.event_id for e in swift_mailbox["inbox"]]


def test_presence_service_idle_with_no_active_grants_leases_or_jobs(tmp_path):
    from sovereign_ai.kernel.capability_grants import CapabilityGrantStore
    from sovereign_ai.kernel.delegations import DelegationStore
    from sovereign_ai.kernel.jobs import JobStore
    from sovereign_ai.kernel.presence import PresenceService
    from sovereign_ai.resources.workspace_leases import WorkspaceLeaseStore

    presence = PresenceService(
        CapabilityGrantStore(tmp_path / "grants.db"),
        WorkspaceLeaseStore(tmp_path / "leases.db"),
        DelegationStore(tmp_path / "delegations.db"),
        JobStore(tmp_path / "jobs.db"),
    )
    record = presence.compute("swift")
    assert record.state == "idle"
    assert record.active_grants == 0
    assert record.active_workspace_leases == 0
    assert record.running_job_ids == []


def test_presence_service_active_with_a_capability_grant(tmp_path):
    from sovereign_ai.kernel.capability_grants import CapabilityGrantStore
    from sovereign_ai.kernel.delegations import DelegationStore
    from sovereign_ai.kernel.jobs import JobStore
    from sovereign_ai.kernel.presence import PresenceService
    from sovereign_ai.resources.workspace_leases import WorkspaceLeaseStore

    grants = CapabilityGrantStore(tmp_path / "grants.db")
    grants.issue("swift", "read", "workspace", "policy", ttl_seconds=3600)
    presence = PresenceService(
        grants,
        WorkspaceLeaseStore(tmp_path / "leases.db"),
        DelegationStore(tmp_path / "delegations.db"),
        JobStore(tmp_path / "jobs.db"),
    )
    record = presence.compute("swift")
    assert record.state == "active"
    assert record.active_grants == 1


def test_presence_service_active_with_a_running_delegated_job(tmp_path):
    from sovereign_ai.kernel.capability_grants import CapabilityGrantStore
    from sovereign_ai.kernel.delegations import DelegationStore
    from sovereign_ai.kernel.jobs import JobStore
    from sovereign_ai.kernel.presence import PresenceService
    from sovereign_ai.resources.workspace_leases import WorkspaceLeaseStore

    delegations = DelegationStore(tmp_path / "delegations.db")
    jobs = JobStore(tmp_path / "jobs.db")
    delegation = delegations.create("swift", "do work", requested_grants=[])
    job = jobs.create("agent", {"delegation_id": delegation.id})
    jobs.mark_running(job.id)
    delegations.set_status(delegation.id, "approved", child_job_id=job.id)

    presence = PresenceService(
        CapabilityGrantStore(tmp_path / "grants.db"),
        WorkspaceLeaseStore(tmp_path / "leases.db"),
        delegations,
        jobs,
    )
    record = presence.compute("swift")
    assert record.state == "active"
    assert record.running_job_ids == [job.id]


def test_roster_http_mailbox_and_presence(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {app.state.session_token}"

        idle = client.get("/roster/presence/swift").json()
        assert idle["state"] == "idle"

        client.post(
            "/collaboration/rooms/build-lab/messages",
            json={"actor_id": "owner", "content": "@swift check the presence endpoint"},
        )
        mailbox = client.get("/collaboration/identities/swift/mailbox").json()
        assert len(mailbox["inbox"]) == 1
        assert "check the presence endpoint" in mailbox["inbox"][0]["payload"]["content"]

        missing = client.get("/collaboration/identities/does-not-exist/mailbox")
        assert missing.status_code == 404


# --- Tier 5 continued: enforceable memory scope filtering -------------------------------


def test_memory_store_search_lexical_scope_filtering(tmp_path):
    """FIXES.md Tier 5: allowed_projects=None preserves existing unrestricted behavior;
    an empty list means unscoped-only (fail-closed for a profile with zero granted
    scopes); a non-empty list means unscoped plus those specific projects."""
    from sovereign_ai.memory.store import MemoryStore

    store = MemoryStore(tmp_path / "mem.db")
    store.put("fact", "shared knowledge everyone can see", project=None)
    store.put("fact", "alpha project secret plan", project="alpha")
    store.put("fact", "beta project secret plan", project="beta")

    unrestricted = store.search_lexical("secret OR shared OR knowledge OR plan")
    assert len(unrestricted) == 3

    unscoped_only = store.search_lexical("secret OR shared OR knowledge OR plan", allowed_projects=[])
    assert [r["project"] for r in unscoped_only] == [None]

    alpha_scoped = store.search_lexical(
        "secret OR shared OR knowledge OR plan", allowed_projects=["alpha"]
    )
    projects = {r["project"] for r in alpha_scoped}
    assert projects == {None, "alpha"}
    assert "beta" not in projects


def test_local_vector_store_search_vector_scope_filtering(tmp_path):
    from sovereign_ai.memory.vector import LocalVectorStore

    store = LocalVectorStore(tmp_path / "vec.db")
    store.put("shared", [1.0, 0.0], "shared", project=None)
    store.put("alpha", [1.0, 0.0], "alpha-scoped", project="alpha")
    store.put("beta", [1.0, 0.0], "beta-scoped", project="beta")

    assert {h["id"] for h in store.search_vector([1.0, 0.0], limit=10)} == {"shared", "alpha", "beta"}
    assert {h["id"] for h in store.search_vector([1.0, 0.0], limit=10, allowed_projects=[])} == {"shared"}
    assert {h["id"] for h in store.search_vector([1.0, 0.0], limit=10, allowed_projects=["alpha"])} == {
        "shared", "alpha",
    }


class _RecordingVectorRetriever:
    """Records the args ContextBuilder.retrieve_text calls it with, proving propagation
    without needing the full specialist-broker machinery."""

    def __init__(self):
        self.calls: list[tuple[str, int, list[str] | None]] = []

    async def search(self, query, limit=20, allowed_projects=None):
        self.calls.append((query, limit, allowed_projects))
        return []


def test_context_builder_propagates_scope_to_both_lexical_and_vector_search(tmp_path):
    from sovereign_ai.memory.context import ContextBuilder
    from sovereign_ai.memory.store import MemoryStore

    memory = MemoryStore(tmp_path / "mem.db")
    memory.put("fact", "alpha project detail", project="alpha")
    memory.put("fact", "beta project detail", project="beta")
    fake_vector = _RecordingVectorRetriever()
    builder = ContextBuilder(memory, text_vector=fake_vector)

    items = asyncio.run(builder.retrieve_text("project detail", allowed_projects=["alpha"]))
    assert [item.content for item in items] == ["alpha project detail"]
    assert fake_vector.calls == [("project detail", 24, ["alpha"])]
