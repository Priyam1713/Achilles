import asyncio
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from sovereign_ai.api.server import create_app
from sovereign_ai.kernel.app import SovereignKernel
from sovereign_ai.kernel.config import ConfigBundle
from sovereign_ai.kernel.jobs import JobStore
from sovereign_ai.kernel.registry import CapabilityRegistry
from sovereign_ai.kernel.types import ActionRequest, CapabilityRequest, RoutingMode, TrustLabel
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

