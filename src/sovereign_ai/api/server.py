from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from sovereign_ai.collaboration import IdentityAlreadyExists
from sovereign_ai.kernel import job_executor
from sovereign_ai.kernel.app import SovereignKernel
from sovereign_ai.kernel.auth import SessionAuth, allowed_hosts
from sovereign_ai.kernel.dispatcher import JobDispatcher, QueueFullError
from sovereign_ai.kernel.jobs import JobStatus
from sovereign_ai.kernel.skills import CandidateStatus
from sovereign_ai.kernel.trigger_scheduler import TriggerScheduler
from sovereign_ai.kernel.types import ActionRequest, CapabilityRequest, RoutingMode
from sovereign_ai.resources.telemetry import snapshot


class MediaRequest(BaseModel):
    request: CapabilityRequest
    settings: dict[str, Any]
    timeout_s: float | None = None


class SpecialistRequest(BaseModel):
    request: CapabilityRequest
    operation: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    timeout_s: float = 300.0


class ChatRequest(BaseModel):
    request: CapabilityRequest
    messages: list[dict[str, Any]]
    model_overrides: dict[str, Any] = Field(default_factory=dict)


class JobSubmission(BaseModel):
    kind: Literal["chat", "specialist", "media", "agent"]
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollaborationIdentityCreate(BaseModel):
    id: str
    display_name: str
    kind: Literal["human", "agent"] = "human"
    agent: dict[str, Any] | None = None


class CollaborationRoomCreate(BaseModel):
    id: str
    name: str
    purpose: str = ""
    owner_id: str = "owner"


class CollaborationMessageCreate(BaseModel):
    actor_id: str = "owner"
    content: str
    parent_event_id: str | None = None
    dispatch_mentions: bool = True


class CollaborationReactionCreate(BaseModel):
    actor_id: str = "owner"
    target_event_id: str
    emoji: str


class CollaborationCanvasUpdate(BaseModel):
    actor_id: str = "owner"
    content: str


class CollaborationMembershipCreate(BaseModel):
    requester_id: str = "owner"


class CollaborationIdentityUpdate(BaseModel):
    display_name: str
    kind: Literal["human", "agent"] = "human"
    agent: dict[str, Any] | None = None


class AgentProfileCreate(BaseModel):
    id: str
    display_name: str
    role: str
    routing_preferences: dict[str, Any] = Field(default_factory=dict)
    memory_scopes: list[str] = Field(default_factory=list)
    budgets: dict[str, Any] = Field(default_factory=dict)
    authority_ceiling: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentProfileStatusUpdate(BaseModel):
    status: Literal["active", "retired"]


class DelegationCreate(BaseModel):
    parent_subject_id: str
    objective: str
    requested_grants: list[dict[str, Any]]
    job_kind: Literal["chat", "specialist", "media", "agent"] = "agent"
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_artifacts: list[str] = Field(default_factory=list)
    acceptance_tests: list[str] = Field(default_factory=list)
    deadline: float | None = None
    budget: dict[str, Any] = Field(default_factory=dict)


class ApprovalResolve(BaseModel):
    resolver_id: str
    approved: bool
    reason: str


class WorkspaceLeaseCreate(BaseModel):
    path: str
    subject_id: str
    writable: bool = True
    ttl_seconds: float = 3600.0


class WorkflowStepCreate(BaseModel):
    id: str
    job_kind: Literal["chat", "specialist", "media", "agent"]
    request_template: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class WorkflowDefinitionCreate(BaseModel):
    name: str
    steps: list[WorkflowStepCreate]


class RecurringTriggerCreate(BaseModel):
    workflow_definition_id: str
    interval_seconds: float
    enabled: bool = True


class RecurringTriggerEnabledUpdate(BaseModel):
    enabled: bool


class SkillCandidateCreate(BaseModel):
    run_id: str
    objective: str
    proposed_by: str


