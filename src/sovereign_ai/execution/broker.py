from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from sovereign_ai.kernel.policy import PolicyEngine
from sovereign_ai.kernel.types import ActionRequest, TrustLabel
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
    ):
        self.policy = policy
        self.workspaces = workspaces
        self.workspace_leases = workspace_leases
        self.openshell = OpenShellBackend()
        self.docker = DockerBackend()

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

        req = ActionRequest(
            action="execute",
            scope="workspace",
            trust=trust,
            description=" ".join(argv),
            mutates_state=mutates_state,
        )
        decision = self.policy.evaluate(req)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        if decision.approval_required and not approved:
            raise PermissionError("Execution requires explicit approval")
        if self.openshell.available():
            return await self.openshell.run(argv, canonical_cwd, sync_back=mutates_state)
        if self.docker.available():
            return await self.docker.run(argv, canonical_cwd, sync_back=mutates_state)
        raise RuntimeError("No hardened execution backend available")
