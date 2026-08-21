from __future__ import annotations

from typing import Any

from .jobs import JobRecord, JobStore
from .workflows import (
    WorkflowDefinitionRecord,
    WorkflowDefinitionStore,
    WorkflowInstanceRecord,
    WorkflowInstanceStore,
    WorkflowStep,
)


class WorkflowService:
    """Drives one `WorkflowDefinition` DAG forward as its steps' jobs complete
    (docs/ARCHITECTURE.md's object-boundary table; `knowledge/research.md`'s "Build the
    minimal kernel DAG only after `Run` and delegation semantics exist" -- Tier 5).

    Like `RosterService`, deliberately does not submit `Job`s to the `JobDispatcher`
    itself: the dispatcher is an API-layer concern, so this stays synchronous and
    unit-testable without a running event loop. `start()`/`advance()` create the durable
    `Job` rows for whichever steps just became ready and return them; the caller (the API
    layer, or `job_executor.execute()`'s own completion hook for `advance()`) submits
    them the same way `enqueue_job` already does for every other job.

    A step is "ready" once every step it `depends_on` has succeeded. Any step failing
    fails the whole instance -- no partial-success/best-effort semantics in this first
    pass; a workflow either completes in full or does not complete.
    """

    def __init__(
        self,
        definitions: WorkflowDefinitionStore,
        instances: WorkflowInstanceStore,
        jobs: JobStore,
    ):
        self.definitions = definitions
        self.instances = instances
        self.jobs = jobs

    def create_definition(self, name: str, steps: list[dict[str, Any]]) -> WorkflowDefinitionRecord:
        return self.definitions.create(name, [WorkflowStep(**step) for step in steps])

    def _job_for_step(
        self, instance_id: str, definition: WorkflowDefinitionRecord, step: WorkflowStep
    ) -> JobRecord:
        return self.jobs.create(
            step.job_kind,
            step.request_template,
            metadata={"workflow": {"instance_id": instance_id, "step_id": step.id}},
        )

    def start(self, definition_id: str) -> tuple[WorkflowInstanceRecord, list[JobRecord]]:
        definition = self.definitions.get(definition_id)
        if definition is None:
            raise ValueError(f"Unknown workflow definition: {definition_id}")

        step_states: dict[str, dict[str, Any]] = {
            step.id: {"status": "pending", "job_id": None} for step in definition.steps
        }
        instance = self.instances.create(definition_id, step_states)

        jobs: list[JobRecord] = []
        for step in definition.steps:
            if not step.depends_on:
                job = self._job_for_step(instance.id, definition, step)
                step_states[step.id] = {"status": "queued", "job_id": job.id}
                jobs.append(job)
        instance = self.instances.update(instance.id, "running", step_states)
        return instance, jobs

    def advance(
        self,
        instance_id: str,
        step_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> tuple[WorkflowInstanceRecord, list[JobRecord]]:
        """Called once a step's job reaches a terminal state. `status` is
        `"succeeded"`/`"failed"`, matching `JobRecord.status`'s vocabulary for those two
        outcomes."""
        instance = self.instances.get(instance_id)
        if instance is None:
            raise ValueError(f"Unknown workflow instance: {instance_id}")
        if instance.status != "running":
            # Already terminal (e.g. a sibling step already failed the whole instance) --
            # nothing further to do, and re-deriving newly-ready steps from a finished
            # instance would be meaningless.
            return instance, []

        definition = self.definitions.get(instance.definition_id)
        if definition is None:
            raise ValueError(f"Unknown workflow definition: {instance.definition_id}")

        step_states = dict(instance.step_states)
        step_states[step_id] = {
            "status": status,
            "job_id": step_states.get(step_id, {}).get("job_id"),
            **({"error": error} if error else {}),
        }

        if status == "failed":
            instance = self.instances.update(instance.id, "failed", step_states)
            return instance, []

        succeeded = {sid for sid, state in step_states.items() if state["status"] == "succeeded"}
        new_jobs: list[JobRecord] = []
        for step in definition.steps:
            if step_states[step.id]["status"] != "pending":
                continue
            if set(step.depends_on) <= succeeded:
                job = self._job_for_step(instance.id, definition, step)
                step_states[step.id] = {"status": "queued", "job_id": job.id}
                new_jobs.append(job)

        all_done = all(state["status"] == "succeeded" for state in step_states.values())
        new_status = "completed" if all_done else "running"
        instance = self.instances.update(instance.id, new_status, step_states)
        return instance, new_jobs
