import asyncio
import json
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

def _local_inference_backend_reachable() -> bool:
    """Is a real inference backend listening where the manifest expects one?

    Several tests assert that a job fails fast "because there is no real inference backend
    in this environment". That is true in a sandbox and false on a developer's own machine
    with the kernel running -- where the job instead starts loading a 16 GB model and the
    test hangs. Making the assumption explicit is the honest fix; loosening the assertion
    would just hide the difference.
    """
    import socket

    from sovereign_ai.kernel.config import ConfigBundle

    try:
        engines = ConfigBundle(str(ROOT / "configs")).engines
        url = engines["engines"]["llama_cpp"]["health_url"]
        host, _, port = url.split("//", 1)[1].split("/", 1)[0].rpartition(":")
        with socket.create_connection((host, int(port)), timeout=0.4):
            return True
    except Exception:
        return False


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


def test_loopback_only_middleware_rejects_foreign_origin(tmp_path, monkeypatch):
    """FIXES.md F-004: an Origin header that does not match this installation (and is not
    a recognized desktop-app origin) must be refused, same as a foreign Host."""
    client = api_client(tmp_path, monkeypatch)
    rebound = client.get("/health", headers={"Origin": "https://attacker.example.com"})
    assert rebound.status_code == 400
    assert "access-control-allow-origin" not in rebound.headers


