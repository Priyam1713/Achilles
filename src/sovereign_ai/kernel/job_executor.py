from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from sovereign_ai.inference.content import extract_message_content
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
    # FIXES.md Tier 5/F-035: which AgentProfile this run is acting for, if any. Optional
    # and unused by default -- an agent job submitted the ordinary way (no delegation
    # involved) still has no profile, exactly as before this field existed. A delegation-
    # spawned job (RosterService.propose_delegation/resolve_approval) is the intended
    # source of a real value here. Recorded on the Run for free: JobDispatcher.submit()
    # already snapshots the whole job.request onto the new Run, so this becomes
    # Run.request["agent_profile_id"] with no dispatcher change. workspace_lease_id opts
    # this run's run_command calls into WorkspaceLease enforcement (F-034); omitting it
    # keeps today's behavior (WorkspaceRegistry-only) unchanged.
    agent_profile_id: str | None = None
    workspace_lease_id: str | None = None


def _assistant_content(result: dict[str, Any]) -> str:
    content = extract_message_content(result.get("result") or {})
    return content or "The model completed the job, but its backend returned no displayable text."


async def execute(
    kernel: SovereignKernel,
    job: JobRecord,
    run: RunRecord,
    submit_callback: Callable[[JobRecord], Any] | None = None,
) -> dict[str, Any]:
    """What a job attempt actually does, independent of how it was submitted.

    Owned by the kernel (not the API layer) because "route a chat/specialist/media
    request and post the collaboration reply" is kernel business logic, not HTTP plumbing.
    `JobDispatcher` calls this once per `Run` attempt; on success or failure it also posts
    the collaboration-room reply the request originated from, if any, and -- if this job
    belongs to a `WorkflowInstance` (`FIXES.md` Tier 5) -- advances that workflow and
    submits whatever step(s) just became ready.

    `submit_callback` is how a workflow's downstream step actually gets to run: this
    function creates the new `Job` row (via `WorkflowService.advance`) but, like
    `RosterService`, does not own a `JobDispatcher` reference itself -- the dispatcher is
    an API-layer concern, constructed per FastAPI app, not part of `SovereignKernel`. The
    caller that *does* own one (`api/server.py`'s `create_app`) passes its own
    `dispatcher.submit` in. Omitting it (any test that constructs a bare `execute()` call)
    still creates the correct `Job` row and updates the workflow instance; it just isn't
    auto-dispatched, which is the same graceful degradation `RosterService`'s callers
    already have to handle for delegation-spawned jobs.
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
        # these side effects only need to notify whoever's waiting, and must not swallow
        # the original error.
        await post_failure(kernel, job, f"{type(exc).__name__}: {exc}")
        _advance_workflow_best_effort(
            kernel, job, "failed", error=f"{type(exc).__name__}: {exc}", submit_callback=submit_callback
        )
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
    _advance_workflow_best_effort(kernel, job, "succeeded", result=result, submit_callback=submit_callback)
    return result


def _advance_workflow_best_effort(
    kernel: SovereignKernel,
    job: JobRecord,
    status: str,
    *,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    submit_callback: Callable[[JobRecord], Any] | None,
) -> None:
    """Advance the `WorkflowInstance` this job's step belongs to, if any. Mirrors
    `post_failure`'s contract: best-effort, must never raise into the dispatcher -- a
    workflow bookkeeping failure must not turn a job that actually succeeded (or failed
    for its own real reason) into something else."""
    workflow = job.metadata.get("workflow")
    if not workflow:
        return
    try:
        _, new_jobs = kernel.workflows.advance(
            workflow["instance_id"], workflow["step_id"], status, result=result, error=error
        )
        if submit_callback is not None:
            for new_job in new_jobs:
                submit_callback(new_job)
    except Exception as exc:
        kernel.events.append(
            stream_id=f"job:{job.id}",
            event_type="workflow.advance_failed",
            payload={"error": f"{type(exc).__name__}: {exc}"},
        )


async def _run_agent_loop(kernel: SovereignKernel, job: JobRecord, run: RunRecord) -> dict[str, Any]:
    """Drive the configured default loop (or another registered loop, via
    `job.request["loop"]`) to completion for one job attempt.

    One `Run` = one full attempt of the task, from first step to `done`/budget-exhausted/
    error. Every individual step is already recorded as a kernel event by the loop itself
    (see `agents/native_loop.py`); this only needs to accumulate the step history into the
    Run's own result so `GET /jobs/{id}/runs` shows a complete picture without a second
    round trip to the event store.
    """
    payload = AgentPayload.model_validate(job.request)
    loop_name = job.request.get("loop") or kernel.agent_loops.default_name
    loop = kernel.agent_loops.get(loop_name)
    state: dict[str, Any] = {
        "run_id": run.id,
        "task": payload.task,
        "workspace": payload.workspace,
        "capability": payload.capability,
        "mode": payload.mode,
        "max_steps": payload.max_steps,
        "approved": payload.approved,
        "agent_profile_id": payload.agent_profile_id,
        "workspace_lease_id": payload.workspace_lease_id,
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
