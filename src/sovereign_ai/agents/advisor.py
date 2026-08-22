from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sovereign_ai.inference.content import extract_message_content
from sovereign_ai.kernel.types import CapabilityRequest, RoutingMode

ADVISOR_PROMPT = """You are reviewing one proposed action by another agent, before it runs.

The task the agent was given:
{task}

The action it proposes:
{action}

Reply with EXACTLY ONE JSON object and nothing else:
  {{"severity": "none" | "note" | "stop", "concern": "<one short sentence>"}}

Use "stop" only when the action is clearly destructive, clearly outside the stated task, or
clearly about to lose work. Use "note" for a real but survivable concern. Use "none" when
the action is a reasonable next step. Most actions are "none"."""

_SEVERITIES = ("none", "note", "stop")


@dataclass
class AdvisorVerdict:
    severity: str
    concern: str

    @property
    def blocks(self) -> bool:
        return self.severity == "stop"


class Advisor:
    """A second, cheaper model that reviews each proposed action before it runs.

    Adapted from oh-my-pi's `advisor` role (`knowledge/harness-research.md`), which is also
    what research wave 7 called a classifier pre-screen: this machine runs a 49.57 tok/s
    fast brain that sits idle while the 6.36 tok/s deep brain thinks, and a review from the
    cheap model is nearly free *relative to the expensive one*.

    **It is not a security boundary, and must never be mistaken for one.** The advisor is a
    language model, so its output is untrusted exactly like the planner's. The only power it
    has is to *add* an objection: a `stop` verdict turns into a refused observation the
    planner must reason about. It can never approve anything, never widen a
    `CapabilityGrant`, and never substitute for `PolicyEngine` — an action it says nothing
    about is still judged by policy, and an action policy refuses stays refused however
    enthusiastic the advisor was. Friction only, in one direction.

    Off by default. It costs one extra generation per turn, which is cheap when the planner
    is the deep brain and roughly a doubling when planner and advisor are the same fast
    model — so enabling it is a decision about *which* brains are in play, not a free win.
    """

    def __init__(
        self,
        inference: Any,
        capability: str = "orchestration_fast",
        mode: str = "fast",
        timeout_severity: str = "none",
    ):
        self.inference = inference
        self.capability = capability
        self.mode = mode
        # What to assume when the advisor itself fails. "none" by design: a broken reviewer
        # must not become an outage for the thing it reviews, and it holds no authority to
        # lose. An operator wanting fail-closed review sets this to "stop" deliberately.
        self.timeout_severity = timeout_severity

    async def review(self, task: str, action: dict[str, Any]) -> AdvisorVerdict:
        prompt = ADVISOR_PROMPT.format(
            task=str(task)[:2000], action=json.dumps(action, default=str)[:2000]
        )
        request = CapabilityRequest(capability=self.capability, mode=RoutingMode(self.mode))
        try:
            result = await self.inference.chat(request, [{"role": "user", "content": prompt}])
        except Exception as exc:
            return AdvisorVerdict(
                severity=self.timeout_severity, concern=f"advisor unavailable: {exc}"
            )

        content = extract_message_content(result.get("result") or {})
        verdict = self._parse(content)
        if verdict is None:
            # An unparsable review is not an objection. Treating garbage as a stop would
            # let a confused reviewer halt work it never actually assessed.
            return AdvisorVerdict(severity="none", concern="advisor reply was unparsable")
        return verdict

    @staticmethod
    def _parse(content: str) -> AdvisorVerdict | None:
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None
        severity = str(parsed.get("severity", "none")).lower()
        if severity not in _SEVERITIES:
            severity = "none"
        return AdvisorVerdict(severity=severity, concern=str(parsed.get("concern", ""))[:400])
