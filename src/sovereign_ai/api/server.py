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


def create_app(config_root: str | None = None) -> FastAPI:
    kernel = SovereignKernel.build(config_root)
    session = SessionAuth(kernel.config.state_dir / "session.token")
    system = kernel.config.system.get("system", {})
    hosts = allowed_hosts(system.get("bind", "127.0.0.1"), int(system.get("port", 7788)))
    resources = kernel.config.system.get("resources", {})
    dispatcher = JobDispatcher(
        kernel.jobs,
        kernel.runs,
        executor=lambda job, run: job_executor.execute(kernel, job, run),
        max_concurrency=int(resources.get("max_concurrent_jobs", 4)),
        queue_max=int(resources.get("job_queue_max", 100)),
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        dispatcher.start()
        yield
        await dispatcher.shutdown()

    app = FastAPI(title="Local Sovereign AI Kernel", version="0.1.0", lifespan=lifespan)
    app.state.kernel = kernel
    app.state.dispatcher = dispatcher
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

    return app
