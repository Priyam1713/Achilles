from __future__ import annotations

from .config import ConfigBundle
from .types import ActionRequest, PolicyDecision, RiskLevel, TrustLabel


class PolicyEngine:
    def __init__(self, config: ConfigBundle):
        self.config = config
        self.rules = config.policies.get("risk_rules", [])
        self.fail_closed = bool(config.policies.get("defaults", {}).get("fail_closed", True))

    def evaluate(self, req: ActionRequest) -> PolicyDecision:
        untrusted = req.trust in {
            TrustLabel.UNTRUSTED_WEB,
            TrustLabel.UNTRUSTED_EMAIL,
            TrustLabel.UNTRUSTED_DOCUMENT,
            TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            TrustLabel.UNTRUSTED_COLLABORATION,
        }
        if untrusted and (
            req.mutates_state
            or req.uses_credentials
            or req.action in {"execute", "credential", "delete", "network_post"}
        ):
            return PolicyDecision(
                allowed=False,
                approval_required=True,
                risk=RiskLevel.CRITICAL,
                reason="Untrusted content cannot directly authorize mutation or credential access.",
            )

        for rule in self.rules:
            match = rule.get("match", {})
            action_match = match.get("action") in (None, req.action)
            scope_match = match.get("scope") in (None, "any", req.scope)
            if action_match and scope_match:
                return PolicyDecision(
                    allowed=True,
                    approval_required=bool(rule.get("approval", False)),
                    risk=RiskLevel(rule.get("risk", "medium")),
                    verifier=rule.get("verify"),
                    reveal_secret_to_model=bool(rule.get("reveal_secret_to_model", False)),
                    reason=f"Matched policy rule for {req.action}:{req.scope}",
                )

        if self.fail_closed:
            return PolicyDecision(
                allowed=False,
                approval_required=True,
                risk=RiskLevel.HIGH,
                reason="No explicit allow rule matched; fail-closed policy.",
            )
        return PolicyDecision(
            allowed=True,
            approval_required=True,
            risk=RiskLevel.HIGH,
            reason="No rule matched; approval required.",
        )
