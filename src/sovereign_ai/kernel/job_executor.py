from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from sovereign_ai.kernel.types import CapabilityRequest

from .jobs import JobRecord
from .runs import RunRecord

if TYPE_CHECKING:
    from sovereign_ai.kernel.app import SovereignKernel


class ChatPayload(BaseModel):
    request: CapabilityRequest
    messages: list[dict[str, Any]]
    model_overrides: dict[str, Any] = Field(default_factory=dict)


class SpecialistPayload(BaseModel):
    request: CapabilityRequest
    operation: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    timeout_s: float = 300.0


class MediaPayload(BaseModel):
    request: CapabilityRequest
    settings: dict[str, Any]
    timeout_s: float | None = None


class AgentPayload(BaseModel):
    task: str
    workspace: str | None = None
    capability: str = "coding"
    mode: str = "smart"
    max_steps: int = 10
    approved: bool = False


def _assistant_content(result: dict[str, Any]) -> str:
    payload = result.get("result") or {}
    choices = payload.get("choices") or []
    if choices:
        content = (choices[0].get("message") or {}).get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return "The model completed the job, but its backend returned no displayable text."


async def execute(kernel: SovereignKernel, job: JobRecord, run: RunRecord) -> dict[str, Any]:
    """What a job attempt actually does, independent of how it was submitted.

    Owned by the kernel (not the API layer) because "route a chat/specialist/media
    request and post the collaboration reply" is kernel business logic, not HTTP plumbing.
    `JobDispatcher` calls this once per `Run` attempt; on success or failure it also posts
    the collaboration-room reply the request originated from, if any.
    """
    try:
        if job.kind == "chat":
            payload = ChatPayload.model_validate(job.request)
            result = await kernel.inference.chat(
                payload.request, payload.messages, payload.model_overrides
            )
        elif job.kind == "specialist":
            specialist_payload = SpecialistPayload.model_validate(job.request)
            result = await kernel.specialists.invoke(
                specialist_payload.request,
                specialist_payload.operation,
                specialist_payload.inputs,
                specialist_payload.options,
                specialist_payload.timeout_s,
            )
        elif job.kind == "media":
            media_payload = MediaPayload.model_validate(job.request)
            result = await kernel.media.generate(
                media_payload.request, media_payload.settings, media_payload.timeout_s
            )
        else:
            result = await _run_agent_loop(kernel, job, run)
    except Exception as exc:
        # The dispatcher records the Job/Run failure itself from this re-raised exception;
        # this side effect only needs to notify the room that asked, and must not swallow
        # the original error.
        await post_failure(kernel, job, f"{type(exc).__name__}: {exc}")
        raise

    origin = job.metadata.get("collaboration")
    if origin:
        try:
            kernel.collaboration.post_job_result(
                origin["room_id"], origin["agent_id"], origin["source_event_id"],
                job.id, _assistant_content(result),
            )
        except Exception as exc:
            kernel.events.append(
                stream_id=f"job:{job.id}",
                event_type="collaboration.reply_failed",
                payload={"error": f"{type(exc).__name__}: {exc}"},
            )
    return result


async def _run_agent_loop(kernel: SovereignKernel, job: JobRecord, run: RunRecord) -> dict[str, Any]:
    """Drive `kernel.agent_loops.get("native")` (or another registered loop, via
    `job.request["loop"]`) to completion for one job attempt.

    One `Run` = one full attempt of the task, from first step to `done`/budget-exhausted/
    error. Every individual step is already recorded as a kernel event by the loop itself
    (see `agents/native_loop.py`); this only needs to accumulate the step history into the
    Run's own result so `GET /jobs/{id}/runs` shows a complete picture without a second
    round trip to the event store.
    """
    payload = AgentPayload.model_validate(job.request)
    loop_name = job.request.get("loop", "native")
    loop = kernel.agent_loops.get(loop_name)
    state: dict[str, Any] = {
        "run_id": run.id,
        "task": payload.task,
        "workspace": payload.workspace,
        "capability": payload.capability,
        "mode": payload.mode,
        "max_steps": payload.max_steps,
        "approved": payload.approved,
    }
    steps: list[dict[str, Any]] = []
    while True:
        step = await loop.next_step(state)
        steps.append({"kind": step.kind, "payload": step.payload, "notes": step.notes})
        if step.done:
            return {"steps": steps, "final": step.payload}


async def post_failure(kernel: SovereignKernel, job: JobRecord, error: str) -> None:
    """Best-effort collaboration-room notification for a failed job.

    The dispatcher records the failure on the Job/Run rows itself; this only handles the
    "tell the room that asked" side effect, and must never raise into the dispatcher.
    """
    origin = job.metadata.get("collaboration")
    if not origin:
        return
    try:
        kernel.collaboration.post_job_failure(origin["room_id"], origin["source_event_id"], job.id, error)
    except Exception:
        pass
