from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

#: Event types the journal records for an agent run, and what each means when reconstructing
#: one. Anything not listed still appears in the transcript as `other`, because silently
#: dropping an event would make the replay a summary rather than a record.
_KNOWN = {
    "agent.step.tool_call": "tool_call",
    "agent.step.done": "done",
    "agent.step.unparsable": "unparsable",
    "agent.checkpoint.created": "checkpoint",
    "agent.checkpoint.failed": "checkpoint_failed",
    "agent.context.compacted": "compacted",
    "agent.decoding.degraded": "degraded",
    "agent.advisor.verdict": "advisor",
}


@dataclass
class ReplayEntry:
    """One thing that happened, with the provenance needed to judge it."""

    seq: int
    kind: str
    event_type: str
    trust: str
    payload: dict[str, Any]

    @property
    def denied(self) -> bool:
        observation = self.payload.get("observation")
        return bool(isinstance(observation, dict) and observation.get("denied"))

    def summarise(self) -> str:
        if self.kind == "tool_call":
            tool = self.payload.get("tool", "?")
            observation = self.payload.get("observation") or {}
            if observation.get("denied"):
                return f"{tool} DENIED: {observation.get('error', '')}"
            if observation.get("error"):
                return f"{tool} error: {observation.get('error')}"
            batched = " (batched)" if self.payload.get("batched") else ""
            return f"{tool}{batched}"
        if self.kind == "done":
            return f"done: {self.payload.get('summary', '')}"
        if self.kind == "checkpoint":
            return f"checkpoint {str(self.payload.get('sha', ''))[:12]} — this edit can be undone"
        if self.kind == "compacted":
            return f"context compacted: {self.payload.get('elided_turns')} steps elided"
        if self.kind == "advisor":
            return f"advisor {self.payload.get('severity')}: {self.payload.get('concern', '')}"
        if self.kind == "degraded":
            return f"decoding degraded: {self.payload.get('reason', '')}"
        if self.kind == "unparsable":
            return "model reply could not be parsed into an action"
        return self.event_type


@dataclass
class RunTranscript:
    """A run, reconstructed from the append-only journal alone.

    This is what research wave 7 called **authority legibility**, in its first concrete
    form. Nothing here is a second record kept alongside the run: it is derived entirely
    from events the loop already appended, which is what makes it trustworthy — a summary
    written by the thing being summarised is not evidence, and a replay that needs its own
    storage is a second source of truth that can disagree with the first.

    `D-030` argues this is a category the field structurally cannot copy quickly, because
    copying it means having the events first.
    """

    run_id: str
    entries: list[ReplayEntry] = field(default_factory=list)

    @property
    def tool_calls(self) -> list[ReplayEntry]:
        return [e for e in self.entries if e.kind == "tool_call"]

    @property
    def denials(self) -> list[ReplayEntry]:
        return [e for e in self.entries if e.denied]

    @property
    def checkpoints(self) -> list[str]:
        return [
            str(e.payload.get("sha"))
            for e in self.entries
            if e.kind == "checkpoint" and e.payload.get("sha")
        ]

    @property
    def outcome(self) -> str:
        for entry in reversed(self.entries):
            if entry.kind == "done":
                return "done"
        return "incomplete"

    @property
    def untrusted_entries(self) -> int:
        return sum(1 for e in self.entries if e.trust == "untrusted_model_output")

    def render(self) -> str:
        lines = [f"run {self.run_id} — {len(self.entries)} recorded events, {self.outcome}"]
        for entry in self.entries:
            marker = "!" if entry.denied else " "
            lines.append(f"{marker} {entry.seq:>5}  [{entry.trust}]  {entry.summarise()}")
        if self.checkpoints:
            lines.append(
                f"\n{len(self.checkpoints)} checkpoint(s) — restore with: "
                f"sovereign checkpoints --restore {self.checkpoints[-1][:12]}"
            )
        return "\n".join(lines)


def replay_run(events, run_id: str) -> RunTranscript:
    """Reconstruct one run from the event store.

    Deterministic by construction: it reads a stream and maps it, holding no state of its
    own and making no inference the events do not support. Replaying the same journal twice
    gives the same transcript, which is the property that makes it usable as evidence rather
    than as a report.
    """
    stream_id = run_id if run_id.startswith("agent-loop:") else f"agent-loop:{run_id}"
    transcript = RunTranscript(run_id=run_id)
    for row in events.read_stream(stream_id):
        payload = row.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"raw": payload}
        transcript.entries.append(
            ReplayEntry(
                seq=int(row.get("seq", 0)),
                kind=_KNOWN.get(row.get("event_type", ""), "other"),
                event_type=str(row.get("event_type", "")),
                trust=str(row.get("trust", "")),
                payload=payload if isinstance(payload, dict) else {"value": payload},
            )
        )
    return transcript
