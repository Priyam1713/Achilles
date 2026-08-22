from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from sovereign_ai.kernel.capability_grants import CapabilityGrantStore
from sovereign_ai.kernel.policy import PolicyEngine
from sovereign_ai.kernel.types import ActionRequest, PolicyDecision, RiskLevel, TrustLabel
from sovereign_ai.resources.workspace_leases import WorkspaceLeaseStore

from .base import ExecutionResult
from .docker import DockerBackend
from .openshell import OpenShellBackend
from .workspaces import WorkspaceRegistry


class ExecutionBroker:
    def __init__(
        self,
        policy: PolicyEngine,
        workspaces: WorkspaceRegistry,
        workspace_leases: WorkspaceLeaseStore | None = None,
        capability_grants: CapabilityGrantStore | None = None,
    ):
        self.policy = policy
        self.workspaces = workspaces
        self.workspace_leases = workspace_leases
        self.capability_grants = capability_grants
        self.openshell = OpenShellBackend()
        self.docker = DockerBackend()

    def authorize(
        self,
        *,
        action: str,
        scope: str,
        description: str,
        trust: TrustLabel = TrustLabel.TRUSTED_USER,
        approved: bool = False,
        mutates_state: bool = True,
        uses_credentials: bool = False,
        subject_id: str | None = None,
        approval_message: str | None = None,
    ) -> PolicyDecision:
        """Grant-then-policy authorisation for one action, without executing anything.

        Extracted from `run_approved` (unchanged in behaviour for its original caller) so
        that the tool plane added in `knowledge/research.md` D-034 has exactly one way to
        ask "may this subject do this?". Every new tool -- writing a file, deleting one,
        generating media, writing memory, querying the web -- clears this before acting, so
        widening what an agent can *do* never widens how authority is *decided*.

        The precedence is the same one F-036/F-037 established for execution: a real,
        unexpired, unrevoked `CapabilityGrant` naming exactly this action and scope already
        cleared policy when it was issued, and is honoured directly. Otherwise
        `PolicyEngine` decides, and for untrusted-sourced mutations its untrusted-content
        gate can never return allowed -- which is why an agent cannot write a file without
        either a grant or a human approval, and is the intended default rather than an
        oversight.

        Raises `PermissionError` on denial. Returns the `PolicyDecision` on success so a
        caller can see the required verifier.
        """
        grant_authorized = bool(
            subject_id
            and self.capability_grants is not None
            and self.capability_grants.is_active(subject_id, action, scope)
        )
        if grant_authorized:
            return PolicyDecision(
                allowed=True,
                approval_required=False,
                risk=RiskLevel.MEDIUM,
                reason=f"active capability grant for {action}:{scope}",
            )
        decision = self.policy.evaluate(
            ActionRequest(
                action=action,
                scope=scope,
                trust=trust,
                description=description,
                mutates_state=mutates_state,
                uses_credentials=uses_credentials,
            )
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)
        if decision.approval_required and not approved:
            raise PermissionError(
                approval_message or f"{action}:{scope} requires explicit approval"
            )
        return decision

    async def run_approved(
        self,
        argv: Sequence[str],
        cwd: str | None,
        trust: TrustLabel = TrustLabel.TRUSTED_USER,
        approved: bool = False,
        mutates_state: bool = True,
        subject_id: str | None = None,
        workspace_lease_id: str | None = None,
    ) -> ExecutionResult:
        """`subject_id`/`workspace_lease_id` are optional and, together, opt a caller into
        `WorkspaceLease` enforcement on top of the existing `WorkspaceRegistry` allow-list
        (FIXES.md Tier 5/F-034). Neither existing caller (`NativeAgentLoop`, every current
        test) passes them, so this is purely additive -- omitting both reproduces exactly
        the pre-existing behavior. Making every execution call require an active lease was
        explicitly deferred at F-031 as its own compatibility review; this keeps that
        review scoped to "opt a specific caller in," not "change the default for
        everyone."""
        if cwd is None:
            raise PermissionError("Execution requires an explicit approved workspace cwd")
        canonical_cwd = str(Path(cwd).expanduser().resolve(strict=False))
        self.workspaces.require(canonical_cwd, require_write=mutates_state)

        if workspace_lease_id is not None:
            if self.workspace_leases is None:
                raise RuntimeError(
                    "workspace_lease_id was supplied but this ExecutionBroker has no "
                    "WorkspaceLeaseStore configured"
                )
            if not subject_id:
                raise PermissionError("workspace_lease_id requires a subject_id")
            lease = self.workspace_leases.get(workspace_lease_id)
            if lease is None or lease.subject_id != subject_id:
                raise PermissionError(
                    f"workspace lease {workspace_lease_id} is not active for subject {subject_id}"
                )
            if str(Path(lease.root_path).expanduser().resolve(strict=False)) != canonical_cwd and not (
                canonical_cwd + "/"
            ).startswith(str(Path(lease.root_path).expanduser().resolve(strict=False)) + "/"):
                raise PermissionError(
                    f"workspace lease {workspace_lease_id} covers {lease.root_path}, not {canonical_cwd}"
                )
            if mutates_state and not lease.writable:
                raise PermissionError(f"workspace lease {workspace_lease_id} is read-only")

        # FIXES.md F-036/F-037: a subject holding an active CapabilityGrant for exactly
        # this action/scope has *already* cleared policy -- RosterService only ever
        # issues one after PolicyEngine.evaluate() allowed it outright, or after a human
        # resolved the ApprovalRequest policy demanded. Re-running PolicyEngine here would
        # re-derive a decision that was already made and already expires on its own
        # (CapabilityGrantStore.is_active checks TTL and revocation), and for untrusted-
        # sourced execute/credential/delete/network_post actions PolicyEngine's own
        # untrusted-content gate can *never* return allowed=True (see F-036) -- without
        # this check, a grant issued for exactly this purpose could never actually
        # authorize anything, making the whole roster/approval pipeline inert for
        # execution. `subject_id` alone is not enough to skip policy: only a real,
        # unexpired, unrevoked grant naming this exact action and scope does.
        self.authorize(
            action="execute",
            scope="workspace",
            description=" ".join(argv),
            trust=trust,
            approved=approved,
            mutates_state=mutates_state,
            subject_id=subject_id,
            approval_message="Execution requires explicit approval",
        )
        if self.openshell.available():
            return await self.openshell.run(argv, canonical_cwd, sync_back=mutates_state)
        if self.docker.available():
            return await self.docker.run(argv, canonical_cwd, sync_back=mutates_state)
        raise RuntimeError("No hardened execution backend available")
