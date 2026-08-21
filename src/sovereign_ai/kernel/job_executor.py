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
        else:
            media_payload = MediaPayload.model_validate(job.request)
            result = await kernel.media.generate(
                media_payload.request, media_payload.settings, media_payload.timeout_s
            )
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
