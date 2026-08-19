from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from sovereign_ai.kernel.policy import PolicyEngine
from sovereign_ai.kernel.types import ActionRequest, TrustLabel

from .base import ExecutionResult
from .docker import DockerBackend
from .openshell import OpenShellBackend
from .workspaces import WorkspaceRegistry


class ExecutionBroker:
    def __init__(self, policy: PolicyEngine, workspaces: WorkspaceRegistry):
        self.policy = policy
        self.workspaces = workspaces
        self.openshell = OpenShellBackend()
        self.docker = DockerBackend()

    async def run_approved(
        self,
        argv: Sequence[str],
        cwd: str | None,
        trust: TrustLabel = TrustLabel.TRUSTED_USER,
        approved: bool = False,
        mutates_state: bool = True,
    ) -> ExecutionResult:
        if cwd is None:
            raise PermissionError("Execution requires an explicit approved workspace cwd")
        canonical_cwd = str(Path(cwd).expanduser().resolve(strict=False))
        self.workspaces.require(canonical_cwd, require_write=mutates_state)

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
