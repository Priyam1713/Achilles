from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from sovereign_ai.kernel.app import SovereignKernel
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
    kind: Literal["chat", "specialist", "media"]
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


def create_app(config_root: str | None = None) -> FastAPI:
    kernel = SovereignKernel.build(config_root)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        tasks = list(application.state.job_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="Local Sovereign AI Kernel", version="0.1.0", lifespan=lifespan)
    app.state.kernel = kernel
    app.state.job_tasks = {}
    kernel.jobs.recover_interrupted()

    def assistant_content(result: dict[str, Any]) -> str:
        payload = result.get("result") or {}
        choices = payload.get("choices") or []
        if choices:
            content = (choices[0].get("message") or {}).get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        return "The model completed the job, but its backend returned no displayable text."

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

    async def execute_job(job_id: str, submission: JobSubmission) -> None:
        kernel.jobs.mark_running(job_id)
        try:
            if submission.kind == "chat":
                request = ChatRequest.model_validate(submission.payload)
                result = await kernel.inference.chat(
                    request.request, request.messages, request.model_overrides
                )
            elif submission.kind == "specialist":
                request = SpecialistRequest.model_validate(submission.payload)
                result = await kernel.specialists.invoke(
                    request.request,
                    request.operation,
                    request.inputs,
                    request.options,
                    request.timeout_s,
                )
            else:
                request = MediaRequest.model_validate(submission.payload)
                result = await kernel.media.generate(
                    request.request, request.settings, request.timeout_s
                )
            kernel.jobs.finish(job_id, "succeeded", result=result)
            origin = submission.metadata.get("collaboration")
            if origin:
                try:
                    kernel.collaboration.post_job_result(
                        origin["room_id"],
                        origin["agent_id"],
                        origin["source_event_id"],
                        job_id,
                        assistant_content(result),
                    )
                except Exception as exc:
                    kernel.events.append(
                        stream_id=f"job:{job_id}",
                        event_type="collaboration.reply_failed",
                        payload={"error": f"{type(exc).__name__}: {exc}"},
                    )
        except asyncio.CancelledError:
            kernel.jobs.finish(job_id, "cancelled", error="cancelled by user")
            raise
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            kernel.jobs.finish(job_id, "failed", error=error)
            origin = submission.metadata.get("collaboration")
            if origin:
                try:
                    kernel.collaboration.post_job_failure(
                        origin["room_id"], origin["source_event_id"], job_id, error
                    )
                except Exception:
                    pass
        finally:
            app.state.job_tasks.pop(job_id, None)

    def enqueue_job(submission: JobSubmission):
        record = kernel.jobs.create(submission.kind, submission.payload, submission.metadata)
        task = asyncio.create_task(execute_job(record.id, submission), name=f"soai-job-{record.id}")
        app.state.job_tasks[record.id] = task
        return record

    @app.get("/ui", include_in_schema=False)
    async def ui():
        path = Path("web/index.html").resolve()
        if not path.exists():
            raise HTTPException(status_code=404, detail="UI not found")
        return FileResponse(path)

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
            "jobs": {"running": len(active_jobs), "queued": len(queued_jobs)},
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

    @app.post("/route")
    async def route(req: CapabilityRequest) -> dict[str, Any]:
        return kernel.scheduler.route(req).model_dump()

    @app.post("/policy/evaluate")
    async def policy(req: ActionRequest) -> dict[str, Any]:
        return kernel.policy.evaluate(req).model_dump()

    @app.post("/chat")
    async def chat(req: ChatRequest) -> dict[str, Any]:
        try:
            return await kernel.inference.chat(req.request, req.messages, req.model_overrides)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/specialist/invoke")
    async def specialist_invoke(req: SpecialistRequest) -> dict[str, Any]:
        try:
            return await kernel.specialists.invoke(
                req.request, req.operation, req.inputs, req.options, req.timeout_s
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/media/generate")
    async def media_generate(req: MediaRequest) -> dict[str, Any]:
        try:
            return await kernel.media.generate(req.request, req.settings, req.timeout_s)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/jobs", status_code=202)
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

    @app.post("/collaboration/identities", status_code=201)
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
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/collaboration/rooms")
    async def collaboration_rooms() -> dict[str, Any]:
        return {"rooms": kernel.collaboration.rooms()}

    @app.post("/collaboration/rooms", status_code=201)
    async def create_collaboration_room(request: CollaborationRoomCreate) -> dict[str, Any]:
        collaboration_human(request.owner_id)
        try:
            return kernel.collaboration.create_room(
                request.id, request.name, request.purpose, request.owner_id
            ).model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/collaboration/rooms/{room_id}/members/{identity_id}", status_code=204)
    async def add_collaboration_member(room_id: str, identity_id: str) -> None:
        try:
            kernel.collaboration.add_member(room_id, identity_id)
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

    @app.post("/collaboration/rooms/{room_id}/messages", status_code=202)
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

    @app.post("/collaboration/rooms/{room_id}/reactions", status_code=201)
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

    @app.put("/collaboration/rooms/{room_id}/canvas")
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

    @app.delete("/jobs/{job_id}")
    async def cancel_job(job_id: str) -> dict[str, Any]:
        record = kernel.jobs.request_cancel(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="job not found")
        task = app.state.job_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
        return record.model_dump()

    return app