class AgentEvaluationCreate(BaseModel):
    verdict: Literal["pass", "fail"]
    evaluated_by: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class SkillPromoteRequest(BaseModel):
    name: str
    promoted_by: str


def create_app(config_root: str | None = None) -> FastAPI:
    kernel = SovereignKernel.build(config_root)
    session = SessionAuth(kernel.config.state_dir / "session.token")
    system = kernel.config.system.get("system", {})
    hosts = allowed_hosts(system.get("bind", "127.0.0.1"), int(system.get("port", 7788)))
    resources = kernel.config.system.get("resources", {})
    dispatcher = JobDispatcher(
        kernel.jobs,
        kernel.runs,
        # submit_callback closes over `dispatcher` itself, defined two lines below --
        # safe because a lambda body is only evaluated when called, and no job runs
        # before this assignment completes (FIXES.md Tier 5: this is what lets a
        # WorkflowInstance's downstream step actually get dispatched once its
        # dependencies succeed, not just recorded as a new Job row).
        executor=lambda job, run: job_executor.execute(kernel, job, run, submit_callback=dispatcher.submit),
        max_concurrency=int(resources.get("max_concurrent_jobs", 4)),
        queue_max=int(resources.get("job_queue_max", 100)),
    )
    trigger_scheduler = TriggerScheduler(
        kernel.triggers, kernel.workflows, dispatcher.submit,
        poll_interval_seconds=float(resources.get("trigger_poll_interval_seconds", 5.0)),
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        dispatcher.start()
        trigger_scheduler.start()
        yield
        await trigger_scheduler.shutdown()
        await dispatcher.shutdown()

    app = FastAPI(title="Local Sovereign AI Kernel", version="0.1.0", lifespan=lifespan)
    app.state.kernel = kernel
    app.state.dispatcher = dispatcher
    app.state.trigger_scheduler = trigger_scheduler
    # Exposed for local tooling/tests that need to call authenticated endpoints
    # in-process; never rendered anywhere except the loopback-checked /ui response.
    app.state.session_token = session.token
    kernel.jobs.recover_interrupted()
    kernel.runs.recover_interrupted()

    def _host_ok(value: str | None) -> bool:
        return bool(value) and value.split(",")[0].strip() in hosts

    class LoopbackOnlyMiddleware(BaseHTTPMiddleware):
        """Reject any request whose Host/Origin does not match this installation.

        This is a DNS-rebinding guard (FIXES.md F-004): a page served from an attacker
        domain whose DNS resolves to 127.0.0.1 can make a victim's browser send requests
        that *look* same-origin, but it cannot forge the Host header a legitimate loopback
        client sends. Applies to every request, including unauthenticated GETs, because the
        session token itself is served from ``/ui`` and must not leak to a rebound origin.
        """

        async def dispatch(self, request: Request, call_next):
            if not _host_ok(request.headers.get("host")):
                return HTMLResponse("Host not allowed", status_code=400)
            origin = request.headers.get("origin")
            if origin is not None:
                origin_host = origin.split("://", 1)[-1]
                if not _host_ok(origin_host):
                    return HTMLResponse("Origin not allowed", status_code=400)
            return await call_next(request)

    app.add_middleware(LoopbackOnlyMiddleware)

    async def require_session(authorization: str | None = Header(default=None)) -> None:
        """Bearer-token guard applied to every mutating (POST/PUT/DELETE) route.

        FIXES.md F-004: previously no mutation endpoint required any credential at all.
        """
        presented = None
        if authorization and authorization.lower().startswith("bearer "):
            presented = authorization[7:].strip()
        if not session.verify(presented):
            raise HTTPException(status_code=401, detail="missing or invalid session token")

    def collaboration_human(identity_id: str):
        identity = kernel.collaboration.store.get_identity(identity_id)
        if identity is None:
            raise HTTPException(status_code=404, detail="collaboration identity not found")
        if identity.kind != "human":
            raise HTTPException(
                status_code=403,
                detail="public collaboration endpoints cannot impersonate agents or the kernel",
            )
        return identity

    def enqueue_job(submission: JobSubmission):
        """Create a durable Job and hand it to the bounded dispatcher (FIXES.md F-010).

        Actual execution -- what "chat"/"specialist"/"media" means, and posting the
        collaboration-room reply -- lives in kernel.job_executor, not here; this function
        is purely admission. A full queue is a 503, not an unboundedly growing task list.
        """
        job = kernel.jobs.create(submission.kind, submission.payload, submission.metadata)
        try:
            dispatcher.submit(job)
        except QueueFullError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return job

    @app.get("/ui", include_in_schema=False)
    async def ui() -> HTMLResponse:
        # Resolved relative to the repository root, not the process CWD (FIXES.md F-015):
        # this file lives at src/sovereign_ai/api/server.py, four directories under root.
        repo_root = Path(__file__).resolve().parents[3]
        path = repo_root / "web" / "index.html"
        if not path.exists():
            raise HTTPException(status_code=404, detail="UI not found")
        html = path.read_text(encoding="utf-8")
        # The LoopbackOnlyMiddleware above already proved this request's Host/Origin belong
        # to this installation before this handler runs, so it is safe to hand the page the
        # token it needs to call mutating endpoints. See FIXES.md F-004.
        html = html.replace("%%SOAI_SESSION_TOKEN%%", session.token)
        return HTMLResponse(html)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "resources": snapshot(kernel.config.state_dir).model_dump()}

    @app.get("/status")
    async def status() -> dict[str, Any]:
        engine_checks: dict[str, bool] = {}
        checks: list[tuple[str, Any]] = []
        for engine_id, spec in kernel.registry.engines.items():
            if not spec.enabled:
                continue
            backend = kernel.inference.backends.get(engine_id) or kernel.media.backends.get(
                engine_id
            )
            if backend is not None:
                checks.append((engine_id, backend.health()))
        results = await asyncio.gather(*(check for _, check in checks), return_exceptions=True)
        for (engine_id, _), result in zip(checks, results, strict=True):
            engine_checks[engine_id] = result is True
        active_jobs = kernel.jobs.list("running", limit=500)
        queued_jobs = kernel.jobs.list("queued", limit=500)
        return {
            "ok": True,
            "inference_ready": any(engine_checks.values()),
            "engines": engine_checks,
            "jobs": {
                "running": len(active_jobs),
                "queued": len(queued_jobs),
                "dispatcher_active": dispatcher.active_count,
                "dispatcher_queue_depth": dispatcher.queue_depth,
            },
            "collaboration": kernel.collaboration.status(),
            "gpu_leases": [lease.__dict__ for lease in await kernel.gpu.active()],
            "paths": {
                "state": str(kernel.config.state_dir),
                "models": str(kernel.config.model_dir),
                "cache": str(kernel.config.cache_dir),
            },
        }

    @app.get("/capabilities")
    async def capabilities() -> dict[str, Any]:
        return {"capabilities": kernel.registry.capabilities()}

    @app.post("/route", dependencies=[Depends(require_session)])
    async def route(req: CapabilityRequest) -> dict[str, Any]:
        return kernel.scheduler.route(req).model_dump()

    @app.post("/policy/evaluate", dependencies=[Depends(require_session)])
    async def policy(req: ActionRequest) -> dict[str, Any]:
        return kernel.policy.evaluate(req).model_dump()

    @app.post("/chat", dependencies=[Depends(require_session)])
    async def chat(req: ChatRequest) -> dict[str, Any]:
        try:
            return await kernel.inference.chat(req.request, req.messages, req.model_overrides)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/specialist/invoke", dependencies=[Depends(require_session)])
    async def specialist_invoke(req: SpecialistRequest) -> dict[str, Any]:
        try:
            return await kernel.specialists.invoke(
                req.request, req.operation, req.inputs, req.options, req.timeout_s
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/media/generate", dependencies=[Depends(require_session)])
    async def media_generate(req: MediaRequest) -> dict[str, Any]:
        try:
            return await kernel.media.generate(req.request, req.settings, req.timeout_s)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/jobs", status_code=202, dependencies=[Depends(require_session)])
    async def submit_job(submission: JobSubmission) -> dict[str, Any]:
        return enqueue_job(submission).model_dump()

    @app.get("/collaboration/status")
    async def collaboration_status() -> dict[str, Any]:
        return kernel.collaboration.status()

    @app.get("/collaboration/identities")
    async def collaboration_identities() -> dict[str, Any]:
        return {
            "identities": [item.model_dump() for item in kernel.collaboration.identities()]
        }

    @app.post(
        "/collaboration/identities",
        status_code=201,
        dependencies=[Depends(require_session)],
    )
    async def create_collaboration_identity(
        request: CollaborationIdentityCreate,
    ) -> dict[str, Any]:
        try:
            if request.kind == "agent" and request.agent:
                capability = request.agent.get("capability")
                mode = request.agent.get("mode")
                if capability not in kernel.registry.capabilities():
                    raise ValueError(f"Unknown agent capability: {capability}")
                RoutingMode(mode)
            trust = "untrusted_model_output" if request.kind == "agent" else "untrusted_collaboration"
            return kernel.collaboration.create_identity(
                request.id, request.display_name, request.kind, trust, request.agent
            ).model_dump()
        except IdentityAlreadyExists as exc:
            # FIXES.md F-003: creation is exclusive, not upsert. A caller cannot silently
            # redefine an existing identity's kind, trust or agent routing.
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put(
        "/collaboration/identities/{identity_id}",
        dependencies=[Depends(require_session)],
    )
    async def update_collaboration_identity(
        identity_id: str, request: CollaborationIdentityUpdate
    ) -> dict[str, Any]:
        """Authorized update path for an existing identity (FIXES.md F-003).

        Separate from creation so a session-authenticated caller can correct a display name
        or agent routing without being able to claim someone else's unused id, and so an
        unauthenticated caller can create exactly once but never silently overwrite.
        """
        try:
            if request.kind == "agent" and request.agent:
                capability = request.agent.get("capability")
                mode = request.agent.get("mode")
                if capability not in kernel.registry.capabilities():
                    raise ValueError(f"Unknown agent capability: {capability}")
                RoutingMode(mode)
            trust = "untrusted_model_output" if request.kind == "agent" else "untrusted_collaboration"
            return kernel.collaboration.update_identity(
                identity_id, request.display_name, request.kind, trust, request.agent
            ).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/collaboration/rooms")
    async def collaboration_rooms() -> dict[str, Any]:
        return {"rooms": kernel.collaboration.rooms()}

    @app.post("/collaboration/rooms", status_code=201, dependencies=[Depends(require_session)])
    async def create_collaboration_room(request: CollaborationRoomCreate) -> dict[str, Any]:
        collaboration_human(request.owner_id)
        try:
            return kernel.collaboration.create_room(
                request.id, request.name, request.purpose, request.owner_id
            ).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/collaboration/rooms/{room_id}/members/{identity_id}",
        status_code=204,
        dependencies=[Depends(require_session)],
    )
    async def add_collaboration_member(
        room_id: str, identity_id: str, request: CollaborationMembershipCreate
    ) -> None:
        # FIXES.md F-002: this endpoint previously had no caller check at all. The
        # requester must be an authenticated human identity who already belongs to the
        # room; membership is the only authorization the collaboration plane has, so
        # granting it must not itself be unauthorized.
        collaboration_human(request.requester_id)
        try:
            kernel.collaboration.add_member(
                room_id, identity_id, requester_id=request.requester_id
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/collaboration/rooms/{room_id}/events")
    async def collaboration_events(room_id: str, limit: int = 100) -> dict[str, Any]:
        try:
            return {
                "events": [
                    item.model_dump() for item in kernel.collaboration.events(room_id, limit)
                ]
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/collaboration/rooms/{room_id}/messages", status_code=202, dependencies=[Depends(require_session)])
    async def post_collaboration_message(
        room_id: str, request: CollaborationMessageCreate
    ) -> dict[str, Any]:
        collaboration_human(request.actor_id)
        try:
            event, dispatches = kernel.collaboration.post_message(
                room_id,
                request.actor_id,
                request.content,
                parent_event_id=request.parent_event_id,
                dispatch_mentions=request.dispatch_mentions,
            )
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        jobs = []
        for dispatch in dispatches:
            submission = JobSubmission(
                kind="chat",
                payload={
                    "request": {
                        "capability": dispatch.capability,
                        "mode": RoutingMode(dispatch.mode),
                        "metadata": {
                            "source": "collaboration_room",
                            "room_id": room_id,
                            "event_id": event.event_id,
                            "trust": "untrusted_collaboration",
                        },
                    },
                    "messages": dispatch.messages,
                    "model_overrides": {},
                },
                metadata={
                    "collaboration": {
                        "room_id": room_id,
                        "source_event_id": event.event_id,
                        "agent_id": dispatch.agent_id,
                    }
                },
            )
            jobs.append(enqueue_job(submission).model_dump())
        return {"event": event.model_dump(), "jobs": jobs}

    @app.post("/collaboration/rooms/{room_id}/reactions", status_code=201, dependencies=[Depends(require_session)])
    async def add_collaboration_reaction(
        room_id: str, request: CollaborationReactionCreate
    ) -> dict[str, Any]:
        collaboration_human(request.actor_id)
        try:
            return kernel.collaboration.add_reaction(
                room_id, request.actor_id, request.target_event_id, request.emoji
            ).model_dump()
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/collaboration/rooms/{room_id}/canvas")
    async def collaboration_canvas(room_id: str) -> dict[str, Any]:
        if kernel.collaboration.store.get_room(room_id) is None:
            raise HTTPException(status_code=404, detail="room not found")
        return kernel.collaboration.canvas(room_id)

    @app.put("/collaboration/rooms/{room_id}/canvas", dependencies=[Depends(require_session)])
    async def update_collaboration_canvas(
        room_id: str, request: CollaborationCanvasUpdate
    ) -> dict[str, Any]:
        collaboration_human(request.actor_id)
        try:
            return kernel.collaboration.update_canvas(
                room_id, request.actor_id, request.content
            ).model_dump()
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/collaboration/rooms/{room_id}/verify")
    async def verify_collaboration_room(room_id: str) -> dict[str, Any]:
        if kernel.collaboration.store.get_room(room_id) is None:
            raise HTTPException(status_code=404, detail="room not found")
        return kernel.collaboration.store.verify_chain(room_id)

    @app.get("/jobs")
    async def list_jobs(status: JobStatus | None = None, limit: int = 50) -> dict[str, Any]:
        return {"jobs": [job.model_dump() for job in kernel.jobs.list(status, limit)]}

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        record = kernel.jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        return record.model_dump()

    @app.get("/jobs/{job_id}/runs")
    async def list_job_runs(job_id: str) -> dict[str, Any]:
        """Every attempt made at this job (FIXES.md F-010) -- a retry is a new Run, not a
        rewrite of the last one, so this is the actual attempt history."""
        if kernel.jobs.get(job_id) is None:
            raise HTTPException(status_code=404, detail="job not found")
        return {"runs": [run.model_dump() for run in kernel.runs.list_for_job(job_id)]}

    @app.delete("/jobs/{job_id}", dependencies=[Depends(require_session)])
    async def cancel_job(job_id: str) -> dict[str, Any]:
        record = kernel.jobs.request_cancel(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        dispatcher.cancel(job_id)
        return record.model_dump()

    # --- Tier 5: persistent-agency (roster) domain -----------------------------------
    # docs/ARCHITECTURE.md, "Persistent agency and the roster domain". Proposing a
    # delegation never grants authority by itself -- every requested grant goes through
    # the same PolicyEngine every other action in this kernel goes through, and only
    # becomes active once policy allows it outright or a human resolves the
    # ApprovalRequest policy required. See kernel/roster.py.

    def _submit_if_present(job) -> dict[str, Any] | None:
        """RosterService creates a Job but never submits it (kernel/roster.py's own
        docstring explains why: the dispatcher is an API-layer concern). Mirrors
        enqueue_job's admission semantics for the one job a roster call may produce."""
        if job is None:
            return None
        try:
            dispatcher.submit(job)
        except QueueFullError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return job.model_dump()

    @app.post("/roster/profiles", status_code=201, dependencies=[Depends(require_session)])
    async def create_agent_profile(request: AgentProfileCreate) -> dict[str, Any]:
        from sovereign_ai.kernel.agent_profiles import AgentProfileAlreadyExists

        try:
            return kernel.roster.create_profile(
                request.id, request.display_name, request.role,
                routing_preferences=request.routing_preferences,
                memory_scopes=request.memory_scopes, budgets=request.budgets,
                authority_ceiling=request.authority_ceiling, metadata=request.metadata,
            ).model_dump()
        except AgentProfileAlreadyExists as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/roster/profiles")
    async def list_agent_profiles() -> dict[str, Any]:
        return {"profiles": [p.model_dump() for p in kernel.agent_profiles.list()]}

    @app.get("/roster/profiles/{profile_id}")
    async def get_agent_profile(profile_id: str) -> dict[str, Any]:
        profile = kernel.agent_profiles.get(profile_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="agent profile not found")
        return profile.model_dump()

    @app.put(
        "/roster/profiles/{profile_id}/status", dependencies=[Depends(require_session)]
    )
    async def set_agent_profile_status(
        profile_id: str, request: AgentProfileStatusUpdate
    ) -> dict[str, Any]:
        try:
            return kernel.agent_profiles.set_status(profile_id, request.status).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/roster/delegations", status_code=201, dependencies=[Depends(require_session)])
    async def propose_delegation(request: DelegationCreate) -> dict[str, Any]:
        try:
            delegation, job = kernel.roster.propose_delegation(
                request.parent_subject_id, request.objective, request.requested_grants,
                job_kind=request.job_kind, inputs=request.inputs,
                expected_artifacts=request.expected_artifacts,
                acceptance_tests=request.acceptance_tests, deadline=request.deadline,
                budget=request.budget,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"delegation": delegation.model_dump(), "job": _submit_if_present(job)}

    @app.get("/roster/delegations/{delegation_id}")
    async def get_delegation(delegation_id: str) -> dict[str, Any]:
        delegation = kernel.delegations.get(delegation_id)
        if delegation is None:
            raise HTTPException(status_code=404, detail="delegation not found")
        return delegation.model_dump()

    @app.get("/roster/delegations")
    async def list_delegations(parent_subject_id: str) -> dict[str, Any]:
        return {
            "delegations": [
                d.model_dump() for d in kernel.delegations.list_for_subject(parent_subject_id)
            ]
        }

    @app.get("/roster/approvals")
    async def list_pending_approvals() -> dict[str, Any]:
        return {"approvals": [a.model_dump() for a in kernel.approvals.list_pending()]}

    @app.post(
        "/roster/approvals/{approval_id}/resolve", dependencies=[Depends(require_session)]
    )
    async def resolve_approval(approval_id: str, request: ApprovalResolve) -> dict[str, Any]:
        try:
            approval, job = kernel.roster.resolve_approval(
                approval_id, request.resolver_id, request.approved, request.reason
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"approval": approval.model_dump(), "job": _submit_if_present(job)}

    @app.get("/roster/grants")
    async def list_active_grants(subject_id: str) -> dict[str, Any]:
        return {
            "grants": [g.model_dump() for g in kernel.capability_grants.active_for_subject(subject_id)]
        }

    @app.get("/roster/presence/{subject_id}")
    async def get_presence(subject_id: str) -> dict[str, Any]:
        """Derived from active grants/leases/jobs, never self-asserted (FIXES.md Tier 5)."""
        return kernel.presence.compute(subject_id).model_dump()

    @app.get("/collaboration/identities/{identity_id}/mailbox")
    async def get_mailbox(identity_id: str, limit: int = 200) -> dict[str, Any]:
        """A read-model over the existing event chain, not a second mutable queue
        (FIXES.md Tier 5): inbox is events mentioning this identity, outbox is events it
        authored, both drawn only from rooms it currently belongs to."""
        try:
            mailbox = kernel.collaboration.mailbox(identity_id, limit)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "inbox": [event.model_dump() for event in mailbox["inbox"]],
            "outbox": [event.model_dump() for event in mailbox["outbox"]],
        }

    @app.post("/workspaces/leases", status_code=201, dependencies=[Depends(require_session)])
    async def acquire_workspace_lease(request: WorkspaceLeaseCreate) -> dict[str, Any]:
        """A lease layers on top of the existing WorkspaceRegistry allow-list, never
        replaces it (FIXES.md Tier 5): the root must already be approved before a
        run-scoped, time-bounded lease can be acquired on it."""
        try:
            kernel.workspaces.require(Path(request.path), require_write=request.writable)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        lease = kernel.workspace_leases.try_acquire(
            request.path, request.subject_id, request.writable, request.ttl_seconds
        )
        if lease is None:
            raise HTTPException(
                status_code=409, detail=f"workspace lease already held on {request.path}"
            )
        return lease.model_dump()

    @app.delete("/workspaces/leases/{lease_id}", dependencies=[Depends(require_session)])
    async def release_workspace_lease(lease_id: str) -> None:
        kernel.workspace_leases.release(lease_id)

    # --- Tier 5 continued: workflow DAGs -----------------------------------------------

    @app.post("/workflows/definitions", status_code=201, dependencies=[Depends(require_session)])
    async def create_workflow_definition(request: WorkflowDefinitionCreate) -> dict[str, Any]:
        from sovereign_ai.kernel.workflows import WorkflowValidationError

        try:
            return kernel.workflows.create_definition(
                request.name, [step.model_dump() for step in request.steps]
            ).model_dump()
        except WorkflowValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/workflows/definitions/{definition_id}")
    async def get_workflow_definition(definition_id: str) -> dict[str, Any]:
        definition = kernel.workflow_definitions.get(definition_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="workflow definition not found")
        return definition.model_dump()

    @app.get("/workflows/definitions/by-name/{name}")
    async def list_workflow_definition_versions(name: str) -> dict[str, Any]:
        return {"versions": [d.model_dump() for d in kernel.workflow_definitions.list_versions(name)]}

    @app.post(
        "/workflows/definitions/{definition_id}/start",
        status_code=201,
        dependencies=[Depends(require_session)],
    )
    async def start_workflow(definition_id: str) -> dict[str, Any]:
        try:
            instance, jobs = kernel.workflows.start(definition_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        submitted = []
        for job in jobs:
            try:
                dispatcher.submit(job)
            except QueueFullError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            submitted.append(job.model_dump())
        return {"instance": instance.model_dump(), "jobs": submitted}

    @app.get("/workflows/instances/{instance_id}")
    async def get_workflow_instance(instance_id: str) -> dict[str, Any]:
        instance = kernel.workflow_instances.get(instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="workflow instance not found")
        return instance.model_dump()

    @app.get("/workflows/definitions/{definition_id}/instances")
    async def list_workflow_instances(definition_id: str) -> dict[str, Any]:
        return {
            "instances": [
                i.model_dump() for i in kernel.workflow_instances.list_for_definition(definition_id)
            ]
        }

    @app.post("/workflows/triggers", status_code=201, dependencies=[Depends(require_session)])
    async def create_recurring_trigger(request: RecurringTriggerCreate) -> dict[str, Any]:
        if kernel.workflow_definitions.get(request.workflow_definition_id) is None:
            raise HTTPException(status_code=404, detail="workflow definition not found")
        try:
            return kernel.triggers.create(
                request.workflow_definition_id, request.interval_seconds, enabled=request.enabled
            ).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/workflows/triggers")
    async def list_recurring_triggers() -> dict[str, Any]:
        return {"triggers": [t.model_dump() for t in kernel.triggers.list()]}

    @app.put(
        "/workflows/triggers/{trigger_id}/enabled", dependencies=[Depends(require_session)]
    )
    async def set_recurring_trigger_enabled(
        trigger_id: str, request: RecurringTriggerEnabledUpdate
    ) -> dict[str, Any]:
        try:
            return kernel.triggers.set_enabled(trigger_id, request.enabled).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # --- Tier 5 continued: skill-candidate evaluation/promotion pipeline --------------

    @app.post("/skills/candidates", status_code=201, dependencies=[Depends(require_session)])
    async def propose_skill_candidate(request: SkillCandidateCreate) -> dict[str, Any]:
        try:
            return kernel.skills.propose_from_run(
                request.run_id, request.objective, request.proposed_by
            ).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/skills/candidates")
    async def list_skill_candidates(status: CandidateStatus | None = None) -> dict[str, Any]:
        return {"candidates": [c.model_dump() for c in kernel.skill_candidates.list(status)]}

    @app.get("/skills/candidates/{candidate_id}")
    async def get_skill_candidate(candidate_id: str) -> dict[str, Any]:
        candidate = kernel.skill_candidates.get(candidate_id)
        if candidate is None:
            raise HTTPException(status_code=404, detail="skill candidate not found")
        return candidate.model_dump()

    @app.post(
        "/skills/candidates/{candidate_id}/evaluations",
        status_code=201,
        dependencies=[Depends(require_session)],
    )
    async def record_agent_evaluation(
        candidate_id: str, request: AgentEvaluationCreate
    ) -> dict[str, Any]:
        try:
            return kernel.skills.record_evaluation(
                candidate_id, request.verdict, request.evaluated_by, evidence=request.evidence
            ).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/skills/candidates/{candidate_id}/evaluations")
    async def list_agent_evaluations(candidate_id: str) -> dict[str, Any]:
        return {
            "evaluations": [
                e.model_dump() for e in kernel.agent_evaluations.list_for_candidate(candidate_id)
            ]
        }

    @app.post(
        "/skills/candidates/{candidate_id}/promote",
        status_code=201,
        dependencies=[Depends(require_session)],
    )
    async def promote_skill_candidate(
        candidate_id: str, request: SkillPromoteRequest
    ) -> dict[str, Any]:
        from sovereign_ai.kernel.skills import SkillPromotionError

        try:
            return kernel.skills.promote(candidate_id, request.name, request.promoted_by).model_dump()
        except SkillPromotionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/skills/candidates/{candidate_id}/reject",
        dependencies=[Depends(require_session)],
    )
    async def reject_skill_candidate(candidate_id: str) -> dict[str, Any]:
        from sovereign_ai.kernel.skills import SkillPromotionError

        try:
            return kernel.skills.reject(candidate_id).model_dump()
        except SkillPromotionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/skills/versions/by-name/{name}")
    async def list_skill_versions(name: str) -> dict[str, Any]:
        return {"versions": [v.model_dump() for v in kernel.skill_versions.list_versions(name)]}

    @app.get("/skills/versions/{version_id}")
    async def get_skill_version(version_id: str) -> dict[str, Any]:
        version = kernel.skill_versions.get(version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="skill version not found")
        return version.model_dump()

    return app
