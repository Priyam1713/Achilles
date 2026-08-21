from __future__ import annotations

from typing import Any

from .agent_profiles import AgentProfileRecord, AgentProfileStore
from .approvals import ApprovalRequestRecord, ApprovalRequestStore
from .capability_grants import CapabilityGrantStore
from .delegations import DelegationRecord, DelegationStore
from .jobs import JobRecord, JobStore
from .policy import PolicyEngine
from .types import ActionRequest, TrustLabel

DEFAULT_GRANT_TTL_SECONDS = 3600.0


class RosterService:
    """Coordinates the persistent-agency domain: proposing a delegation never grants
    authority by itself; every requested grant is evaluated by the same `PolicyEngine`
    every other action in this kernel goes through, and only becomes an active
    `CapabilityGrant` once policy allows it outright or a human resolves the
    `ApprovalRequest` policy required (docs/ARCHITECTURE.md, "Persistent agency and the
    roster domain"; FIXES.md Tier 5).

    Deliberately does not construct or submit `Job`/`Run` objects to the `JobDispatcher`:
    the dispatcher is an API-layer concern (constructed per FastAPI app instance, not part
    of `SovereignKernel`) so this service stays synchronous and unit-testable without a
    running event loop. `propose_delegation`/`resolve_approval` create the durable `Job`
    row (via `JobStore.create`, exactly like any other job) once every requested grant is
    satisfied, and return it to the caller -- the API layer submits it to the dispatcher
    the same way `api/server.py`'s existing `enqueue_job` already does for every other job.
    """

    def __init__(
        self,
        profiles: AgentProfileStore,
        delegations: DelegationStore,
        grants: CapabilityGrantStore,
        approvals: ApprovalRequestStore,
        jobs: JobStore,
        policy: PolicyEngine,
    ):
        self.profiles = profiles
        self.delegations = delegations
        self.grants = grants
        self.approvals = approvals
        self.jobs = jobs
        self.policy = policy

    def create_profile(
        self,
        profile_id: str,
        display_name: str,
        role: str,
        *,
        routing_preferences: dict[str, Any] | None = None,
        memory_scopes: list[str] | None = None,
        budgets: dict[str, Any] | None = None,
        authority_ceiling: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentProfileRecord:
        return self.profiles.create(
            profile_id, display_name, role,
            routing_preferences=routing_preferences, memory_scopes=memory_scopes,
            budgets=budgets, authority_ceiling=authority_ceiling, metadata=metadata,
        )

    def propose_delegation(
        self,
        parent_subject_id: str,
        objective: str,
        requested_grants: list[dict[str, Any]],
        *,
        job_kind: str = "agent",
        inputs: dict[str, Any] | None = None,
        expected_artifacts: list[str] | None = None,
        acceptance_tests: list[str] | None = None,
        deadline: float | None = None,
        budget: dict[str, Any] | None = None,
        trust: TrustLabel = TrustLabel.UNTRUSTED_COLLABORATION,
    ) -> tuple[DelegationRecord, JobRecord | None]:
        """Propose one delegation and evaluate every requested grant against policy.

        `requested_grants` is a list of `{"action", "scope", "mutates_state"?,
        "uses_credentials"?}` dicts. An entry that omits `mutates_state`/`uses_credentials`
        is evaluated as if both were `True` -- the conservative default, matching this
        project's fail-closed policy stance, so an under-specified request never gets
        *more* lenient treatment by omission.

        A grant outside the delegating profile's `authority_ceiling` is rejected
        immediately, before spending a policy evaluation on a request that could never
        succeed even if approved.

        Returns `(delegation, job)`. `job` is non-`None` only when every requested grant
        was already active (no approval round-trip needed) -- the caller is responsible
        for submitting it to the dispatcher. Otherwise the delegation is left
        `awaiting_approval` and `resolve_approval` is what eventually produces the job.
        """
        for requested in requested_grants:
            ceiling_key = f"{requested['action']}:{requested['scope']}"
            if not self.profiles.has_ceiling(parent_subject_id, ceiling_key):
                raise PermissionError(
                    f"{parent_subject_id} has no authority ceiling covering "
                    f"'{ceiling_key}' -- cannot request a grant it could never hold"
                )

        delegation = self.delegations.create(
            parent_subject_id, objective,
            inputs=inputs, expected_artifacts=expected_artifacts,
            acceptance_tests=acceptance_tests, requested_grants=requested_grants,
            deadline=deadline, budget=budget,
        )

        all_active = True
        for requested in requested_grants:
            decision = self.policy.evaluate(
                ActionRequest(
                    action=requested["action"],
                    scope=requested["scope"],
                    trust=trust,
                    description=f"delegation {delegation.id}: {objective}",
                    mutates_state=requested.get("mutates_state", True),
                    uses_credentials=requested.get("uses_credentials", True),
                )
            )
            if decision.approval_required:
                self.approvals.create(
                    parent_subject_id, requested["action"], requested["scope"],
                    decision.risk.value, decision.reason,
                    evidence={"delegation_id": delegation.id},
                )
                all_active = False
            elif decision.allowed:
                self.grants.issue(
                    parent_subject_id, requested["action"], requested["scope"], "policy",
                    delegation_id=delegation.id, ttl_seconds=DEFAULT_GRANT_TTL_SECONDS,
                )
            else:
                # Policy refused outright with no path to approval (should not occur given
                # PolicyEngine's current rules always pair a refusal with approval_required,
                # but a future rule could add one -- treat it as a hard rejection, not a
                # silent partial grant).
                rejected = self.delegations.set_status(delegation.id, "rejected")
                return rejected, None

        if not all_active:
            return self.delegations.set_status(delegation.id, "awaiting_approval"), None

        job = self.jobs.create(job_kind, {"delegation_id": delegation.id, **(inputs or {})})
        delegation = self.delegations.set_status(delegation.id, "approved", child_job_id=job.id)
        return delegation, job

    def resolve_approval(
        self, approval_id: str, resolver_id: str, approved: bool, reason: str
    ) -> tuple[ApprovalRequestRecord, JobRecord | None]:
        """Resolve one pending approval. If it was the last one a delegation was waiting
        on and it was approved, issues the grant, creates the delegation's job and returns
        it for the caller to dispatch. A denial rejects the whole delegation -- a
        delegation with any denied requested grant does not partially proceed."""
        approval = self.approvals.resolve(approval_id, resolver_id, approved, reason)
        delegation_id = approval.evidence.get("delegation_id")
        if not delegation_id:
            return approval, None
        delegation = self.delegations.get(delegation_id)
        if delegation is None or delegation.status != "awaiting_approval":
            return approval, None

        if not approved:
            # A delegation with any denied requested grant does not partially proceed:
            # revoke any grant this same delegation already had issued for its other
            # requested actions, not just skip issuing this one.
            self.grants.revoke_for_delegation(delegation.id)
            self.delegations.set_status(delegation.id, "rejected")
            return approval, None

        self.grants.issue(
            approval.subject_id, approval.action, approval.scope, resolver_id,
            approval_request_id=approval.id, delegation_id=delegation.id,
            ttl_seconds=DEFAULT_GRANT_TTL_SECONDS,
        )

        still_pending = [
            requested
            for requested in delegation.requested_grants
            if not self.grants.is_active(
                delegation.parent_subject_id, requested["action"], requested["scope"]
            )
        ]
        if still_pending:
            return approval, None

        job = self.jobs.create(
            "agent", {"delegation_id": delegation.id, **delegation.inputs}
        )
        self.delegations.set_status(delegation.id, "approved", child_job_id=job.id)
        return approval, job