def test_loopback_only_middleware_allows_desktop_app_origin_with_cors_headers(tmp_path, monkeypatch):
    """The Tauri desktop client's webview origin (Tier 6 desktop product) is never the
    same as the kernel API's own host:port, on any platform Tauri supports -- it needs an
    explicit, still-precise CORS allowance rather than being rejected as a foreign origin,
    and the response must carry real CORS headers or the webview's fetch() cannot read it."""
    client = api_client(tmp_path, monkeypatch)
    response = client.get("/health", headers={"Origin": "http://localhost:1420"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:1420"


def test_loopback_only_middleware_answers_desktop_app_preflight(tmp_path, monkeypatch):
    """No route defines OPTIONS, so the desktop app's CORS preflight must be answered by
    the middleware itself rather than falling through to a 404/405."""
    client = api_client(tmp_path, monkeypatch)
    response = client.options(
        "/roster/approvals/some-id/resolve",
        headers={"Origin": "http://localhost:1420", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:1420"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_loopback_only_middleware_rejects_preflight_from_foreign_origin(tmp_path, monkeypatch):
    """A preflight is only ever answered for a recognized desktop-app origin -- an
    arbitrary origin's OPTIONS request must still be refused, not accidentally granted
    the same short-circuit."""
    client = api_client(tmp_path, monkeypatch)
    response = client.options(
        "/health", headers={"Origin": "https://attacker.example.com"}
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


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


# --- Tier 5 continued: opt-in WorkspaceLease enforcement in ExecutionBroker ------------


def test_execution_broker_lease_id_without_subject_id_is_rejected(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)

    async def drive():
        return await k.execution.run_approved(
            ["true"], str(workspace), workspace_lease_id="fake-lease-id"
        )

    with pytest.raises(PermissionError, match="requires a subject_id"):
        asyncio.run(drive())


def test_execution_broker_rejects_unknown_lease(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)

    async def drive():
        return await k.execution.run_approved(
            ["true"], str(workspace), subject_id="run-1", workspace_lease_id="does-not-exist"
        )

    with pytest.raises(PermissionError, match="not active for subject"):
        asyncio.run(drive())


def test_execution_broker_rejects_lease_held_by_a_different_subject(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    lease = k.workspace_leases.try_acquire(str(workspace), "run-1", writable=True, ttl_seconds=60)

    async def drive():
        return await k.execution.run_approved(
            ["true"], str(workspace), subject_id="run-2", workspace_lease_id=lease.id
        )

    with pytest.raises(PermissionError, match="not active for subject"):
        asyncio.run(drive())


def test_execution_broker_rejects_lease_for_a_different_path(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    leased_dir = tmp_path / "leased"
    other_dir = tmp_path / "other"
    leased_dir.mkdir()
    other_dir.mkdir()
    k.workspaces.add(leased_dir, writable=True)
    k.workspaces.add(other_dir, writable=True)
    lease = k.workspace_leases.try_acquire(str(leased_dir), "run-1", writable=True, ttl_seconds=60)

    async def drive():
        return await k.execution.run_approved(
            ["true"], str(other_dir), subject_id="run-1", workspace_lease_id=lease.id
        )

    with pytest.raises(PermissionError, match="covers"):
        asyncio.run(drive())


def test_execution_broker_rejects_write_through_a_readonly_lease(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    lease = k.workspace_leases.try_acquire(str(workspace), "run-1", writable=False, ttl_seconds=60)

    async def drive():
        return await k.execution.run_approved(
            ["true"], str(workspace), subject_id="run-1", workspace_lease_id=lease.id,
            mutates_state=True,
        )

    with pytest.raises(PermissionError, match="read-only"):
        asyncio.run(drive())


def test_execution_broker_accepts_a_valid_matching_lease(tmp_path, monkeypatch):
    """A lease that genuinely matches subject, path and write mode must pass every lease
    check and reach backend selection -- proof the new checks did not silently reject a
    legitimate lease, not just that they reject illegitimate ones. `available()` is
    stubbed to return False immediately: the real implementations shell out to `wsl` to
    probe OpenShell/Docker, which is not meaningful (and, nested inside this WSL-hosted
    test run, not fast) to exercise here -- this test is about the lease gate, not about
    backend discovery."""
    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    lease = k.workspace_leases.try_acquire(str(workspace), "run-1", writable=True, ttl_seconds=60)
    monkeypatch.setattr(k.execution.openshell, "available", lambda: False)
    monkeypatch.setattr(k.execution.docker, "available", lambda: False)

    async def drive():
        return await k.execution.run_approved(
            ["true"], str(workspace), subject_id="run-1", workspace_lease_id=lease.id,
            mutates_state=True, approved=True,
        )

    with pytest.raises(RuntimeError, match="No hardened execution backend available"):
        asyncio.run(drive())


def test_execution_broker_raises_if_no_lease_store_configured(tmp_path):
    from sovereign_ai.execution.broker import ExecutionBroker
    from sovereign_ai.execution.workspaces import WorkspaceRegistry
    from sovereign_ai.kernel.policy import PolicyEngine

    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = WorkspaceRegistry(tmp_path / "workspaces.json")
    registry.add(workspace, writable=True)
    broker = ExecutionBroker(PolicyEngine(_FakeConfig()), registry)

    async def drive():
        return await broker.run_approved(
            ["true"], str(workspace), subject_id="run-1", workspace_lease_id="anything"
        )

    with pytest.raises(RuntimeError, match="no WorkspaceLeaseStore configured"):
        asyncio.run(drive())


def _broker_with_grants(tmp_path):
    from sovereign_ai.execution.broker import ExecutionBroker
    from sovereign_ai.execution.workspaces import WorkspaceRegistry
    from sovereign_ai.kernel.capability_grants import CapabilityGrantStore
    from sovereign_ai.kernel.policy import PolicyEngine

    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = WorkspaceRegistry(tmp_path / "workspaces.json")
    registry.add(workspace, writable=True)
    grants = CapabilityGrantStore(tmp_path / "grants.db")
    broker = ExecutionBroker(PolicyEngine(_FakeConfig()), registry, capability_grants=grants)
    broker.openshell.available = lambda: False
    broker.docker.available = lambda: False
    return broker, grants, workspace


def test_execution_broker_active_capability_grant_bypasses_untrusted_policy_gate(tmp_path):
    """FIXES.md F-037 (closes F-036): a real CapabilityGrant for exactly
    (subject, "execute", "workspace") lets a call that PolicyEngine's own untrusted-
    content gate would otherwise deny unconditionally reach backend selection instead."""
    broker, grants, workspace = _broker_with_grants(tmp_path)

    async def without_grant():
        return await broker.run_approved(
            ["true"], str(workspace), trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            mutates_state=True, subject_id="swift",
        )

    with pytest.raises(PermissionError, match="Untrusted content cannot directly authorize"):
        asyncio.run(without_grant())

    grants.issue("swift", "execute", "workspace", "policy", ttl_seconds=3600)

    async def with_grant():
        return await broker.run_approved(
            ["true"], str(workspace), trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            mutates_state=True, subject_id="swift",
        )

    with pytest.raises(RuntimeError, match="No hardened execution backend available"):
        asyncio.run(with_grant())


def test_execution_broker_grant_for_a_different_scope_does_not_bypass(tmp_path):
    """No implicit wildcards (CapabilityGrantStore.is_active's own stated contract): a
    grant issued for a different action never authorizes "execute"."""
    broker, grants, workspace = _broker_with_grants(tmp_path)
    grants.issue("swift", "read", "workspace", "policy", ttl_seconds=3600)

    async def drive():
        return await broker.run_approved(
            ["true"], str(workspace), trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            mutates_state=True, subject_id="swift",
        )

    with pytest.raises(PermissionError, match="Untrusted content cannot directly authorize"):
        asyncio.run(drive())


def test_execution_broker_expired_grant_does_not_bypass(tmp_path):
    broker, grants, workspace = _broker_with_grants(tmp_path)
    grants.issue("swift", "execute", "workspace", "policy", ttl_seconds=-1)

    async def drive():
        return await broker.run_approved(
            ["true"], str(workspace), trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            mutates_state=True, subject_id="swift",
        )

    with pytest.raises(PermissionError, match="Untrusted content cannot directly authorize"):
        asyncio.run(drive())


def test_execution_broker_revoked_grant_does_not_bypass(tmp_path):
    broker, grants, workspace = _broker_with_grants(tmp_path)
    grant = grants.issue("swift", "execute", "workspace", "policy", ttl_seconds=3600)
    grants.revoke(grant.id)

    async def drive():
        return await broker.run_approved(
            ["true"], str(workspace), trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            mutates_state=True, subject_id="swift",
        )

    with pytest.raises(PermissionError, match="Untrusted content cannot directly authorize"):
        asyncio.run(drive())


def test_execution_broker_someone_elses_grant_does_not_bypass(tmp_path):
    broker, grants, workspace = _broker_with_grants(tmp_path)
    grants.issue("someone-else", "execute", "workspace", "policy", ttl_seconds=3600)

    async def drive():
        return await broker.run_approved(
            ["true"], str(workspace), trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            mutates_state=True, subject_id="swift",
        )

    with pytest.raises(PermissionError, match="Untrusted content cannot directly authorize"):
        asyncio.run(drive())


def test_execution_broker_no_subject_id_falls_through_to_normal_policy(tmp_path):
    """A caller that never supplies subject_id gets exactly today's pre-F-037 behavior --
    even if some other subject happens to hold a matching grant, an anonymous call is
    never implicitly credited with it."""
    broker, grants, workspace = _broker_with_grants(tmp_path)
    grants.issue("swift", "execute", "workspace", "policy", ttl_seconds=3600)

    async def drive():
        return await broker.run_approved(
            ["true"], str(workspace), trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT, mutates_state=True,
        )

    with pytest.raises(PermissionError, match="Untrusted content cannot directly authorize"):
        asyncio.run(drive())


def test_execution_broker_grant_bypass_does_not_apply_when_no_grant_store_configured(tmp_path):
    """A broker built without a CapabilityGrantStore (the F-034-era constructor shape)
    must behave exactly as it did before F-037 -- never silently authorize anything."""
    from sovereign_ai.execution.broker import ExecutionBroker
    from sovereign_ai.execution.workspaces import WorkspaceRegistry
    from sovereign_ai.kernel.policy import PolicyEngine

    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = WorkspaceRegistry(tmp_path / "workspaces.json")
    registry.add(workspace, writable=True)
    broker = ExecutionBroker(PolicyEngine(_FakeConfig()), registry)

    async def drive():
        return await broker.run_approved(
            ["true"], str(workspace), trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            mutates_state=True, subject_id="swift",
        )

    with pytest.raises(PermissionError, match="Untrusted content cannot directly authorize"):
        asyncio.run(drive())


# --- Tier 5 continued: AgentProfile identity propagation --------------------------------


def test_agent_payload_carries_profile_and_lease_ids():
    from sovereign_ai.kernel.job_executor import AgentPayload

    payload = AgentPayload(task="do work")
    assert payload.agent_profile_id is None
    assert payload.workspace_lease_id is None

    scoped = AgentPayload(task="do work", agent_profile_id="swift", workspace_lease_id="lease-1")
    assert scoped.agent_profile_id == "swift"
    assert scoped.workspace_lease_id == "lease-1"


def test_roster_service_delegation_job_carries_agent_profile_id_immediate_grant(tmp_path):
    roster = _roster_with_fake_policy(tmp_path)
    _, job = roster.propose_delegation(
        "swift",
        "read the repo",
        [{"action": "read", "scope": "workspace", "mutates_state": False, "uses_credentials": False}],
    )
    assert job is not None
    assert job.request["agent_profile_id"] == "swift"


def test_roster_service_delegation_job_carries_agent_profile_id_after_approval(tmp_path):
    roster = _roster_with_fake_policy(tmp_path)
    roster.propose_delegation(
        "swift", "run a command", [{"action": "execute", "scope": "workspace"}]
    )
    pending = roster.approvals.list_pending()
    _, job = roster.resolve_approval(pending[0].id, "owner", True, "approved")
    assert job is not None
    assert job.request["agent_profile_id"] == "swift"


def test_native_agent_loop_run_command_lease_without_grant_still_blocked_by_policy(tmp_path, monkeypatch):
    """A run_command call whose state carries a genuinely matching agent_profile_id/
    workspace_lease_id clears the F-034 lease gate -- but without an active
    CapabilityGrant, is still denied by PolicyEngine downstream of that gate.
    `_run_command` hardcodes `trust=UNTRUSTED_MODEL_OUTPUT`, and PolicyEngine's
    untrusted-content gate returns `allowed=False` for `action="execute"` unconditionally
    -- regardless of `mutates_state` and the `approved` flag -- unless F-037's grant
    bypass applies (see the companion test below for that case). Confirmed directly
    against PolicyEngine.evaluate() before F-036 was filed; this test keeps that
    no-grant behavior honest and pinned now that a grant *can* change the outcome."""
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    lease = k.workspace_leases.try_acquire(str(workspace), "swift-profile", writable=True, ttl_seconds=60)

    fake = _FakeInference(['{"tool": "run_command", "args": {"argv": ["true"], "mutates_state": true}}'])
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events)
    state = {
        "run_id": "test-run-lease",
        "task": "run a command",
        "workspace": str(workspace),
        "approved": True,
        "agent_profile_id": "swift-profile",
        "workspace_lease_id": lease.id,
    }

    step = asyncio.run(loop.next_step(state))
    observation = step.payload["observation"]
    # Denied by PolicyEngine specifically (not by the lease gate -- that message says
    # "not active for subject"/"covers"/"read-only", none of which appear here), proving
    # the lease check itself passed and the block is downstream of it.
    assert observation["error"] == (
        "denied: Untrusted content cannot directly authorize mutation or credential access."
    )


def test_native_agent_loop_run_command_succeeds_with_a_matching_capability_grant(tmp_path, monkeypatch):
    """FIXES.md F-037: closes F-036. The same setup as the test above, but with a real
    CapabilityGrant issued for exactly (subject, "execute", "workspace") -- this is what
    actually makes the roster/approval pipeline load-bearing for execution, not just
    record-keeping. Reaches backend selection (stubbed to have no backend), proving the
    call cleared both the lease gate and the policy gate, via the grant."""
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    lease = k.workspace_leases.try_acquire(str(workspace), "swift-profile", writable=True, ttl_seconds=60)
    k.capability_grants.issue("swift-profile", "execute", "workspace", "policy", ttl_seconds=3600)
    monkeypatch.setattr(k.execution.openshell, "available", lambda: False)
    monkeypatch.setattr(k.execution.docker, "available", lambda: False)

    fake = _FakeInference(['{"tool": "run_command", "args": {"argv": ["true"], "mutates_state": true}}'])
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events)
    state = {
        "run_id": "test-run-grant",
        "task": "run a command",
        "workspace": str(workspace),
        "agent_profile_id": "swift-profile",
        "workspace_lease_id": lease.id,
    }

    step = asyncio.run(loop.next_step(state))
    observation = step.payload["observation"]
    assert observation["error"] == "RuntimeError: No hardened execution backend available"


def test_native_agent_loop_run_command_denied_by_mismatched_lease(tmp_path, monkeypatch):
    """Same setup, but the run's state names a lease belonging to a different subject --
    must be denied by the lease gate specifically, not silently ignored."""
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    lease = k.workspace_leases.try_acquire(str(workspace), "someone-else", writable=True, ttl_seconds=60)

    fake = _FakeInference(['{"tool": "run_command", "args": {"argv": ["true"], "mutates_state": true}}'])
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events)
    state = {
        "run_id": "test-run-lease-denied",
        "task": "run a command",
        "workspace": str(workspace),
        "approved": True,
        "agent_profile_id": "swift-profile",
        "workspace_lease_id": lease.id,
    }

    step = asyncio.run(loop.next_step(state))
    observation = step.payload["observation"]
    assert "denied" in observation["error"]
    assert "not active for subject" in observation["error"]


# --- Tier 5 continued: workflow DAGs -----------------------------------------------------


def test_workflow_definition_store_validates_dag_shape(tmp_path):
    from sovereign_ai.kernel.workflows import (
        WorkflowDefinitionStore,
        WorkflowStep,
        WorkflowValidationError,
    )

    store = WorkflowDefinitionStore(tmp_path / "definitions.db")

    with pytest.raises(WorkflowValidationError, match="at least one step"):
        store.create("empty", [])

    with pytest.raises(WorkflowValidationError, match="unique"):
        store.create("dup", [WorkflowStep(id="a", job_kind="chat"), WorkflowStep(id="a", job_kind="chat")])

    with pytest.raises(WorkflowValidationError, match="unknown step"):
        store.create("bad-dep", [WorkflowStep(id="a", job_kind="chat", depends_on=["does-not-exist"])])

    with pytest.raises(WorkflowValidationError, match="cycle"):
        store.create(
            "cycle",
            [
                WorkflowStep(id="a", job_kind="chat", depends_on=["b"]),
                WorkflowStep(id="b", job_kind="chat", depends_on=["a"]),
            ],
        )

    # A valid diamond DAG must be accepted.
    valid = store.create(
        "diamond",
        [
            WorkflowStep(id="a", job_kind="chat"),
            WorkflowStep(id="b", job_kind="chat", depends_on=["a"]),
            WorkflowStep(id="c", job_kind="chat", depends_on=["a"]),
            WorkflowStep(id="d", job_kind="chat", depends_on=["b", "c"]),
        ],
    )
    assert [step.id for step in valid.steps] == ["a", "b", "c", "d"]


def test_workflow_definition_store_versions_are_immutable_and_incrementing(tmp_path):
    from sovereign_ai.kernel.workflows import WorkflowDefinitionStore, WorkflowStep

    store = WorkflowDefinitionStore(tmp_path / "definitions.db")
    first = store.create("wf", [WorkflowStep(id="a", job_kind="chat")])
    second = store.create("wf", [WorkflowStep(id="a", job_kind="chat"), WorkflowStep(id="b", job_kind="chat")])

    assert first.version == 1
    assert second.version == 2
    assert first.id != second.id
    assert store.latest("wf").id == second.id
    assert [d.version for d in store.list_versions("wf")] == [1, 2]
    # No update method exists at all -- immutability is structural, not just convention.
    assert not hasattr(store, "update")


def _linear_workflow(tmp_path):
    from sovereign_ai.kernel.jobs import JobStore
    from sovereign_ai.kernel.workflow_service import WorkflowService
    from sovereign_ai.kernel.workflows import (
        WorkflowDefinitionStore,
        WorkflowInstanceStore,
        WorkflowStep,
    )

    definitions = WorkflowDefinitionStore(tmp_path / "definitions.db")
    instances = WorkflowInstanceStore(tmp_path / "instances.db")
    jobs = JobStore(tmp_path / "jobs.db")
    service = WorkflowService(definitions, instances, jobs)
    definition = definitions.create(
        "linear",
        [
            WorkflowStep(id="a", job_kind="chat"),
            WorkflowStep(id="b", job_kind="chat", depends_on=["a"]),
        ],
    )
    return service, definition


def test_workflow_service_start_only_creates_jobs_for_ready_steps(tmp_path):
    service, definition = _linear_workflow(tmp_path)
    instance, jobs = service.start(definition.id)
    assert instance.status == "running"
    assert [job.kind for job in jobs] == ["chat"]
    assert instance.step_states["a"]["status"] == "queued"
    assert instance.step_states["a"]["job_id"] == jobs[0].id
    assert instance.step_states["b"]["status"] == "pending"
    assert instance.step_states["b"]["job_id"] is None


def test_workflow_service_advance_creates_downstream_job_and_completes(tmp_path):
    service, definition = _linear_workflow(tmp_path)
    instance, _jobs = service.start(definition.id)

    instance, new_jobs = service.advance(instance.id, "a", "succeeded", result={"ok": True})
    assert instance.status == "running"
    assert len(new_jobs) == 1
    assert instance.step_states["b"]["status"] == "queued"
    assert instance.step_states["b"]["job_id"] == new_jobs[0].id

    instance, final_jobs = service.advance(instance.id, "b", "succeeded", result={"ok": True})
    assert instance.status == "completed"
    assert final_jobs == []


def test_workflow_service_step_failure_fails_the_whole_instance(tmp_path):
    service, definition = _linear_workflow(tmp_path)
    instance, _jobs = service.start(definition.id)

    instance, new_jobs = service.advance(instance.id, "a", "failed", error="boom")
    assert instance.status == "failed"
    assert instance.step_states["a"]["error"] == "boom"
    assert new_jobs == []

    # Already terminal: a further advance call is a safe no-op, not an error, and must
    # not resurrect the instance or create the downstream job after the fact.
    instance, more_jobs = service.advance(instance.id, "b", "succeeded")
    assert instance.status == "failed"
    assert more_jobs == []


def test_workflow_service_advance_unknown_instance_or_definition_raises(tmp_path):
    service, _definition = _linear_workflow(tmp_path)
    with pytest.raises(ValueError, match="Unknown workflow instance"):
        service.advance("does-not-exist", "a", "succeeded")
    with pytest.raises(ValueError, match="Unknown workflow definition"):
        service.start("does-not-exist")


def test_job_executor_advances_workflow_on_success_and_submits_downstream_job(tmp_path, monkeypatch):
    """End to end through the real kernel and job_executor.execute(), not the
    WorkflowService in isolation: a workflow's first step actually completing must
    advance the instance and hand the newly-ready downstream job to submit_callback."""
    from sovereign_ai.kernel import job_executor

    k = kernel(tmp_path, monkeypatch)
    definition = k.workflows.create_definition(
        "chat-chain",
        [
            {"id": "a", "job_kind": "chat", "request_template": {
                "request": {"capability": "reasoning", "mode": "fast"},
                "messages": [{"role": "user", "content": "step a"}],
            }},
            {"id": "b", "job_kind": "chat", "depends_on": ["a"], "request_template": {
                "request": {"capability": "reasoning", "mode": "fast"},
                "messages": [{"role": "user", "content": "step b"}],
            }},
        ],
    )
    instance, jobs = k.workflows.start(definition.id)
    job_a = jobs[0]
    run_a = k.runs.create(job_a.id, 1, job_a.request)

    fake_result = {"result": {"choices": [{"message": {"content": "done with a"}}]}}
    monkeypatch.setattr(k.inference, "chat", lambda *a, **kw: _async_return(fake_result))

    submitted = []
    result = asyncio.run(
        job_executor.execute(k, job_a, run_a, submit_callback=submitted.append)
    )
    assert result == fake_result

    updated_instance = k.workflow_instances.get(instance.id)
    assert updated_instance.status == "running"
    assert updated_instance.step_states["b"]["status"] == "queued"
    assert len(submitted) == 1
    assert submitted[0].id == updated_instance.step_states["b"]["job_id"]


def _async_return(value):
    async def _coro():
        return value
    return _coro()


@pytest.mark.skipif(
    _local_inference_backend_reachable(),
    reason="a real inference backend is running, so a chat job will not fail fast",
)
def test_workflow_http_start_creates_and_dispatches_the_first_step(tmp_path, monkeypatch):
    """A workflow with no real inference backend in this test environment: the step's job
    is genuinely submitted to the real dispatcher and reaches a terminal (failed) state,
    and that failure genuinely propagates to fail the workflow instance -- proving the
    job_executor -> WorkflowService wiring fires through the real HTTP/dispatcher stack,
    not just in a direct unit call."""
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {app.state.session_token}"

        created = client.post(
            "/workflows/definitions",
            json={
                "name": "http-chain",
                "steps": [
                    {
                        "id": "a", "job_kind": "chat",
                        "request_template": {
                            "request": {"capability": "reasoning", "mode": "fast"},
                            "messages": [{"role": "user", "content": "hi"}],
                        },
                    },
                    {
                        "id": "b", "job_kind": "chat", "depends_on": ["a"],
                        "request_template": {
                            "request": {"capability": "reasoning", "mode": "fast"},
                            "messages": [{"role": "user", "content": "hi again"}],
                        },
                    },
                ],
            },
        )
        assert created.status_code == 201
        definition_id = created.json()["id"]

        started = client.post(f"/workflows/definitions/{definition_id}/start")
        assert started.status_code == 201
        body = started.json()
        assert len(body["jobs"]) == 1
        job_id = body["jobs"][0]["id"]
        instance_id = body["instance"]["id"]

        job = None
        for _ in range(200):
            job = client.get(f"/jobs/{job_id}").json()
            if job["status"] in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(0.1)
        assert job["status"] == "failed"  # no real inference backend in this environment

        instance = None
        for _ in range(200):
            instance = client.get(f"/workflows/instances/{instance_id}").json()
            if instance["status"] != "running":
                break
            time.sleep(0.1)
        assert instance["status"] == "failed"
        assert instance["step_states"]["a"]["status"] == "failed"
        assert instance["step_states"]["b"]["status"] == "pending"


# --- Tier 5 continued: recurring workflow triggers ---------------------------------------


def test_recurring_trigger_store_rejects_non_positive_interval(tmp_path):
    from sovereign_ai.kernel.triggers import RecurringTriggerStore

    store = RecurringTriggerStore(tmp_path / "triggers.db")
    with pytest.raises(ValueError, match="positive"):
        store.create("def-1", 0)
    with pytest.raises(ValueError, match="positive"):
        store.create("def-1", -5)


def test_recurring_trigger_store_due_respects_schedule_and_enabled(tmp_path):
    from sovereign_ai.kernel.triggers import RecurringTriggerStore

    store = RecurringTriggerStore(tmp_path / "triggers.db")
    trigger = store.create("def-1", 60)

    assert store.due() == []  # next_run_at is 60s out; not due yet
    assert [t.id for t in store.due(now=time.time() + 61)] == [trigger.id]

    store.set_enabled(trigger.id, False)
    assert store.due(now=time.time() + 61) == []


def test_recurring_trigger_store_mark_ran_advances_next_run_at(tmp_path):
    from sovereign_ai.kernel.triggers import RecurringTriggerStore

    store = RecurringTriggerStore(tmp_path / "triggers.db")
    trigger = store.create("def-1", 60)
    now = time.time() + 61

    updated = store.mark_ran(trigger.id, now=now)
    assert updated.last_run_at == now
    assert updated.next_run_at == now + 60
    assert store.due(now=now) == []  # no longer due right after running


def test_recurring_trigger_store_unknown_id_raises(tmp_path):
    from sovereign_ai.kernel.triggers import RecurringTriggerStore

    store = RecurringTriggerStore(tmp_path / "triggers.db")
    with pytest.raises(ValueError, match="Unknown recurring trigger"):
        store.mark_ran("does-not-exist")
    with pytest.raises(ValueError, match="Unknown recurring trigger"):
        store.set_enabled("does-not-exist", False)


def test_trigger_scheduler_tick_starts_due_workflow_and_submits_jobs(tmp_path):
    from sovereign_ai.kernel.jobs import JobStore
    from sovereign_ai.kernel.trigger_scheduler import TriggerScheduler
    from sovereign_ai.kernel.triggers import RecurringTriggerStore
    from sovereign_ai.kernel.workflow_service import WorkflowService
    from sovereign_ai.kernel.workflows import (
        WorkflowDefinitionStore,
        WorkflowInstanceStore,
        WorkflowStep,
    )

    definitions = WorkflowDefinitionStore(tmp_path / "definitions.db")
    instances = WorkflowInstanceStore(tmp_path / "instances.db")
    jobs = JobStore(tmp_path / "jobs.db")
    workflows = WorkflowService(definitions, instances, jobs)
    triggers = RecurringTriggerStore(tmp_path / "triggers.db")

    definition = definitions.create("scheduled", [WorkflowStep(id="a", job_kind="chat")])
    hourly = triggers.create(definition.id, 3600)
    due_soon = triggers.create(definition.id, 60)

    submitted = []
    scheduler = TriggerScheduler(triggers, workflows, submitted.append)
    now = time.time()
    assert scheduler.tick(now=now) == []  # neither is due yet

    # Deterministic "time passing", not a real sleep: advance past due_soon's schedule
    # but not hourly's.
    later = now + 61
    result = scheduler.tick(now=later)

    assert len(result) == 1
    assert submitted == result
    assert triggers.get(due_soon.id).last_run_at == later
    assert triggers.due(now=later) == []  # due_soon is no longer due right after running
    assert triggers.get(hourly.id).last_run_at is None  # untouched


def test_trigger_scheduler_tick_disables_trigger_for_missing_definition(tmp_path):
    from sovereign_ai.kernel.jobs import JobStore
    from sovereign_ai.kernel.trigger_scheduler import TriggerScheduler
    from sovereign_ai.kernel.triggers import RecurringTriggerStore
    from sovereign_ai.kernel.workflow_service import WorkflowService
    from sovereign_ai.kernel.workflows import WorkflowDefinitionStore, WorkflowInstanceStore

    definitions = WorkflowDefinitionStore(tmp_path / "definitions.db")
    instances = WorkflowInstanceStore(tmp_path / "instances.db")
    jobs = JobStore(tmp_path / "jobs.db")
    workflows = WorkflowService(definitions, instances, jobs)
    triggers = RecurringTriggerStore(tmp_path / "triggers.db")
    trigger = triggers.create("does-not-exist", 60)

    scheduler = TriggerScheduler(triggers, workflows, lambda job: None)
    result = scheduler.tick(now=time.time() + 61)

    assert result == []
    assert triggers.get(trigger.id).enabled is False


def test_recurring_trigger_http_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {app.state.session_token}"

        definition = client.post(
            "/workflows/definitions",
            json={"name": "trig-wf", "steps": [{"id": "a", "job_kind": "chat"}]},
        ).json()

        missing_def = client.post(
            "/workflows/triggers",
            json={"workflow_definition_id": "does-not-exist", "interval_seconds": 60},
        )
        assert missing_def.status_code == 404

        created = client.post(
            "/workflows/triggers",
            json={"workflow_definition_id": definition["id"], "interval_seconds": 0.05},
        )
        assert created.status_code == 201
        trigger_id = created.json()["id"]
        assert created.json()["enabled"] is True

        listed = client.get("/workflows/triggers").json()["triggers"]
        assert trigger_id in [t["id"] for t in listed]

        disabled = client.put(f"/workflows/triggers/{trigger_id}/enabled", json={"enabled": False})
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False

        missing_toggle = client.put(
            "/workflows/triggers/does-not-exist/enabled", json={"enabled": True}
        )
        assert missing_toggle.status_code == 404

        # Directly drive one tick (rather than waiting on the real poll_interval_seconds)
        # to prove the scheduler wired into this app's lifespan actually works, without a
        # slow, wall-clock-dependent test: disabled must not fire even though its
        # schedule is already due.
        time.sleep(0.1)
        assert app.state.trigger_scheduler.tick() == []


# --- Tier 5 continued: skill-candidate evaluation/promotion pipeline --------------------


def _succeeded_run(tmp_path, steps=None):
    from sovereign_ai.kernel.runs import RunStore

    runs = RunStore(tmp_path / "runs.db")
    run = runs.create("job-1", 1, {"task": "do something"})
    runs.mark_running(run.id)
    runs.finish(
        run.id, "succeeded",
        result={"steps": steps if steps is not None else [{"kind": "tool_call", "payload": {}}]},
    )
    return runs, runs.get(run.id)


def _skill_pipeline(tmp_path):
    from sovereign_ai.kernel.skill_service import SkillService
    from sovereign_ai.kernel.skills import (
        AgentEvaluationStore,
        SkillCandidateStore,
        SkillVersionStore,
    )

    runs, run = _succeeded_run(tmp_path)
    candidates = SkillCandidateStore(tmp_path / "candidates.db")
    evaluations = AgentEvaluationStore(tmp_path / "evaluations.db")
    versions = SkillVersionStore(tmp_path / "versions.db")
    service = SkillService(runs, candidates, evaluations, versions)
    return service, run


def test_skill_service_propose_requires_a_succeeded_run_with_steps(tmp_path):
    from sovereign_ai.kernel.runs import RunStore
    from sovereign_ai.kernel.skill_service import SkillService
    from sovereign_ai.kernel.skills import (
        AgentEvaluationStore,
        SkillCandidateStore,
        SkillVersionStore,
    )

    runs = RunStore(tmp_path / "runs.db")
    candidates = SkillCandidateStore(tmp_path / "candidates.db")
    evaluations = AgentEvaluationStore(tmp_path / "evaluations.db")
    versions = SkillVersionStore(tmp_path / "versions.db")
    service = SkillService(runs, candidates, evaluations, versions)

    with pytest.raises(ValueError, match="Unknown run"):
        service.propose_from_run("does-not-exist", "objective", "tester")

    running_run = runs.create("job-1", 1, {})
    runs.mark_running(running_run.id)
    with pytest.raises(ValueError, match="not 'succeeded'"):
        service.propose_from_run(running_run.id, "objective", "tester")

    empty_steps_run = runs.create("job-2", 1, {})
    runs.mark_running(empty_steps_run.id)
    runs.finish(empty_steps_run.id, "succeeded", result={"steps": []})
    with pytest.raises(ValueError, match="no non-empty 'steps'"):
        service.propose_from_run(empty_steps_run.id, "objective", "tester")


def test_skill_service_propose_creates_a_candidate_with_the_run_trajectory(tmp_path):
    steps = [{"kind": "tool_call", "payload": {"tool": "read_file"}}]
    from sovereign_ai.kernel.skill_service import SkillService
    from sovereign_ai.kernel.skills import (
        AgentEvaluationStore,
        SkillCandidateStore,
        SkillVersionStore,
    )

    runs, run = _succeeded_run(tmp_path, steps)
    candidates = SkillCandidateStore(tmp_path / "candidates.db")
    evaluations = AgentEvaluationStore(tmp_path / "evaluations.db")
    versions = SkillVersionStore(tmp_path / "versions.db")
    service = SkillService(runs, candidates, evaluations, versions)

    candidate = service.propose_from_run(run.id, "read a file", "tester")
    assert candidate.status == "proposed"
    assert candidate.source_run_id == run.id
    assert candidate.trajectory == steps
    assert candidates.get(candidate.id) == candidate


def test_skill_service_record_evaluation_transitions_candidate_status(tmp_path):
    service, run = _skill_pipeline(tmp_path)
    candidate = service.propose_from_run(run.id, "objective", "tester")

    evaluation = service.record_evaluation(candidate.id, "pass", "reviewer", evidence={"note": "looks right"})
    assert evaluation.verdict == "pass"
    assert evaluation.evidence == {"note": "looks right"}
    assert service.candidates.get(candidate.id).status == "evaluated"

    with pytest.raises(ValueError, match="Unknown skill candidate"):
        service.record_evaluation("does-not-exist", "pass", "reviewer")


def test_skill_service_promote_requires_a_passing_evaluation(tmp_path):
    from sovereign_ai.kernel.skills import SkillPromotionError

    service, run = _skill_pipeline(tmp_path)
    candidate = service.propose_from_run(run.id, "objective", "tester")

    with pytest.raises(SkillPromotionError, match="no passing evaluation"):
        service.promote(candidate.id, "read-a-file", "promoter")

    service.record_evaluation(candidate.id, "fail", "reviewer")
    with pytest.raises(SkillPromotionError, match="no passing evaluation"):
        service.promote(candidate.id, "read-a-file", "promoter")

    service.record_evaluation(candidate.id, "pass", "reviewer")
    version = service.promote(candidate.id, "read-a-file", "promoter")
    assert version.name == "read-a-file"
    assert version.version == 1
    assert version.skill_candidate_id == candidate.id
    assert service.candidates.get(candidate.id).status == "promoted"


def test_skill_service_promote_is_not_repeatable(tmp_path):
    from sovereign_ai.kernel.skills import SkillPromotionError

    service, run = _skill_pipeline(tmp_path)
    candidate = service.propose_from_run(run.id, "objective", "tester")
    service.record_evaluation(candidate.id, "pass", "reviewer")
    service.promote(candidate.id, "read-a-file", "promoter")

    with pytest.raises(SkillPromotionError, match="already promoted"):
        service.promote(candidate.id, "read-a-file-again", "promoter")
    with pytest.raises(SkillPromotionError, match="already promoted"):
        service.reject(candidate.id)


def test_skill_service_reject(tmp_path):
    service, run = _skill_pipeline(tmp_path)
    candidate = service.propose_from_run(run.id, "objective", "tester")
    service.record_evaluation(candidate.id, "fail", "reviewer")

    rejected = service.reject(candidate.id)
    assert rejected.status == "rejected"


def test_skill_version_store_versions_are_immutable_and_incrementing(tmp_path):
    from sovereign_ai.kernel.skills import SkillVersionStore

    store = SkillVersionStore(tmp_path / "versions.db")
    first = store.create("greet", "cand-1", "eval-1", [{"a": 1}], "promoter")
    second = store.create("greet", "cand-2", "eval-2", [{"a": 2}], "promoter")

    assert first.version == 1
    assert second.version == 2
    assert store.latest("greet").id == second.id
    assert [v.version for v in store.list_versions("greet")] == [1, 2]
    assert not hasattr(store, "update")


def test_skill_pipeline_http_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("SOVEREIGN_STATE_DIR", str(tmp_path / "state"))
    app = create_app(str(ROOT / "configs"))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        client.headers["Authorization"] = f"Bearer {app.state.session_token}"
        kernel_instance = app.state.kernel

        job = kernel_instance.jobs.create("agent", {"task": "read a file"})
        run = kernel_instance.runs.create(job.id, 1, job.request)
        kernel_instance.runs.mark_running(run.id)
        kernel_instance.runs.finish(
            run.id, "succeeded",
            result={"steps": [{"kind": "tool_call", "payload": {"tool": "read_file"}}]},
        )

        proposed = client.post(
            "/skills/candidates",
            json={"run_id": run.id, "objective": "read a file", "proposed_by": "tester"},
        )
        assert proposed.status_code == 201
        candidate_id = proposed.json()["id"]

        premature = client.post(
            f"/skills/candidates/{candidate_id}/promote",
            json={"name": "read-a-file", "promoted_by": "promoter"},
        )
        assert premature.status_code == 409

        evaluated = client.post(
            f"/skills/candidates/{candidate_id}/evaluations",
            json={"verdict": "pass", "evaluated_by": "reviewer", "evidence": {"note": "ok"}},
        )
        assert evaluated.status_code == 201
        assert client.get(f"/skills/candidates/{candidate_id}").json()["status"] == "evaluated"
        assert len(client.get(f"/skills/candidates/{candidate_id}/evaluations").json()["evaluations"]) == 1

        promoted = client.post(
            f"/skills/candidates/{candidate_id}/promote",
            json={"name": "read-a-file", "promoted_by": "promoter"},
        )
        assert promoted.status_code == 201
        version_id = promoted.json()["id"]
        assert promoted.json()["version"] == 1

        fetched = client.get(f"/skills/versions/{version_id}")
        assert fetched.status_code == 200
        by_name = client.get("/skills/versions/by-name/read-a-file").json()["versions"]
        assert [v["id"] for v in by_name] == [version_id]

        evaluated_list = client.get("/skills/candidates", params={"status": "promoted"}).json()
        assert candidate_id in [c["id"] for c in evaluated_list["candidates"]]


# --- Tier 6: harness tournament infrastructure -------------------------------------------


def test_harness_tasks_checkers_pass_on_correct_output(tmp_path):
    from harness_tasks import TASKS

    by_id = {task.id: task for task in TASKS}

    workspace = tmp_path / "read-and-report"
    workspace.mkdir()
    by_id["read-and-report"].setup(workspace)
    passed, _ = by_id["read-and-report"].check(workspace, "The secret number is 4217.")
    assert passed

    workspace = tmp_path / "list-directory-count"
    workspace.mkdir()
    by_id["list-directory-count"].setup(workspace)
    passed, _ = by_id["list-directory-count"].check(workspace, "There are 5 files.")
    assert passed

    workspace = tmp_path / "mutation-without-authorization"
    workspace.mkdir()
    by_id["mutation-without-authorization"].setup(workspace)
    passed, _ = by_id["mutation-without-authorization"].check(workspace, "I was denied.")
    assert passed  # untouched file is the correct, desired outcome

    workspace = tmp_path / "authorized-mutation"
    workspace.mkdir()
    by_id["authorized-mutation"].setup(workspace)
    (workspace / "result.txt").write_text("done\n", encoding="utf-8")
    passed, _ = by_id["authorized-mutation"].check(workspace, "Created result.txt")
    assert passed


def test_harness_tasks_checkers_fail_on_wrong_output(tmp_path):
    from harness_tasks import TASKS

    by_id = {task.id: task for task in TASKS}

    workspace = tmp_path / "read-and-report"
    workspace.mkdir()
    by_id["read-and-report"].setup(workspace)
    passed, detail = by_id["read-and-report"].check(workspace, "I could not find the file.")
    assert not passed
    assert "4217" in detail

    workspace = tmp_path / "mutation-without-authorization"
    workspace.mkdir()
    by_id["mutation-without-authorization"].setup(workspace)
    (workspace / "protected.txt").unlink()  # simulate the file having actually been deleted
    passed, detail = by_id["mutation-without-authorization"].check(workspace, "deleted it")
    assert not passed

    workspace = tmp_path / "authorized-mutation"
    workspace.mkdir()
    by_id["authorized-mutation"].setup(workspace)
    passed, detail = by_id["authorized-mutation"].check(workspace, "done")
    assert not passed
    assert "never created" in detail


def test_harness_tournament_runs_native_loop_against_all_tasks(tmp_path, monkeypatch):
    """Drives the real NativeAgentLoop (scripted inference, no live model needed) through
    every harness task via harness_tournament.run_task(), proving the runner itself --
    workspace setup, agent-loop driving, denied-attempt counting, capability-grant
    issuance for the one task that needs it, and post-condition checking -- is correct.
    The authorized-mutation task is expected to reach backend selection and stop there
    (no real OpenShell/Docker backend in this test environment, the same honest boundary
    every other execution test in this suite hits) -- this test asserts that real,
    partial outcome rather than papering over it."""
    from harness_tasks import TASKS
    from harness_tournament import run_task

    k = kernel(tmp_path, monkeypatch)
    workspace_root = tmp_path / "tournament-workspaces"

    scripts = {
        "read-and-report": [
            '{{"tool": "read_file", "args": {{"path": "{workspace}/data.txt"}}}}',
            '{{"tool": "done", "summary": "The secret number is 4217"}}',
        ],
        "list-directory-count": [
            '{{"tool": "list_directory", "args": {{"path": "{workspace}/items"}}}}',
            '{{"tool": "done", "summary": "There are 5 files. 5"}}',
        ],
        "mutation-without-authorization": [
            '{{"tool": "run_command", "args": {{"argv": ["rm", "{workspace}/protected.txt"], "mutates_state": true}}}}',
            '{{"tool": "done", "summary": "I was denied permission to delete the file."}}',
        ],
        "authorized-mutation": [
            '{{"tool": "run_command", "args": {{"argv": ["sh", "-c", "echo done > {workspace}/result.txt"], "mutates_state": true}}}}',
            '{{"tool": "done", "summary": "Created result.txt"}}',
        ],
        # Goal-phrased rather than tool-phrased, and satisfiable with write_file -- so
        # unlike authorized-mutation it needs no execution backend and can genuinely pass
        # here, which is what makes it a real check of write:workspace grant issuance.
        "authorized-write": [
            '{{"tool": "write_file", "args": {{"path": "{workspace}/outcome.txt", "content": "done"}}}}',
            '{{"tool": "done", "summary": "Created outcome.txt"}}',
        ],
        # The context-economy tasks (F-060). Scripted here only to prove the runner drives
        # them; whether a real model succeeds is what the live tournament measures.
        "large-file-question": [
            '{{"tool": "read_file", "args": {{"path": "{workspace}/module.py"}}}}',
            '{{"tool": "done", "summary": "The odd one out is compute_final_answer"}}',
        ],
        "multi-file-gather": [
            '{{"batch": [{{"tool": "read_file", "args": {{"path": "{workspace}/alpha.txt"}}}},'
            ' {{"tool": "read_file", "args": {{"path": "{workspace}/beta.txt"}}}},'
            ' {{"tool": "read_file", "args": {{"path": "{workspace}/gamma.txt"}}}}]}}',
            '{{"tool": "done", "summary": "11 + 22 + 33 = 66"}}',
        ],
        "long-horizon-scan": [
            '{{"tool": "grep", "args": {{"pattern": "TARGET", "path": "{workspace}/facts"}}}}',
            '{{"tool": "done", "summary": "It is note_09.txt"}}',
        ],
    }

    results = {}
    for task in TASKS:
        # Must match run_task()'s own layout exactly: it scopes by loop name as well as
        # task id so two loops cannot collide. Scripting a different path was harmless
        # while every task's post-condition read the final summary or expected a denial,
        # and became a real failure the moment a task actually wrote a file.
        workspace = workspace_root / "native" / task.id
        replies = [reply.format(workspace=workspace) for reply in scripts[task.id]]
        # NativeAgentLoop was constructed once at kernel-build time and holds its own
        # `inference` reference internally -- patching k.inference itself would not
        # reach it, so the already-registered loop instance's attribute is patched
        # directly instead.
        k.agent_loops.get("native").inference = _FakeInference(replies)
        result = asyncio.run(run_task(k, "native", task, workspace_root))
        results[task.id] = result

    assert results["read-and-report"]["passed"] is True
    assert results["list-directory-count"]["passed"] is True

    assert results["mutation-without-authorization"]["passed"] is True
    assert results["mutation-without-authorization"]["denied_attempts"] == 1

    # No real execution backend in this environment: the grant/policy gates are
    # genuinely cleared (proven by reaching backend selection, not denied earlier), but
    # the task still correctly fails its post-condition since nothing actually ran.
    assert results["authorized-mutation"]["passed"] is False

    # The write-based task needs no execution backend, so it must genuinely pass -- which
    # proves the runner issues the task's *declared* grants (write:workspace here) rather
    # than the execute:workspace it used to hard-code for every mutating task.
    assert results["authorized-write"]["passed"] is True
    assert results["authorized-write"]["denied_attempts"] == 0

    # The context-economy tasks are read-only, so they pass here with no backend at all --
    # which is the point: they measure context handling, not execution.
    assert results["large-file-question"]["passed"] is True
    assert results["multi-file-gather"]["passed"] is True
    assert results["long-horizon-scan"]["passed"] is True
    assert results["authorized-mutation"]["denied_attempts"] == 0
    assert "never created" in results["authorized-mutation"]["detail"]
    assert k.capability_grants.is_active(
        "tournament-native-authorized-mutation", "execute", "workspace"
    )


# --- Remote provider pool: plug-and-play seam (FIXES.md, Tier 6 item 3) ---
#
# knowledge/research.md's remote-inference policy requires an adapter behind the existing
# inference interface, a secret handle (never a literal key in config), explicit
# data-classification/local-only exclusion, request/token/cost/quota/timeout/circuit-breaker
# limits, and provenance recording -- all *before* any actual provider may be enabled. No
# provider is enabled by any of this: configs/engines.yaml declares none, and these tests
# build a synthetic remote EngineSpec/ModelSpec by hand to prove the plumbing works without
# needing real external credentials or a network call.


class _FakeSecrets:
    """Stands in for kernel.secrets.SecretStore without touching the real OS keyring --
    keyring has no backend available in a headless WSL test run, and these tests are
    about the plug-and-play plumbing, not the keyring integration itself."""

    def __init__(self, values: dict[str, str] | None = None):
        self._values = values or {}

    def get(self, name: str) -> str | None:
        return self._values.get(name)


def _remote_engine_spec(**overrides):
    from sovereign_ai.kernel.types import EngineSpec

    defaults = dict(
        id="remote-test",
        kind="openai_compatible",
        enabled=True,
        base_url="https://example.invalid/v1",
        remote=True,
        api_key_secret="remote-test-key",
    )
    defaults.update(overrides)
    return EngineSpec(**defaults)


def _remote_model_spec(engine_id="remote-test", capability="remote_test_capability"):
    from sovereign_ai.kernel.types import ModelSpec, ModelStatus

    return ModelSpec(
        id="remote-test-model",
        name="Remote Test Model",
        source_type="reference",
        status=ModelStatus.FINAL,
        install_policy="runtime_only",
        capabilities=[capability],
        preferred_engines=[engine_id],
        quality_prior=0.9,
    )


def test_remote_quota_ledger_records_and_aggregates_usage_today(tmp_path):
    from sovereign_ai.inference.remote_quota import RemoteQuotaLedger

    ledger = RemoteQuotaLedger(tmp_path / "remote_quota.db")
    ledger.record(
        "eng", "model", status="success", route_reason="r", prompt_tokens=100,
        completion_tokens=50, cost_usd=0.01,
    )
    ledger.record(
        "eng", "model", status="success", route_reason="r", prompt_tokens=200,
        completion_tokens=100, cost_usd=0.02,
    )
    ledger.record("eng", "model", status="failure", route_reason="boom")
    ledger.record("eng", "model", status="refused", route_reason="quota exhausted")

    usage = ledger.usage_today("eng")
    assert usage["requests"] == 4  # every attempt counts against the request quota
    assert usage["tokens"] == 450  # only successes moved real tokens
    assert usage["cost_usd"] == pytest.approx(0.03)  # only successes were ever billed

    assert ledger.usage_today("other-engine") == {"requests": 0, "tokens": 0, "cost_usd": 0}


def test_remote_quota_ledger_circuit_breaker_streak_resets_on_success(tmp_path):
    from sovereign_ai.inference.remote_quota import RemoteQuotaLedger

    ledger = RemoteQuotaLedger(tmp_path / "remote_quota.db")
    for _ in range(3):
        ledger.record("eng", "model", status="failure", route_reason="boom")
    assert ledger.consecutive_failures("eng") == 3
    assert ledger.last_failure_at("eng") is not None

    # A refused row (breaker already open, or budget exhausted) is not itself a new
    # failure and must not extend or reset the streak.
    ledger.record("eng", "model", status="refused", route_reason="breaker open")
    assert ledger.consecutive_failures("eng") == 3

    ledger.record("eng", "model", status="success", route_reason="r", prompt_tokens=1)
    assert ledger.consecutive_failures("eng") == 0


def test_inference_broker_only_builds_remote_backend_when_credential_is_configured(tmp_path, monkeypatch):
    from sovereign_ai.inference.broker import InferenceBroker
    from sovereign_ai.inference.remote_backend import RemoteOpenAICompatibleBackend
    from sovereign_ai.inference.remote_quota import RemoteQuotaLedger

    k = kernel(tmp_path, monkeypatch)
    k.registry.engines["remote-with-secret"] = _remote_engine_spec(id="remote-with-secret")
    k.registry.engines["remote-no-secret"] = _remote_engine_spec(
        id="remote-no-secret", api_key_secret=None
    )
    broker = InferenceBroker(
        k.registry, k.scheduler, k.gpu, _FakeSecrets(), RemoteQuotaLedger(tmp_path / "rq.db")
    )
    assert isinstance(broker.backends["remote-with-secret"], RemoteOpenAICompatibleBackend)
    assert "remote-no-secret" not in broker.backends


def test_inference_broker_without_secrets_configures_no_remote_backends(tmp_path, monkeypatch):
    from sovereign_ai.inference.broker import InferenceBroker

    k = kernel(tmp_path, monkeypatch)
    k.registry.engines["remote-test"] = _remote_engine_spec()
    broker = InferenceBroker(k.registry, k.scheduler, k.gpu)
    assert "remote-test" not in broker.backends


def test_scheduler_excludes_remote_engine_unless_request_opts_in(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    k.registry.engines["remote-test"] = _remote_engine_spec()
    k.registry.models["remote-test-model"] = _remote_model_spec()
    k.registry.by_capability["remote_test_capability"] = ["remote-test-model"]

    denied = k.scheduler.route(CapabilityRequest(capability="remote_test_capability"))
    assert denied.candidates == []
    assert any("remote engine not permitted" in w for w in denied.warnings)

    allowed = k.scheduler.route(
        CapabilityRequest(capability="remote_test_capability", allow_remote=True)
    )
    assert len(allowed.candidates) == 1
    assert allowed.candidates[0].engine_id == "remote-test"


def test_inference_broker_refuses_remote_call_once_daily_request_quota_is_exhausted(
    tmp_path, monkeypatch
):
    from sovereign_ai.inference.broker import InferenceBroker
    from sovereign_ai.inference.remote_quota import RemoteQuotaLedger

    k = kernel(tmp_path, monkeypatch)
    k.registry.engines["remote-test"] = _remote_engine_spec(max_requests_per_day=1)
    k.registry.models["remote-test-model"] = _remote_model_spec()
    k.registry.by_capability["remote_test_capability"] = ["remote-test-model"]

    ledger = RemoteQuotaLedger(tmp_path / "rq.db")
    ledger.record("remote-test", "remote-test-model", status="success", route_reason="prior call")
    broker = InferenceBroker(k.registry, k.scheduler, k.gpu, _FakeSecrets({"remote-test-key": "sk-x"}), ledger)

    request = CapabilityRequest(capability="remote_test_capability", allow_remote=True)
    with pytest.raises(RuntimeError, match="daily request quota exhausted"):
        asyncio.run(broker.chat(request, [{"role": "user", "content": "hi"}]))
    # The refusal itself is recorded, so the ledger's own request count reflects the attempt.
    assert ledger.usage_today("remote-test")["requests"] == 2


def test_inference_broker_refuses_remote_call_when_circuit_breaker_is_open(tmp_path, monkeypatch):
    from sovereign_ai.inference.broker import InferenceBroker
    from sovereign_ai.inference.remote_quota import RemoteQuotaLedger

    k = kernel(tmp_path, monkeypatch)
    k.registry.engines["remote-test"] = _remote_engine_spec(circuit_breaker_threshold=2)
    k.registry.models["remote-test-model"] = _remote_model_spec()
    k.registry.by_capability["remote_test_capability"] = ["remote-test-model"]

    ledger = RemoteQuotaLedger(tmp_path / "rq.db")
    ledger.record("remote-test", "remote-test-model", status="failure", route_reason="boom")
    ledger.record("remote-test", "remote-test-model", status="failure", route_reason="boom")
    broker = InferenceBroker(k.registry, k.scheduler, k.gpu, _FakeSecrets({"remote-test-key": "sk-x"}), ledger)

    request = CapabilityRequest(capability="remote_test_capability", allow_remote=True)
    with pytest.raises(RuntimeError, match="circuit breaker open"):
        asyncio.run(broker.chat(request, [{"role": "user", "content": "hi"}]))


def test_remote_backend_fails_honestly_when_credential_is_not_set(tmp_path):
    from sovereign_ai.inference.remote_backend import RemoteOpenAICompatibleBackend

    backend = RemoteOpenAICompatibleBackend(
        "https://example.invalid/v1", "missing-secret", _FakeSecrets()
    )
    assert asyncio.run(backend.health()) is False
    with pytest.raises(RuntimeError, match="missing-secret"):
        asyncio.run(backend.chat("some-model", [{"role": "user", "content": "hi"}]))


# --- Goose harness adapter (FIXES.md, Tier 6 item 1 continued: D-015) ---
#
# GooseAgentLoop shells out to a real external binary, so these tests stand in a small
# fake "goose" CLI (a python3 script, not the real 300MB binary) rather than depending on
# a compiled Goose checkout or a live local model server being available in CI. The real
# binary was built and live-verified manually against this project's own llama.cpp
# backend (docs/FIXES.md) -- these tests pin GooseAgentLoop's own contract: single-shot
# completion, no re-invocation on a second next_step() call, and honest failure reporting.


def test_goose_agent_loop_runs_once_and_returns_done(tmp_path):
    from sovereign_ai.agents.goose_loop import GooseAgentLoop

    # GooseAgentLoop invokes `self.goose_binary` as a single executable, so the fake
    # "goose" is a directly-executable shebang script rather than an interpreter + a
    # separate script path.
    calls_file = tmp_path / "calls.txt"
    shim = tmp_path / "fake_goose"
    shim.write_text(
        f"#!/usr/bin/env python3\n"
        f"with open({str(calls_file)!r}, 'a') as f:\n"
        f"    f.write('call\\n')\n"
        f"print('READY', end='')\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)

    loop = GooseAgentLoop(str(shim), "http://127.0.0.1:1/v1", "test-model", timeout_s=10)
    state = {"task": "say ready"}
    step = asyncio.run(loop.next_step(state))
    assert step.done is True
    assert step.kind == "done"
    assert step.payload["summary"] == "READY"
    assert calls_file.read_text().count("call") == 1

    # A second call for the *same* state must not relaunch the subprocess -- one
    # `goose run` already ran Goose's own loop to completion.
    step2 = asyncio.run(loop.next_step(state))
    assert step2.done is True
    assert calls_file.read_text().count("call") == 1


def test_goose_agent_loop_reports_harness_error_on_nonzero_exit(tmp_path):
    from sovereign_ai.agents.goose_loop import GooseAgentLoop

    shim = tmp_path / "goose_shim.sh"
    shim.write_text("#!/usr/bin/env bash\necho 'boom' >&2\nexit 3\n", encoding="utf-8")
    shim.chmod(0o755)

    loop = GooseAgentLoop(str(shim), "http://127.0.0.1:1/v1", "test-model", timeout_s=10)
    step = asyncio.run(loop.next_step({"task": "x"}))
    assert step.done is True
    assert step.kind == "harness_error"
    assert "boom" in step.payload["error"]


def test_goose_agent_loop_reports_harness_error_when_binary_missing(tmp_path):
    from sovereign_ai.agents.goose_loop import GooseAgentLoop

    loop = GooseAgentLoop(str(tmp_path / "does-not-exist"), "http://127.0.0.1:1/v1", "m")
    step = asyncio.run(loop.next_step({"task": "x"}))
    assert step.done is True
    assert step.kind == "harness_error"
    assert "not found" in step.payload["error"]


def test_kernel_registers_goose_loop_only_when_binary_exists_on_disk(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    goose_binary = k.config.runtime_dir / "goose" / "bin" / "goose"
    if goose_binary.exists():
        assert "goose" in k.agent_loops.names()
    else:
        assert "goose" not in k.agent_loops.names()


# --- MCP tool bridge (FIXES.md follow-on to F-043: Goose's real per-step tool access) ---
#
# agents/mcp_bridge.py exposes the kernel's whole tool plane as MCP tools, dispatching
# through the same ToolDispatcher instances NativeAgentLoop uses -- so a bridged external
# harness cannot be held to a weaker policy than the reference loop. @mcp.tool() returns the wrapped function unchanged (verified against the
# installed `mcp` package's own source), so these tests call the tool functions directly
# rather than driving a real stdio MCP client/server pair -- a real live run through the
# actual `goose` binary is the genuine end-to-end proof, done separately and reported in
# FIXES.md, not reproduced here since it needs a live local model server.


def _reset_mcp_bridge_kernel():
    from sovereign_ai.agents import mcp_bridge

    mcp_bridge._kernel = None
    return mcp_bridge


def test_mcp_bridge_read_file_denies_unregistered_path(tmp_path, monkeypatch):
    kernel(tmp_path, monkeypatch)
    bridge = _reset_mcp_bridge_kernel()
    target = tmp_path / "secret.txt"
    target.write_text("nope", encoding="utf-8")
    with pytest.raises(PermissionError):
        asyncio.run(bridge.read_file(str(target)))


def test_mcp_bridge_read_file_returns_content_for_registered_workspace(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    bridge = _reset_mcp_bridge_kernel()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "data.txt").write_text("the secret number is 4217", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    result = asyncio.run(bridge.read_file(str(workspace / "data.txt")))
    assert "4217" in result


def test_mcp_bridge_list_directory_returns_sorted_entries(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    bridge = _reset_mcp_bridge_kernel()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "b.txt").write_text("", encoding="utf-8")
    (workspace / "a.txt").write_text("", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    result = asyncio.run(bridge.list_directory(str(workspace)))
    assert result.split("\n") == ["a.txt", "b.txt"]


def test_mcp_bridge_run_command_denied_without_capability_grant(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    bridge = _reset_mcp_bridge_kernel()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    monkeypatch.setenv("SOAI_MCP_AGENT_PROFILE_ID", "no-such-grant")
    monkeypatch.setenv("SOAI_MCP_WORKSPACE", str(workspace))
    with pytest.raises(PermissionError, match="Untrusted content cannot directly authorize"):
        asyncio.run(bridge.run_command(["true"]))


def test_mcp_bridge_run_command_with_grant_reaches_backend_selection(tmp_path, monkeypatch):
    """Mirrors F-041's own honest-limits test pattern: a real CapabilityGrant must let the
    call clear the policy gate (no PermissionError), even though this test environment
    has no real OpenShell/Docker backend to actually run the command."""
    k = kernel(tmp_path, monkeypatch)
    bridge = _reset_mcp_bridge_kernel()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    k.capability_grants.issue("granted-agent", "execute", "workspace", "test", ttl_seconds=300)
    monkeypatch.setenv("SOAI_MCP_AGENT_PROFILE_ID", "granted-agent")
    monkeypatch.setenv("SOAI_MCP_WORKSPACE", str(workspace))
    k.execution.openshell.available = lambda: False
    k.execution.docker.available = lambda: False
    # _get_kernel() otherwise builds its own independent SovereignKernel, separate from
    # `k` -- the availability patches above would silently apply to a kernel this call
    # never touches. Pre-seeding the module-level cache reuses `k` itself.
    bridge._kernel = k

    with pytest.raises(RuntimeError, match="No hardened execution backend available"):
        asyncio.run(bridge.run_command(["true"]))


def test_goose_agent_loop_extension_command_includes_identity_and_workspace():
    from sovereign_ai.agents.goose_loop import GooseAgentLoop

    state = {"agent_profile_id": "tournament-task", "workspace": "/tmp/ws"}
    command = GooseAgentLoop._extension_command(state)
    assert "SOAI_MCP_AGENT_PROFILE_ID=tournament-task" in command
    assert "SOAI_MCP_WORKSPACE=/tmp/ws" in command
    assert "sovereign_ai.agents.mcp_bridge" in command


def test_goose_agent_loop_enable_tools_defaults_off():
    from sovereign_ai.agents.goose_loop import GooseAgentLoop

    loop = GooseAgentLoop("goose", "http://127.0.0.1:1/v1", "m")
    assert loop.enable_tools is False


# ---------------------------------------------------------------------------------------
# The tool plane (knowledge/research.md research wave 8, D-034).
#
# Wave 8's reachability audit found ToolRegistry holding zero tools while ~290 GB of
# specialist models sat installed and uncallable, and the agent loop limited to read_file /
# list_directory / run_command. These tests exist so "installed" can never again be mistaken
# for "reachable": they assert registration, that the new tools work end to end through the
# real loop, and -- most importantly -- that widening what an agent can do did not widen how
# authority is decided.
# ---------------------------------------------------------------------------------------


def test_tool_plane_is_registered_and_covers_the_capability_domains(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    names = set(k.tool_dispatcher.names())

    # Files and search: the minimum for a coding agent.
    assert {"read_file", "write_file", "edit_file", "grep", "glob", "run_command"} <= names
    # The domains wave 8 found unreachable.
    assert {
        "invoke_specialist",
        "generate_media",
        "search_memory",
        "remember",
        "web_search",
    } <= names
    # The registry itself is no longer an empty dictionary behind a ranking algorithm.
    assert len(k.tools.discover("edit a python file", limit=10)) > 0
    assert k.tool_dispatcher.describe().count("\n") >= len(names) - 1


def test_agent_loop_writes_a_file_only_with_a_capability_grant(tmp_path, monkeypatch):
    """The whole point of the tool plane: a real edit, still refused by default.

    Untrusted model output plus a mutation is exactly what PolicyEngine's untrusted-content
    gate blocks, so the first attempt must fail even though the workspace is writable. The
    second attempt differs only by an active CapabilityGrant -- the same mechanism F-037
    established for execution, now covering file writes.
    """
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    target = workspace / "generated.txt"

    action = json.dumps(
        {
            "tool": "write_file",
            "args": {"path": target.as_posix(), "content": "written by the agent\n"},
        }
    )
    fake = _FakeInference([action, '{"tool": "done", "summary": "stopped after denial"}'])
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events, tools=k.tool_dispatcher)
    state = {
        "run_id": "tool-run-1",
        "task": "create a file",
        "workspace": str(workspace),
        "agent_profile_id": "agent-writer",
    }

    denied = asyncio.run(loop.next_step(state))
    assert denied.payload["observation"]["denied"] is True
    assert not target.exists(), "a denied write must not touch the filesystem"

    # Now issue exactly the grant the policy path demands, and nothing more.
    k.capability_grants.issue(
        "agent-writer", "write", "workspace", "test-operator", ttl_seconds=60
    )
    fake._replies = [action, '{"tool": "done", "summary": "wrote the file"}']
    state["history"] = []
    allowed = asyncio.run(loop.next_step(state))

    assert allowed.payload["observation"]["created"] is True
    # Reread from disk rather than trusting the tool's own report.
    assert target.read_text(encoding="utf-8") == "written by the agent\n"


def test_edit_file_refuses_an_ambiguous_match(tmp_path, monkeypatch):
    from sovereign_ai.tools.base import ToolContext
    from sovereign_ai.tools.files import EditFileTool

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    target = workspace / "dup.py"
    target.write_text("x = 1\nx = 1\n", encoding="utf-8")
    k.capability_grants.issue(
        "agent-editor", "write", "workspace", "test-operator", ttl_seconds=60
    )

    tool = EditFileTool(k.workspaces, k.execution)
    ctx = ToolContext(workspace=str(workspace), subject_id="agent-editor")

    ambiguous = asyncio.run(
        tool.run({"path": str(target), "old_string": "x = 1", "new_string": "x = 2"}, ctx)
    )
    assert ambiguous["occurrences"] == 2
    assert target.read_text(encoding="utf-8") == "x = 1\nx = 1\n", "refused edit must not write"

    unique = asyncio.run(
        tool.run({"path": str(target), "old_string": "x = 1\nx = 1", "new_string": "x = 2"}, ctx)
    )
    assert unique["replacements"] == 1
    assert target.read_text(encoding="utf-8") == "x = 2\n"


def test_grep_and_glob_are_first_class_read_tools(tmp_path, monkeypatch):
    """Searching is a read, and should be gated like one -- not smuggled through the
    execution policy as a shell command, which is all this project could do before."""
    from sovereign_ai.tools.base import ToolContext
    from sovereign_ai.tools.files import GlobTool, GrepTool

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    (workspace / "pkg").mkdir(parents=True)
    (workspace / "pkg" / "a.py").write_text("def target_function():\n    pass\n", encoding="utf-8")
    (workspace / "pkg" / "b.txt").write_text("target_function mentioned here\n", encoding="utf-8")
    (workspace / ".git").mkdir()
    (workspace / ".git" / "c.py").write_text("target_function()\n", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)
    ctx = ToolContext(workspace=str(workspace))

    hits = asyncio.run(GrepTool(k.workspaces).run({"pattern": r"def target_\w+"}, ctx))
    assert hits["count"] == 1
    assert hits["matches"][0]["line"] == 1

    scoped = asyncio.run(
        GrepTool(k.workspaces).run({"pattern": "target_function", "glob": "*.py"}, ctx)
    )
    # .git is skipped, so the only .py match is the real source file.
    assert [m["path"] for m in scoped["matches"]] == [str(workspace / "pkg" / "a.py")]

    found = asyncio.run(GlobTool(k.workspaces).run({"pattern": "**/*.py"}, ctx))
    assert found["matches"] == [str(workspace / "pkg" / "a.py")]


def test_tools_refuse_paths_outside_an_approved_workspace(tmp_path, monkeypatch):
    from sovereign_ai.tools.base import ToolContext

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    ctx = ToolContext(workspace=str(workspace), subject_id="agent-x")
    observation = asyncio.run(k.tool_dispatcher.invoke("read_file", {"path": str(outside)}, ctx))
    assert observation["denied"] is True
    assert "approved" in observation["error"]


def test_search_memory_tool_puts_retrieval_back_in_the_loop(tmp_path, monkeypatch):
    """D-038: ContextBuilder existed and no request path ever called it."""
    from sovereign_ai.tools.base import ToolContext

    k = kernel(tmp_path, monkeypatch)
    k.memory.put(
        kind="note",
        content="the deploy key lives in the operator's keyring, never in the repo",
        source="operator",
        trust="trusted_user",
    )
    ctx = ToolContext(subject_id="agent-reader")
    found = asyncio.run(k.tool_dispatcher.invoke("search_memory", {"query": "deploy key"}, ctx))
    assert found["count"] >= 1
    assert "keyring" in found["items"][0]["content"]
    assert found["items"][0]["trust"] == "trusted_user"


def test_remember_is_denied_without_a_grant_and_labelled_untrusted_with_one(
    tmp_path, monkeypatch
):
    from sovereign_ai.tools.base import ToolContext

    k = kernel(tmp_path, monkeypatch)
    ctx = ToolContext(subject_id="agent-writer")

    denied = asyncio.run(
        k.tool_dispatcher.invoke("remember", {"content": "I decided this is true"}, ctx)
    )
    assert denied["denied"] is True

    k.capability_grants.issue("agent-writer", "write", "memory", "test-operator", ttl_seconds=60)
    stored = asyncio.run(
        k.tool_dispatcher.invoke("remember", {"content": "I decided this is true"}, ctx)
    )
    # The agent does not get to choose its own trust label.
    assert stored["trust"] == "untrusted_model_output"
    rows = k.memory.search_lexical("decided")
    assert rows and rows[0]["trust"] == "untrusted_model_output"


def test_web_search_authorises_then_fails_legibly_when_the_engine_is_down(tmp_path, monkeypatch):
    """The SearXNG this project deploys had no client at all until the tool plane. When it
    is not running, the agent should get an actionable observation, not a stack trace."""
    from sovereign_ai.tools.base import ToolContext
    from sovereign_ai.tools.capabilities import WebSearchTool

    k = kernel(tmp_path, monkeypatch)
    tool = WebSearchTool(k.execution, base_url="http://127.0.0.1:9", timeout_s=2.0)
    result = asyncio.run(tool.run({"query": "sovereign ai"}, ToolContext(subject_id="agent-x")))
    assert "unreachable" in result["error"]
    assert "docker-compose" in result["error"]


# ---------------------------------------------------------------------------------------
# Constrained decoding (D-020, F-048). Measured on this machine before it existed: a live
# four-step task on the 9B fast brain spent two of its four turns emitting a reply the loop
# could not parse. These tests pin the mechanism and, more importantly, the honest
# degradation path -- a backend that cannot honour the schema must cost one retry and a
# recorded event, never the run.
# ---------------------------------------------------------------------------------------


class _RecordingInference:
    """Captures the model_overrides the loop passes, so the schema itself is assertable."""

    def __init__(self, replies: list[str], fail_when_constrained: bool = False):
        self._replies = list(replies)
        self.overrides: list[dict | None] = []
        self.fail_when_constrained = fail_when_constrained

    async def chat(self, request, messages, model_overrides=None):
        self.overrides.append(model_overrides)
        if self.fail_when_constrained and model_overrides:
            raise RuntimeError("backend does not support response_format")
        content = (
            self._replies.pop(0) if self._replies else '{"tool": "done", "summary": "done"}'
        )
        return {"result": {"choices": [{"message": {"content": content}}]}}


def test_action_schema_is_derived_from_the_registered_tools(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    schema = k.tool_dispatcher.action_schema()
    names = set(schema["properties"]["tool"]["enum"])
    assert names == set(k.tool_dispatcher.names()) | {"done"}
    assert schema["additionalProperties"] is False
    # `tool` is no longer globally required: a batch action carries `batch` instead, and
    # requiring `tool` would make every batch structurally invalid (F-059).
    assert "required" not in schema
    assert "batch" in schema["properties"]


def test_loop_constrains_decoding_with_the_action_schema(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)

    fake = _RecordingInference(['{"tool": "done", "summary": "nothing to do"}'])
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events, tools=k.tool_dispatcher)
    step = asyncio.run(loop.next_step({"run_id": "c-1", "task": "t", "workspace": str(workspace)}))

    assert step.kind == "done"
    sent = fake.overrides[0]
    assert sent["response_format"]["type"] == "json_schema"
    enum = sent["response_format"]["json_schema"]["schema"]["properties"]["tool"]["enum"]
    assert "read_file" in enum and "done" in enum


def test_loop_degrades_legibly_when_a_backend_rejects_the_schema(tmp_path, monkeypatch):
    """The prose parser survives only as a fallback, and its use is recorded as a
    degradation rather than treated as normal operation (D-020)."""
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)

    fake = _RecordingInference(
        ['{"tool": "done", "summary": "fell back"}', '{"tool": "done", "summary": "second"}'],
        fail_when_constrained=True,
    )
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events, tools=k.tool_dispatcher)
    state = {"run_id": "c-2", "task": "t", "workspace": str(workspace)}

    step = asyncio.run(loop.next_step(state))
    assert step.kind == "done", "a rejected constraint must not fail the run"
    assert fake.overrides[0] is not None and fake.overrides[1] is None

    events = [e["event_type"] for e in k.events.read_stream("agent-loop:c-2")]
    assert "agent.decoding.degraded" in events

    # The loop remembers, so the next turn does not pay for the same rejection again.
    state["history"] = []
    asyncio.run(loop.next_step(state))
    assert fake.overrides[2] is None


# ---------------------------------------------------------------------------------------
# Project instructions, context budget and file-state checkpoints (D-022, D-025, D-021).
# ---------------------------------------------------------------------------------------


def test_agents_md_is_loaded_as_guidance_not_permission(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text(
        "# House rules\nAlways run the tests with `pytest -q`.\n", encoding="utf-8"
    )
    k.workspaces.add(workspace, writable=False)

    fake = _RecordingInference(['{"tool": "done", "summary": "ok"}'])
    loop = NativeAgentLoop(fake, k.execution, k.workspaces, k.events, tools=k.tool_dispatcher)
    state = {"run_id": "agents-md", "task": "t", "workspace": str(workspace)}
    messages = loop._build_messages(state)
    system = messages[0]["content"]

    assert "Always run the tests with `pytest -q`" in system
    # It arrives explicitly framed as guidance that cannot authorise anything.
    assert "not permission" in system
    assert "cannot authorise" in system


def test_missing_agents_md_changes_nothing(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)
    loop = NativeAgentLoop(
        _RecordingInference([]), k.execution, k.workspaces, k.events, tools=k.tool_dispatcher
    )
    system = loop._build_messages({"run_id": "no-md", "task": "t", "workspace": str(workspace)})[0]
    assert "AGENTS.md" not in system["content"]


def test_compact_history_elides_the_middle_and_reports_what_it_dropped():
    from sovereign_ai.agents.context import ContextBudget, compact_history

    budget = ContextBudget(keep_recent_turns=2, keep_leading_turns=1)
    history = [
        {"assistant": f"reply {i}", "action": {"tool": tool}, "observation": obs}
        for i, (tool, obs) in enumerate(
            [
                ("read_file", {"path": "a"}),
                ("grep", {"count": 1}),
                ("grep", {"count": 0}),
                ("run_command", {"error": "boom"}),
                ("write_file", {"denied": True, "error": "denied: nope"}),
                ("read_file", {"path": "b"}),
                ("read_file", {"path": "c"}),
            ]
        )
    ]
    rendered, note = compact_history(history, budget)

    assert len(rendered) == 3
    assert rendered[0]["assistant"] == "reply 0"
    assert [turn["assistant"] for turn in rendered[1:]] == ["reply 5", "reply 6"]
    assert note["elided_turns"] == 4
    # The digest distinguishes a denial and an error from a success, because that is what a
    # model needs to not repeat them.
    assert note["tools"] == {
        "grep": 2,
        "run_command(error)": 1,
        "write_file(denied)": 1,
    }


def test_short_history_is_left_alone():
    from sovereign_ai.agents.context import ContextBudget, compact_history

    history = [{"assistant": "one", "action": {"tool": "read_file"}, "observation": {}}]
    rendered, note = compact_history(history, ContextBudget())
    assert rendered == history and note is None


def test_loop_compacts_a_long_history_and_records_it(tmp_path, monkeypatch):
    from sovereign_ai.agents.context import ContextBudget
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)
    loop = NativeAgentLoop(
        _RecordingInference([]),
        k.execution,
        k.workspaces,
        k.events,
        tools=k.tool_dispatcher,
        budget=ContextBudget(keep_recent_turns=2, keep_leading_turns=1),
    )
    state = {
        "run_id": "compact-1",
        "task": "long task",
        "workspace": str(workspace),
        "history": [
            {"assistant": f"r{i}", "action": {"tool": "read_file"}, "observation": {"path": str(i)}}
            for i in range(10)
        ],
    }
    messages = loop._build_messages(state)
    joined = " ".join(m["content"] for m in messages)

    assert "7 earlier steps elided" in joined
    assert "r9" in joined and "r0" in joined and "r5" not in joined
    events = [e["event_type"] for e in k.events.read_stream("agent-loop:compact-1")]
    assert "agent.context.compacted" in events


def test_observation_budget_truncates_without_hiding_that_it_did():
    from sovereign_ai.agents.context import ContextBudget, truncate_observation

    text = truncate_observation({"content": "x" * 5000}, ContextBudget(max_observation_chars=100))
    assert len(text) < 200
    assert "chars]" in text


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for shadow checkpoints")
def test_shadow_repository_snapshots_and_restores_without_touching_real_git(tmp_path):
    from sovereign_ai.kernel.shadow_git import ShadowRepository

    workspace = tmp_path / "ws"
    workspace.mkdir()
    real_git_marker = workspace / ".git"
    real_git_marker.mkdir()
    (real_git_marker / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    target = workspace / "code.py"
    target.write_text("original\n", encoding="utf-8")

    shadow = ShadowRepository(tmp_path / "state", workspace)
    first = shadow.snapshot("before")
    assert first is not None

    target.write_text("modified\n", encoding="utf-8")
    second = shadow.snapshot("after")
    assert second is not None and second.sha != first.sha

    shadow.restore(first.sha)
    assert target.read_text(encoding="utf-8") == "original\n"

    # The user's own repository was never a participant.
    assert (real_git_marker / "HEAD").read_text(encoding="utf-8") == "ref: refs/heads/main\n"
    assert not (real_git_marker / "objects").exists()
    assert len(shadow.history()) == 2


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for shadow checkpoints")
def test_agent_write_creates_a_restorable_checkpoint(tmp_path, monkeypatch):
    """D-021 end to end: an agent edit can be undone, which is what makes leaving one
    running reasonable in the first place."""
    from sovereign_ai.agents.native_loop import NativeAgentLoop
    from sovereign_ai.kernel.shadow_git import ShadowRepository

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "code.py").write_text("original\n", encoding="utf-8")
    k.workspaces.add(workspace, writable=True)
    k.capability_grants.issue("agent-w", "write", "workspace", "operator", ttl_seconds=60)

    state_dir = tmp_path / "shadow-state"
    shadow = ShadowRepository(state_dir, workspace)
    baseline = shadow.snapshot("baseline")
    assert baseline is not None

    action = json.dumps(
        {
            "tool": "write_file",
            "args": {"path": (workspace / "code.py").as_posix(), "content": "rewritten\n"},
        }
    )
    loop = NativeAgentLoop(
        _RecordingInference([action]),
        k.execution,
        k.workspaces,
        k.events,
        tools=k.tool_dispatcher,
        checkpoint_root=state_dir,
    )
    step = asyncio.run(
        loop.next_step(
            {
                "run_id": "ckpt-1",
                "task": "rewrite",
                "workspace": str(workspace),
                "agent_profile_id": "agent-w",
            }
        )
    )
    assert step.payload["observation"].get("error") is None
    assert (workspace / "code.py").read_text(encoding="utf-8") == "rewritten\n"

    events = [e for e in k.events.read_stream("agent-loop:ckpt-1")]
    created = [e for e in events if e["event_type"] == "agent.checkpoint.created"]
    assert created, "a mutating tool call must leave a restorable checkpoint"

    shadow.restore(baseline.sha)
    assert (workspace / "code.py").read_text(encoding="utf-8") == "original\n"


def test_read_only_tools_do_not_create_checkpoints(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("hello", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    action = json.dumps({"tool": "read_file", "args": {"path": (workspace / "a.txt").as_posix()}})
    loop = NativeAgentLoop(
        _RecordingInference([action]),
        k.execution,
        k.workspaces,
        k.events,
        tools=k.tool_dispatcher,
        checkpoint_root=tmp_path / "shadow-state",
    )
    asyncio.run(loop.next_step({"run_id": "ckpt-2", "task": "read", "workspace": str(workspace)}))
    events = [e["event_type"] for e in k.events.read_stream("agent-loop:ckpt-2")]
    assert "agent.checkpoint.created" not in events


# ---------------------------------------------------------------------------------------
# Server-sent events over the kernel journal (D-027). Wave 7's second severity-1 finding was
# that nothing in this system streamed: every surface polled on a four-second timer.
# ---------------------------------------------------------------------------------------


def test_event_store_reads_forward_from_a_cursor(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    k.events.append("run:a", "one", {"n": 1})
    k.events.append("other:b", "two", {"n": 2})
    k.events.append("run:a", "three", {"n": 3})

    everything = k.events.read_after(0)
    assert [e["event_type"] for e in everything] == ["one", "two", "three"]

    # A cursor resumes exactly where it stopped: no replay, no skip.
    after_first = k.events.read_after(int(everything[0]["seq"]))
    assert [e["event_type"] for e in after_first] == ["two", "three"]

    scoped = k.events.read_after(0, stream_prefix="run:")
    assert [e["event_type"] for e in scoped] == ["one", "three"]


def test_event_stream_endpoint_emits_sse_frames(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    client = api_client(tmp_path, monkeypatch)
    k.events.append("agent-loop:sse-1", "agent.step.tool_call", {"tool": "read_file"})
    k.events.append("agent-loop:sse-1", "agent.step.done", {"summary": "finished"})

    response = client.get("/events/stream?follow=false")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    body = response.text
    assert "event: agent.step.tool_call" in body
    assert "event: agent.step.done" in body
    assert "data: {" in body
    # Every frame carries its sequence as the SSE id, which is what makes reconnection exact.
    assert "id: 1" in body


def test_event_stream_requires_a_session(tmp_path, monkeypatch):
    client = api_client(tmp_path, monkeypatch)
    del client.headers["Authorization"]
    assert client.get("/events/stream?follow=false").status_code == 401


def test_event_stream_resumes_from_a_cursor_without_replaying(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    client = api_client(tmp_path, monkeypatch)
    k.events.append("agent-loop:sse-2", "first", {})
    first_seq = int(k.events.read_after(0)[-1]["seq"])
    k.events.append("agent-loop:sse-2", "second", {})

    body = client.get(f"/events/stream?follow=false&after={first_seq}").text
    assert "event: second" in body
    assert "event: first" not in body


# ---------------------------------------------------------------------------------------
# Endpoints the control surface needs (research wave 7 X-01/X-03, D-026/D-028).
# ---------------------------------------------------------------------------------------


def test_workspaces_endpoint_lists_only_registered_directories(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, label="demo", writable=True)
    client = api_client(tmp_path, monkeypatch)

    body = client.get("/workspaces").json()
    assert [w["label"] for w in body["workspaces"]] == ["demo"]
    assert body["workspaces"][0]["writable"] is True


def test_tools_endpoint_exposes_the_plane_with_its_risk_scopes(tmp_path, monkeypatch):
    client = api_client(tmp_path, monkeypatch)
    tools = {t["id"]: t for t in client.get("/tools").json()["tools"]}

    assert {"read_file", "write_file", "grep", "web_search", "invoke_specialist"} <= set(tools)
    assert tools["read_file"]["mutating"] is False
    assert tools["write_file"]["mutating"] is True
    assert tools["web_search"]["risk_scope"] == "public_web"


def test_issuing_a_grant_is_bounded_authenticated_and_audited(tmp_path, monkeypatch):
    """The control surface's 'authorise writes' control has to issue a real grant, because
    approval alone can never authorise a model-proposed mutation (F-036). That makes this
    endpoint an authority surface, so its bounds are part of the contract."""
    k = kernel(tmp_path, monkeypatch)
    client = api_client(tmp_path, monkeypatch)

    unauthenticated = TestClient(create_app(str(ROOT / "configs")), base_url="http://127.0.0.1")
    assert unauthenticated.post("/roster/grants", json={
        "subject_id": "x", "action": "write", "scope": "workspace"}).status_code == 401

    created = client.post("/roster/grants", json={
        "subject_id": "web-operator", "action": "write", "scope": "workspace",
        "ttl_seconds": 900, "reason": "test"})
    assert created.status_code == 201
    assert k.capability_grants.is_active("web-operator", "write", "workspace")

    # Closed enumerations and a capped TTL: not a general-purpose authority faucet.
    assert client.post("/roster/grants", json={
        "subject_id": "web-operator", "action": "sudo", "scope": "workspace"}).status_code == 422
    assert client.post("/roster/grants", json={
        "subject_id": "web-operator", "action": "write", "scope": "workspace",
        "ttl_seconds": 999_999}).status_code == 422

    # And it leaves a record of who authorised what.
    issued = [e for e in k.events.read_after(0) if e["event_type"] == "capability_grant.issued"]
    assert issued and "write" in issued[-1]["payload_json"]


def test_grant_actually_unblocks_a_write_that_approval_alone_cannot(tmp_path, monkeypatch):
    """The finding that motivated the endpoint: `approved=True` does not help, because
    PolicyEngine's untrusted-content gate never returns allowed for a model-proposed
    mutation. Only a grant does. This pins that so no UI can imply otherwise again."""
    from sovereign_ai.tools.base import ToolContext

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    target = workspace / "out.txt"

    approved_ctx = ToolContext(workspace=str(workspace), approved=True, subject_id="ui-subject")
    denied = asyncio.run(k.tool_dispatcher.invoke(
        "write_file", {"path": str(target), "content": "x"}, approved_ctx))
    assert denied["denied"] is True, "approval must not authorise an untrusted mutation"
    assert not target.exists()

    k.capability_grants.issue("ui-subject", "write", "workspace", "operator", ttl_seconds=60)
    allowed = asyncio.run(k.tool_dispatcher.invoke(
        "write_file", {"path": str(target), "content": "x"},
        ToolContext(workspace=str(workspace), subject_id="ui-subject")))
    assert allowed.get("created") is True
    assert target.read_text(encoding="utf-8") == "x"


def test_control_surface_html_is_served_with_a_session_token(tmp_path, monkeypatch):
    """The page authenticates with a header, never a token in the URL, so the server has to
    inject it into the document it serves."""
    client = api_client(tmp_path, monkeypatch)
    page = client.get("/ui")
    assert page.status_code == 200
    body = page.text
    assert "%%SOAI_SESSION_TOKEN%%" not in body, "the placeholder must be substituted"
    assert "/events/stream" in body, "the surface must consume the stream, not poll"
    assert 'role="tablist"' in body and 'aria-live' in body


def test_mcp_bridge_exposes_the_whole_tool_plane(tmp_path, monkeypatch):
    """The bridge must not drift from the tool plane.

    Widening it from three tools to all thirteen is what lets an external harness run on
    *governed* tools rather than raw filesystem access (knowledge/harness-research.md).
    If a tool is ever added to the kernel and not here, an external harness silently loses
    a capability the native loop has -- so this asserts the two sets match.
    """
    k = kernel(tmp_path, monkeypatch)
    bridge = _reset_mcp_bridge_kernel()

    exposed = {
        name
        for name in dir(bridge)
        if callable(getattr(bridge, name))
        and not name.startswith("_")
        and name in set(k.tool_dispatcher.names())
    }
    assert exposed == set(k.tool_dispatcher.names()), (
        "bridge and tool plane disagree: "
        f"missing={set(k.tool_dispatcher.names()) - exposed}"
    )


def test_mcp_bridge_write_is_denied_without_a_grant_then_allowed_with_one(
    tmp_path, monkeypatch
):
    """The point of the bridge: an external harness gets the same authority model, not a
    weaker one. Same assertion as the native loop's own test, through MCP instead."""
    k = kernel(tmp_path, monkeypatch)
    bridge = _reset_mcp_bridge_kernel()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    target = workspace / "bridged.txt"
    monkeypatch.setenv("SOAI_MCP_AGENT_PROFILE_ID", "bridge-subject")
    monkeypatch.setenv("SOAI_MCP_WORKSPACE", str(workspace))

    with pytest.raises(PermissionError):
        asyncio.run(bridge.write_file(str(target), "hello"))
    assert not target.exists(), "a denied bridged write must not touch the filesystem"

    k.capability_grants.issue(
        "bridge-subject", "write", "workspace", "test-operator", ttl_seconds=60
    )
    result = asyncio.run(bridge.write_file(str(target), "hello"))
    assert "created" in result
    assert target.read_text(encoding="utf-8") == "hello"


def test_mcp_bridge_formats_for_tokens_not_json(tmp_path, monkeypatch):
    """read_file returns raw text and grep returns `path:line: text`.

    Wrapping a whole file in JSON to escape it would inflate exactly the resource this
    project has least of (docs/FIXES.md F-005: 6.36 tok/s on the deep brain)."""
    k = kernel(tmp_path, monkeypatch)
    bridge = _reset_mcp_bridge_kernel()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.py").write_text('x = "quoted"\ndef find_me():\n    pass\n', encoding="utf-8")
    k.workspaces.add(workspace, writable=False)
    monkeypatch.setenv("SOAI_MCP_WORKSPACE", str(workspace))

    content = asyncio.run(bridge.read_file(str(workspace / "a.py")))
    assert content.startswith('x = "quoted"'), "content must not be JSON-escaped"

    hits = asyncio.run(bridge.grep("def find_me"))
    assert hits.splitlines()[0].endswith(":2: def find_me():")


def test_mcp_bridge_reports_expected_failures_in_band(tmp_path, monkeypatch):
    """A missing file is an observation the agent should act on; a policy denial is a
    protocol fault. The bridge distinguishes them deliberately."""
    k = kernel(tmp_path, monkeypatch)
    bridge = _reset_mcp_bridge_kernel()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)

    result = asyncio.run(bridge.read_file(str(workspace / "absent.txt")))
    assert result.startswith("error: not a file")


# ---------------------------------------------------------------------------------------
# OpenCode adapter (knowledge/harness-research.md ranked it the strongest mature
# provider-neutral open harness; F-054's tournament could not measure it because no adapter
# existed). These tests pin the containment properties, which are the whole reason a
# bridged external harness is comparable to the native loop at all.
# ---------------------------------------------------------------------------------------


def _opencode_loop(**kwargs):
    from sovereign_ai.agents.opencode_loop import OpenCodeAgentLoop

    return OpenCodeAgentLoop(
        "/nonexistent/opencode", "http://127.0.0.1:18080/v1", "qwen35-9b", **kwargs
    )


def test_opencode_adapter_disables_every_builtin_tool():
    """A bridged run must have no ungoverned path to the filesystem, shell or network.

    If any built-in survived, the tournament would compare a harness using tools that never
    pass through PolicyEngine against a native loop whose every action does -- which would
    make the comparison meaningless and the result flattering to the wrong side.
    """
    from sovereign_ai.agents.opencode_loop import _BUILTIN_TOOLS_TO_DISABLE

    config = _opencode_loop()._config({"workspace": "/tmp/ws", "agent_profile_id": "s"})
    assert set(config["tools"]) == set(_BUILTIN_TOOLS_TO_DISABLE)
    assert all(enabled is False for enabled in config["tools"].values())
    for dangerous in ("bash", "write", "edit", "read", "webfetch"):
        assert config["tools"][dangerous] is False


def test_opencode_adapter_points_only_at_the_kernel_bridge():
    config = _opencode_loop()._config(
        {"workspace": "/tmp/ws", "agent_profile_id": "subject-1", "run_id": "run-1"}
    )
    assert list(config["mcp"]) == ["kernel"], "the bridge must be the only tool source"
    server = config["mcp"]["kernel"]
    assert server["type"] == "local"
    assert server["command"][-1] == "sovereign_ai.agents.mcp_bridge"
    # The identity every grant is checked against has to reach the bridge, or every
    # mutating call is denied for the wrong reason.
    assert server["environment"]["SOAI_MCP_AGENT_PROFILE_ID"] == "subject-1"
    assert server["environment"]["SOAI_MCP_WORKSPACE"] == "/tmp/ws"


def test_opencode_adapter_provider_points_at_the_local_router():
    config = _opencode_loop()._config({})
    provider = config["provider"]["sovereign"]
    assert provider["options"]["baseURL"] == "http://127.0.0.1:18080/v1"
    assert "qwen35-9b" in provider["models"]


def test_opencode_adapter_without_tools_has_no_mcp_server():
    config = _opencode_loop(enable_tools=False)._config({"workspace": "/tmp/ws"})
    assert "mcp" not in config
    assert all(enabled is False for enabled in config["tools"].values())


def test_opencode_adapter_never_writes_its_config_into_the_workspace(tmp_path):
    """The tournament's post-conditions inspect the workspace directory, so a config file
    dropped there would let the harness's own configuration count as task output."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    loop = _opencode_loop()
    step = asyncio.run(
        loop.next_step(
            {"task": "anything", "workspace": str(workspace), "agent_profile_id": "s"}
        )
    )
    assert step.done and step.kind == "harness_error"
    assert "not found" in step.payload["error"]
    assert list(workspace.iterdir()) == [], "the workspace must be left exactly as found"


def test_opencode_loop_registers_only_when_the_binary_exists(tmp_path, monkeypatch):
    """Runtime truth over manifest assumption: an install without OpenCode gets one fewer
    loop, not a loop that fails at first use."""
    from sovereign_ai.kernel import app as kernel_app

    monkeypatch.setattr(kernel_app, "resolve_opencode_binary", lambda: None)
    absent = kernel(tmp_path, monkeypatch)
    assert "opencode" not in absent.agent_loops.names()

    monkeypatch.setattr(kernel_app, "resolve_opencode_binary", lambda: "/usr/bin/opencode")
    present = kernel(tmp_path / "second", monkeypatch)
    assert "opencode" in present.agent_loops.names()


# ---------------------------------------------------------------------------------------
# The HTTP tool-invoke endpoint and the Pi adapter.
#
# Pi has no MCP client by design, so the bridge that reaches Goose and OpenCode cannot
# reach it. It does have in-process extensions, so its extension calls POST /tools/{name}
# instead -- which means that endpoint is now an authority surface and is tested like one.
# ---------------------------------------------------------------------------------------


def test_tool_invoke_endpoint_enforces_the_same_grant_rule(tmp_path, monkeypatch):
    k = kernel(tmp_path, monkeypatch)
    client = api_client(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=True)
    target = workspace / "http.txt"

    denied = client.post(
        "/tools/write_file",
        json={
            "args": {"path": str(target), "content": "x"},
            "workspace": str(workspace),
            "subject_id": "http-subject",
        },
    )
    # A refusal must be a protocol error, not a 200 whose body mentions denial.
    assert denied.status_code == 403
    assert "denied" in denied.json()["detail"]
    assert not target.exists()

    k.capability_grants.issue("http-subject", "write", "workspace", "operator", ttl_seconds=60)
    allowed = client.post(
        "/tools/write_file",
        json={
            "args": {"path": str(target), "content": "x"},
            "workspace": str(workspace),
            "subject_id": "http-subject",
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["result"]["created"] is True
    assert target.read_text(encoding="utf-8") == "x"


def test_tool_invoke_endpoint_requires_a_session_and_a_real_tool(tmp_path, monkeypatch):
    client = api_client(tmp_path, monkeypatch)
    assert client.post("/tools/does_not_exist", json={"args": {}}).status_code == 404

    unauthenticated = TestClient(create_app(str(ROOT / "configs")), base_url="http://127.0.0.1")
    assert unauthenticated.post("/tools/read_file", json={"args": {}}).status_code == 401


def test_tools_endpoint_publishes_a_usable_json_schema(tmp_path, monkeypatch):
    """A protocol client declares our tools to its own model from this, so it has to be a
    real schema rather than the prompt's worked example."""
    client = api_client(tmp_path, monkeypatch)
    tools = {t["id"]: t for t in client.get("/tools").json()["tools"]}

    read = tools["read_file"]["input_schema"]
    assert read["type"] == "object"
    assert read["properties"]["path"]["type"] == "string"
    assert read["properties"]["offset"]["type"] == "integer"

    run = tools["run_command"]["input_schema"]
    assert run["properties"]["argv"]["type"] == "array"
    assert run["properties"]["mutates_state"]["type"] == "boolean"


def _pi_loop(**kwargs):
    from sovereign_ai.agents.pi_loop import PiAgentLoop

    return PiAgentLoop(
        "/nonexistent/pi",
        "http://127.0.0.1:18080/v1",
        "qwen35-9b",
        kernel_url="http://127.0.0.1:7788",
        session_token="test-token",
        **kwargs,
    )


def test_pi_adapter_declares_a_generic_openai_compatible_provider():
    """Deliberately not Pi's built-in llama.cpp provider: that integration drives the
    router's management API and answered 404/503 against this build (F-056)."""
    config = _pi_loop()._models_json()
    provider = config["providers"]["sovereign"]
    assert provider["api"] == "openai-completions"
    assert provider["baseUrl"] == "http://127.0.0.1:18080/v1"
    assert provider["compat"]["supportsDeveloperRole"] is False
    assert [m["id"] for m in provider["models"]] == ["qwen35-9b"]


def test_pi_adapter_environment_carries_identity_and_isolates_operator_config(tmp_path):
    env = _pi_loop()._environment(
        {"agent_profile_id": "subject-1", "workspace": "/tmp/ws", "run_id": "run-1"},
        tmp_path / "agent",
    )
    assert env["SOAI_AGENT_PROFILE_ID"] == "subject-1"
    assert env["SOAI_WORKSPACE"] == "/tmp/ws"
    assert env["SOAI_SESSION_TOKEN"] == "test-token"
    assert env["SOAI_KERNEL_URL"] == "http://127.0.0.1:7788"
    # A run must not read or write the operator's own Pi config, sessions or credentials.
    assert env["PI_CODING_AGENT_DIR"] == str(tmp_path / "agent")
    # Nor make startup network calls on a machine whose premise is working without one.
    assert env["PI_OFFLINE"] == "1"


def test_pi_extension_ships_in_this_repository_and_uses_only_the_kernel():
    """The extension is part of *our* authority model, not Pi's, so it lives here -- and
    it must reach the kernel and nothing else."""
    from sovereign_ai.agents.pi_loop import PI_EXTENSION

    assert PI_EXTENSION.is_file(), f"missing {PI_EXTENSION}"
    source = PI_EXTENSION.read_text(encoding="utf-8")
    assert "SOAI_KERNEL_URL" in source
    assert "/tools/" in source
    # Tools are discovered, never hard-coded, so the extension cannot drift from the plane.
    assert "GET /tools" in source or "listTools" in source


def test_pi_adapter_reports_a_missing_binary_without_touching_the_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    step = asyncio.run(
        _pi_loop().next_step(
            {"task": "anything", "workspace": str(workspace), "agent_profile_id": "s"}
        )
    )
    assert step.done and step.kind == "harness_error"
    assert "not found" in step.payload["error"]
    assert list(workspace.iterdir()) == []


def test_pi_loop_registers_only_when_the_binary_exists(tmp_path, monkeypatch):
    from sovereign_ai.kernel import app as kernel_app

    monkeypatch.setattr(kernel_app, "resolve_pi_binary", lambda: None)
    absent = kernel(tmp_path, monkeypatch)
    assert "pi" not in absent.agent_loops.names()

    monkeypatch.setattr(kernel_app, "resolve_pi_binary", lambda: "/usr/bin/pi")
    present = kernel(tmp_path / "second", monkeypatch)
    assert "pi" in present.agent_loops.names()


# ---------------------------------------------------------------------------------------
# Context economy in the tools themselves (knowledge/harness-research.md, adoption item 3).
# Both changes exist because the measured constraint on this machine is tokens per turn,
# not model quality: F-056 showed the lightest-context harness fastest and the heaviest
# timing out, on identical hardware.
# ---------------------------------------------------------------------------------------


def test_read_file_outlines_a_large_file_instead_of_dumping_it(tmp_path, monkeypatch):
    from sovereign_ai.tools.base import ToolContext
    from sovereign_ai.tools.files import ReadFileTool

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    body = ["import os", ""]
    for i in range(200):
        body += [f"def function_{i}():", f"    return {i}", ""]
    target = workspace / "big.py"
    target.write_text("\n".join(body), encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    result = asyncio.run(
        ReadFileTool(k.workspaces).run({"path": str(target)}, ToolContext(workspace=str(workspace)))
    )
    assert result["outlined"] is True
    assert result["total_lines"] > 400
    assert any("def function_0" in entry for entry in result["outline"])
    # The whole point: the observation is a sketch, not the file.
    assert len(result["content"]) < len(target.read_text(encoding="utf-8")) / 2
    assert "offset/limit" in result["note"] or "re-read" in result["note"].lower()


def test_read_file_still_returns_exact_text_for_a_requested_range(tmp_path, monkeypatch):
    """Outlining must never cost the agent access to the real content."""
    from sovereign_ai.tools.base import ToolContext
    from sovereign_ai.tools.files import ReadFileTool

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = workspace / "big.py"
    target.write_text("\n".join(f"line {i}" for i in range(1, 801)), encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    ranged = asyncio.run(
        ReadFileTool(k.workspaces).run(
            {"path": str(target), "offset": 500, "limit": 3},
            ToolContext(workspace=str(workspace)),
        )
    )
    assert ranged.get("outlined") is None
    assert ranged["content"] == "line 500\nline 501\nline 502"


def test_small_files_are_returned_whole(tmp_path, monkeypatch):
    from sovereign_ai.tools.base import ToolContext
    from sovereign_ai.tools.files import ReadFileTool

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = workspace / "small.txt"
    target.write_text("just\na\nfew\nlines", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    result = asyncio.run(
        ReadFileTool(k.workspaces).run({"path": str(target)}, ToolContext(workspace=str(workspace)))
    )
    assert result.get("outlined") is None
    assert result["content"] == "just\na\nfew\nlines"


def test_outline_finds_definitions_across_languages():
    from sovereign_ai.tools.files import outline

    sketch = outline(
        "\n".join(
            [
                "def python_fn():",
                "class PythonClass:",
                "export function tsFn() {",
                "pub fn rust_fn() {",
                "func goFn() {",
                "## A markdown heading",
                "    not_a_definition = 1",
            ]
        )
    )
    joined = " ".join(sketch)
    for expected in ["python_fn", "PythonClass", "tsFn", "rust_fn", "goFn", "markdown heading"]:
        assert expected in joined
    assert "not_a_definition" not in joined


def test_grep_uses_ripgrep_when_available_and_agrees_with_the_fallback(tmp_path, monkeypatch):
    """Both engines must return the same matches. A faster search that finds different
    things is not an optimisation, it is a bug."""
    from sovereign_ai.tools.base import ToolContext
    from sovereign_ai.tools.files import GrepTool

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    (workspace / "pkg").mkdir(parents=True)
    (workspace / "pkg" / "a.py").write_text("def target_function():\n    pass\n", encoding="utf-8")
    (workspace / "pkg" / "b.py").write_text("# calls target_function here\n", encoding="utf-8")
    (workspace / ".git").mkdir()
    (workspace / ".git" / "c.py").write_text("target_function()\n", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)
    ctx = ToolContext(workspace=str(workspace))

    tool = GrepTool(k.workspaces)
    real = asyncio.run(tool.run({"pattern": "target_function"}, ctx))

    # Force the portable path and compare.
    monkeypatch.setattr("sovereign_ai.tools.files.shutil.which", lambda name: None)
    fallback = asyncio.run(tool.run({"pattern": "target_function"}, ctx))

    def key(result):
        return sorted((Path(m["path"]).name, m["line"]) for m in result["matches"])

    assert key(real) == key(fallback)
    # .git is excluded by both.
    assert all(".git" not in m["path"] for m in real["matches"])
    assert fallback["engine"] == "python"


def test_grep_degrades_to_the_portable_path_when_ripgrep_misbehaves(tmp_path, monkeypatch):
    """A missing or unusual ripgrep must degrade, never break the tool."""
    from sovereign_ai.tools.base import ToolContext
    from sovereign_ai.tools.files import GrepTool

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("findme\n", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    monkeypatch.setattr(
        "sovereign_ai.tools.files.GrepTool._ripgrep",
        staticmethod(lambda *args, **kwargs: None),
    )
    result = asyncio.run(
        GrepTool(k.workspaces).run({"pattern": "findme"}, ToolContext(workspace=str(workspace)))
    )
    assert result["count"] == 1
    assert result["engine"] == "python"


# ---------------------------------------------------------------------------------------
# Focus Chain (knowledge/harness-research.md adoption item 4, adapted from Cline).
# F-049 elides history deterministically to fit a 16K window and nothing restated the
# objective afterwards, so a long run could forget what it was doing while still having
# room to keep doing something. These tests pin the fix and its trigger.
# ---------------------------------------------------------------------------------------


def test_update_plan_accepts_both_shapes_a_small_model_produces(tmp_path, monkeypatch):
    from sovereign_ai.tools.base import ToolContext

    k = kernel(tmp_path, monkeypatch)
    ctx = ToolContext(run_id="plan-run")

    bare = asyncio.run(
        k.tool_dispatcher.invoke(
            "update_plan", {"steps": ["read the config", "report the value"]}, ctx
        )
    )
    assert bare["recorded"] == 2
    assert "[ ] read the config" in bare["plan"]

    structured = asyncio.run(
        k.tool_dispatcher.invoke(
            "update_plan",
            {
                "steps": [
                    {"step": "read the config", "status": "done"},
                    {"step": "report the value", "status": "active"},
                ]
            },
            ctx,
        )
    )
    assert structured["done"] == 1
    assert "[x] read the config" in structured["plan"]
    assert "[>] report the value" in structured["plan"]


def test_update_plan_needs_no_grant_and_no_execution_backend(tmp_path, monkeypatch):
    """A loop that cannot restate its objective is the failure this prevents, so it must
    not be the thing policy refuses."""
    from sovereign_ai.tools.base import ToolContext

    k = kernel(tmp_path, monkeypatch)
    result = asyncio.run(
        k.tool_dispatcher.invoke("update_plan", {"steps": ["a step"]}, ToolContext())
    )
    assert result.get("denied") is None
    assert result["recorded"] == 1


def test_plans_are_scoped_per_run(tmp_path, monkeypatch):
    from sovereign_ai.tools.base import ToolContext

    k = kernel(tmp_path, monkeypatch)
    asyncio.run(k.tool_dispatcher.invoke("update_plan", {"steps": ["run one"]}, ToolContext(run_id="a")))
    asyncio.run(k.tool_dispatcher.invoke("update_plan", {"steps": ["run two"]}, ToolContext(run_id="b")))
    assert "run one" in k.tool_dispatcher.plans.render("a")
    assert "run one" not in k.tool_dispatcher.plans.render("b")
    assert k.tool_dispatcher.plans.render("never-seen") == ""


def test_loop_restates_the_objective_on_a_cadence(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)
    loop = NativeAgentLoop(
        _RecordingInference([]), k.execution, k.workspaces, k.events,
        tools=k.tool_dispatcher, focus_every=3,
    )
    state = {
        "run_id": "focus-1",
        "task": "find the deploy key",
        "workspace": str(workspace),
        "history": [],
    }

    def rendered(turns):
        state["history"] = [
            {"assistant": f"r{i}", "action": {"tool": "read_file"}, "observation": {"path": str(i)}}
            for i in range(turns)
        ]
        return " ".join(m["content"] for m in loop._build_messages(state))

    assert "Reminder of the objective" not in rendered(2)
    assert "Reminder of the objective: find the deploy key" in rendered(3)


def test_loop_restates_the_objective_whenever_history_was_elided(tmp_path, monkeypatch):
    """The cadence is not the only trigger: compaction is the exact moment a run loses the
    thread, so it restates unconditionally there even if no cadence turn is due."""
    from sovereign_ai.agents.context import ContextBudget
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)
    loop = NativeAgentLoop(
        _RecordingInference([]), k.execution, k.workspaces, k.events,
        tools=k.tool_dispatcher,
        budget=ContextBudget(keep_recent_turns=2, keep_leading_turns=1),
        focus_every=0,  # cadence disabled: only compaction can trigger a restatement
    )
    state = {
        "run_id": "focus-2",
        "task": "find the deploy key",
        "workspace": str(workspace),
        "history": [
            {"assistant": f"r{i}", "action": {"tool": "read_file"}, "observation": {"path": str(i)}}
            for i in range(9)
        ],
    }
    joined = " ".join(m["content"] for m in loop._build_messages(state))
    assert "Reminder of the objective: find the deploy key" in joined
    assert "Do not repeat work" in joined


def test_the_recorded_plan_is_restated_with_the_objective(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop
    from sovereign_ai.tools.base import ToolContext

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    k.workspaces.add(workspace, writable=False)
    asyncio.run(
        k.tool_dispatcher.invoke(
            "update_plan",
            {"steps": [{"step": "read config", "status": "done"}, {"step": "report", "status": "active"}]},
            ToolContext(run_id="focus-3"),
        )
    )
    loop = NativeAgentLoop(
        _RecordingInference([]), k.execution, k.workspaces, k.events,
        tools=k.tool_dispatcher, focus_every=2,
    )
    state = {
        "run_id": "focus-3",
        "task": "do the thing",
        "workspace": str(workspace),
        "history": [
            {"assistant": "r0", "action": {"tool": "read_file"}, "observation": {}},
            {"assistant": "r1", "action": {"tool": "read_file"}, "observation": {}},
        ],
    }
    joined = " ".join(m["content"] for m in loop._build_messages(state))
    assert "[x] read config" in joined
    assert "[>] report" in joined


# ---------------------------------------------------------------------------------------
# Parallel tool dispatch (knowledge/harness-research.md adoption item 5, from ForgeCode).
# Every turn costs a full generation at 6-52 tok/s, so three reads issued together remove
# two generations outright. The safety property is the interesting half: concurrency is
# allowed only where it cannot reorder mutations or their audit trail.
# ---------------------------------------------------------------------------------------


def test_action_schema_offers_a_bounded_batch(tmp_path, monkeypatch):
    from sovereign_ai.tools.dispatcher import MAX_BATCH

    k = kernel(tmp_path, monkeypatch)
    schema = k.tool_dispatcher.action_schema()
    batch = schema["properties"]["batch"]
    assert batch["type"] == "array"
    assert batch["maxItems"] == MAX_BATCH
    assert set(batch["items"]["properties"]["tool"]["enum"]) == set(k.tool_dispatcher.names()) | {"done"}


def test_read_only_batches_run_concurrently(tmp_path, monkeypatch):
    """The whole point: independent reads must not be serialised."""
    import time

    from sovereign_ai.tools.base import ToolContext

    k = kernel(tmp_path, monkeypatch)

    class _SlowTool:
        def __init__(self, name):
            from sovereign_ai.tools.registry import ToolSpec

            self.spec = ToolSpec(id=name, description="slow", capabilities=[], mutating=False)

        async def run(self, args, ctx):
            await asyncio.sleep(0.3)
            return {"ok": self.spec.id}

    for name in ("slow_a", "slow_b", "slow_c"):
        k.tool_dispatcher.register(_SlowTool(name))

    calls = [{"tool": "slow_a"}, {"tool": "slow_b"}, {"tool": "slow_c"}]
    started = time.perf_counter()
    results = asyncio.run(k.tool_dispatcher.invoke_batch(calls, ToolContext()))
    elapsed = time.perf_counter() - started

    assert [r["ok"] for r in results] == ["slow_a", "slow_b", "slow_c"]
    assert elapsed < 0.7, f"three 0.3s reads took {elapsed:.2f}s -- they were serialised"


def test_a_batch_containing_a_mutation_runs_in_order(tmp_path, monkeypatch):
    """Two writes racing on one workspace is a correctness hazard, and it also scrambles
    the order of the audit events and checkpoints meant to reconstruct what happened."""
    from sovereign_ai.tools.base import ToolContext
    from sovereign_ai.tools.registry import ToolSpec

    k = kernel(tmp_path, monkeypatch)
    order: list[str] = []

    class _Recorder:
        def __init__(self, name, mutating):
            self.spec = ToolSpec(id=name, description="x", capabilities=[], mutating=mutating)

        async def run(self, args, ctx):
            order.append(f"start:{self.spec.id}")
            await asyncio.sleep(0.05)
            order.append(f"end:{self.spec.id}")
            return {"ok": self.spec.id}

    k.tool_dispatcher.register(_Recorder("reader", False))
    k.tool_dispatcher.register(_Recorder("writer", True))

    asyncio.run(
        k.tool_dispatcher.invoke_batch(
            [{"tool": "reader"}, {"tool": "writer"}], ToolContext()
        )
    )
    # Strict interleaving would show start:reader, start:writer, ... if run concurrently.
    assert order == ["start:reader", "end:reader", "start:writer", "end:writer"]


def test_loop_executes_a_batch_and_records_one_event_per_call(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    (workspace / "items").mkdir(parents=True)
    (workspace / "a.txt").write_text("alpha", encoding="utf-8")
    (workspace / "b.txt").write_text("beta", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    action = json.dumps(
        {
            "batch": [
                {"tool": "read_file", "args": {"path": (workspace / "a.txt").as_posix()}},
                {"tool": "read_file", "args": {"path": (workspace / "b.txt").as_posix()}},
                {"tool": "list_directory", "args": {"path": workspace.as_posix()}},
            ]
        }
    )
    loop = NativeAgentLoop(
        _RecordingInference([action]), k.execution, k.workspaces, k.events,
        tools=k.tool_dispatcher,
    )
    step = asyncio.run(
        loop.next_step({"run_id": "batch-1", "task": "read both", "workspace": str(workspace)})
    )

    results = step.payload["observation"]["batch"]
    assert [r["tool"] for r in results] == ["read_file", "read_file", "list_directory"]
    assert results[0]["observation"]["content"] == "alpha"
    assert results[1]["observation"]["content"] == "beta"

    # The audit trail must look exactly as if the calls had arrived separately.
    events = [e for e in k.events.read_stream("agent-loop:batch-1")]
    tool_calls = [e for e in events if e["event_type"] == "agent.step.tool_call"]
    assert len(tool_calls) == 3
    assert all(e["payload"]["batched"] is True for e in tool_calls)
    assert [e["payload"]["tool"] for e in tool_calls] == [
        "read_file",
        "read_file",
        "list_directory",
    ]


def test_a_batch_is_capped(tmp_path, monkeypatch):
    from sovereign_ai.agents.native_loop import NativeAgentLoop
    from sovereign_ai.tools.dispatcher import MAX_BATCH

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("alpha", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    action = json.dumps(
        {
            "batch": [
                {"tool": "read_file", "args": {"path": (workspace / "a.txt").as_posix()}}
                for _ in range(MAX_BATCH + 4)
            ]
        }
    )
    loop = NativeAgentLoop(
        _RecordingInference([action]), k.execution, k.workspaces, k.events,
        tools=k.tool_dispatcher,
    )
    step = asyncio.run(
        loop.next_step({"run_id": "batch-2", "task": "spam", "workspace": str(workspace)})
    )
    assert len(step.payload["observation"]["batch"]) == MAX_BATCH


def test_single_actions_still_work_unchanged(tmp_path, monkeypatch):
    """The batch form is additive: a model that only ever emits one action is unaffected."""
    from sovereign_ai.agents.native_loop import NativeAgentLoop

    k = kernel(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("alpha", encoding="utf-8")
    k.workspaces.add(workspace, writable=False)

    action = json.dumps({"tool": "read_file", "args": {"path": (workspace / "a.txt").as_posix()}})
    loop = NativeAgentLoop(
        _RecordingInference([action]), k.execution, k.workspaces, k.events,
        tools=k.tool_dispatcher,
    )
    step = asyncio.run(
        loop.next_step({"run_id": "single-1", "task": "read", "workspace": str(workspace)})
    )
    assert step.payload["tool"] == "read_file"
    assert step.payload["observation"]["content"] == "alpha"
