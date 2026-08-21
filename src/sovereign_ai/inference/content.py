from __future__ import annotations

from typing import Any


def extract_message_content(payload: dict[str, Any]) -> str:
    """Pull the assistant's text from an OpenAI-compatible chat-completion payload.

    Handles "thinking" chat templates (Qwen3.5/Nemotron-style) whose reasoning trace lives
    in a separate `reasoning_content` field. `content` holds the final answer once the
    model finishes reasoning and is always preferred -- but it is legitimately empty when
    generation was cut off by `max_tokens` mid-thought, before the model ever reached a
    final answer. Falling back to `reasoning_content` in that case returns the model's
    actual work-in-progress text instead of an empty string a caller would otherwise treat
    as "the model produced nothing".

    Found live 2026-08-21: a quality-eval run against `qwen35-9b` scored 1/5 because four
    of five tasks returned an empty `content` -- not because the model got them wrong, but
    because thinking-mode reasoning consumed the whole token budget before an answer was
    ever written to `content`. The same unwrap-only-`content` logic existed independently
    in `job_executor._assistant_content` (the collaboration-reply path) and
    `NativeAgentLoop._extract_content` (the agent-loop path), so both could have silently
    treated a real, budget-cut-off model turn as empty output in production, not just in
    this benchmark. See `docs/FIXES.md` F-028.
    """
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return ""
