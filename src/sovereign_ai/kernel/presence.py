from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field

from sovereign_ai.resources.workspace_leases import WorkspaceLeaseStore

from .capability_grants import CapabilityGrantStore
from .delegations import DelegationStore
from .jobs import JobStore

PresenceState = Literal["active", "idle"]


class PresenceRecord(BaseModel):
    subject_id: str
    state: PresenceState
    active_grants: int
    active_workspace_leases: int
    running_job_ids: list[str] = Field(default_factory=list)
    checked_at: float


class PresenceService:
    """Presence is derived from active leases and run state, never self-asserted by a
    model (docs/ARCHITECTURE.md, "Persistent agency and the roster domain";
    `knowledge/research.md`'s minimal implementation sequence, step 2: "active leases,
    run state and health checks determine presence"; and the same document's verdict item
    5, "escalation cannot trust raw model confidence" -- the same principle applied to
    presence: a subject cannot claim to be busy, it either holds an active grant/lease or
    it does not).

    A subject with no active grant, no active workspace lease and no job currently
    queued or running is `idle` -- there is nothing else presence could mean here, since
    this kernel has no separate liveness signal (heartbeat, socket, process) for a logical
    `AgentProfile`, only for the concrete leases and jobs a run acting for it currently
    holds.
    """

    def __init__(
        self,
        grants: CapabilityGrantStore,
        workspace_leases: WorkspaceLeaseStore,
        delegations: DelegationStore,
        jobs: JobStore,
    ):
        self.grants = grants
        self.workspace_leases = workspace_leases
        self.delegations = delegations
        self.jobs = jobs

    def compute(self, subject_id: str) -> PresenceRecord:
        active_grants = len(self.grants.active_for_subject(subject_id))
        active_leases = len(self.workspace_leases.active_for_subject(subject_id))

        running_job_ids: list[str] = []
        for delegation in self.delegations.list_for_subject(subject_id):
            if not delegation.child_job_id:
                continue
            job = self.jobs.get(delegation.child_job_id)
            if job is not None and job.status in ("queued", "running"):
                running_job_ids.append(job.id)

        active = bool(active_grants or active_leases or running_job_ids)
        return PresenceRecord(
            subject_id=subject_id,
            state="active" if active else "idle",
            active_grants=active_grants,
            active_workspace_leases=active_leases,
            running_job_ids=running_job_ids,
            checked_at=time.time(),
        )
