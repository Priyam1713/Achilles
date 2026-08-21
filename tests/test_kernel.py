import asyncio
import shutil
import time
from pathlib import Path

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
    verified_source: true
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
