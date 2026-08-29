from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The filename the field standardised on. Adopting it rather than inventing a fourth one is
#: the whole point of `knowledge/research.md` D-022: a repository that already carries an
#: AGENTS.md for some other agent works here with no new file and no conversion.
PROJECT_INSTRUCTION_FILES = ("AGENTS.md", ".agents/AGENTS.md")

MAX_INSTRUCTION_CHARS = 8_000


@dataclass(frozen=True)
class ContextBudget:
    """How much of a 16K window one agent turn is allowed to spend on its own history.

    `D-025`: context is the scarcest resource on this machine and was the only major one the
    kernel did not arbitrate. The loop appended every reply and every observation forever,
    with a flat per-observation truncation as the sole control, which meant a long task did
    not degrade -- it hit the wall and stopped.
    """

    keep_recent_turns: int = 6
    keep_leading_turns: int = 1
    max_observation_chars: int = 2_000
    max_history_chars: int = 24_000


def load_project_instructions(workspace: str | Path | None) -> str | None:
    """Read the workspace's own AGENTS.md, if it has one.

    Returned content is **guidance, not authority**. It is a file inside a directory that may
    have been cloned from anywhere, so it is handed to the model labelled as untrusted
    document content: it can shape how work is done and can never widen what may be done
    (baseline invariant 4, `D-022`'s safety boundary).
    """
    if not workspace:
        return None
    root = Path(workspace)
    for name in PROJECT_INSTRUCTION_FILES:
        candidate = root / name
        try:
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if not text:
            continue
        if len(text) > MAX_INSTRUCTION_CHARS:
            text = text[:MAX_INSTRUCTION_CHARS] + "\n\n[...project instructions truncated...]"
        return text
    return None


def _observation_digest(turn: dict[str, Any]) -> str:
    action = turn.get("action") or {}
    tool = action.get("tool") or (
        f"batch({len(action.get('batch') or ())})" if action.get("batch") else "reply"
    )
    observation = turn.get("observation") or {}
    if isinstance(observation, list):
        nested = [
            item.get("observation")
            for item in observation
            if isinstance(item, dict) and isinstance(item.get("observation"), dict)
        ]
        if any(item.get("denied") for item in nested):
            return f"{tool}(denied)"
        if any(item.get("error") for item in nested):
            return f"{tool}(error)"
        return str(tool)
    if not isinstance(observation, dict):
        return str(tool)
    if observation.get("denied"):
        return f"{tool}(denied)"
    if observation.get("error"):
        return f"{tool}(error)"
    return str(tool)


def compact_history(
    history: list[dict[str, Any]], budget: ContextBudget
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Fit a run's history into the budget, and say exactly what was dropped.

    The elision is **deterministic**, not model-generated. A summarising pass would cost a
    whole generation at 6-52 tok/s and could invent a step that never happened; counting the
    elided tool calls costs nothing and cannot lie. The first turn is kept because it usually
    contains the orienting read, and the most recent turns are kept because that is where the
    task actually is.

    Returns the turns to render plus a note describing the elision, or ``None`` when the
    history already fit.
    """
    total = sum(len(json.dumps(turn, default=str)) for turn in history)
    over_turns = len(history) > budget.keep_recent_turns + budget.keep_leading_turns
    if not over_turns and total <= budget.max_history_chars:
        return history, None

    leading = history[: budget.keep_leading_turns]
    recent = history[-budget.keep_recent_turns :] if budget.keep_recent_turns else []
    elided = history[len(leading) : len(history) - len(recent)]
    if not elided:
        return history, None

    counts = Counter(_observation_digest(turn) for turn in elided)
    note = {
        "elided_turns": len(elided),
        "tools": dict(sorted(counts.items())),
    }
    return [*leading, *recent], note


def truncate_observation(observation: Any, budget: ContextBudget) -> str:
    text = json.dumps(observation, default=str)
    if len(text) <= budget.max_observation_chars:
        return text
    return text[: budget.max_observation_chars] + f"...[+{len(text) - budget.max_observation_chars} chars]"
