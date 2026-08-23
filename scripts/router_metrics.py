"""Read the llama.cpp router's own counters, so token cost is measured rather than inferred.

Every claim in `docs/FIXES.md` F-057 through F-061 is about **tokens** — outlining a file to
save context, batching calls to save generations, restating an objective cheaply — and every
one of them was verified with **wall time and step counts**, which are proxies. Wall time
also moves with GPU contention and model residency, so it is a noisy proxy at that.

The router publishes the real quantity at `/metrics?model=<id>`, and it publishes it for
*every* client. That is what makes it the right instrument: the native loop, Goose, OpenCode
and Pi all talk to the same server, so snapshotting these counters around a task measures all
four on the same scale, including harnesses whose internals we cannot see.

`llamacpp:prompt_tokens_cached_total` is worth naming separately: it is prompt-cache reuse,
which `knowledge/harness-research.md` lists as an adopted-but-unconfigured lever (`D-025`).
Until now this project had no way to observe whether the cache was working at all.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

#: The counters worth carrying into a report. All monotonic, all per-model.
COUNTERS = (
    "llamacpp:prompt_tokens_total",
    "llamacpp:prompt_tokens_cached_total",
    "llamacpp:tokens_predicted_total",
    "llamacpp:prompt_seconds_total",
    "llamacpp:tokens_predicted_seconds_total",
    "llamacpp:n_decode_total",
    "llamacpp:spec_decode_num_accepted_tokens_total",
    "llamacpp:spec_decode_num_draft_tokens_total",
)

_SHORT = {
    "llamacpp:prompt_tokens_total": "prompt_tokens",
    "llamacpp:prompt_tokens_cached_total": "prompt_tokens_cached",
    "llamacpp:tokens_predicted_total": "generated_tokens",
    "llamacpp:prompt_seconds_total": "prompt_seconds",
    "llamacpp:tokens_predicted_seconds_total": "generation_seconds",
    "llamacpp:n_decode_total": "decodes",
    "llamacpp:spec_decode_num_accepted_tokens_total": "spec_accepted_tokens",
    "llamacpp:spec_decode_num_draft_tokens_total": "spec_draft_tokens",
}


@dataclass(frozen=True)
class MetricsSnapshot:
    """Counter values at one instant. `available` is False when the router did not answer."""

    values: dict[str, float]
    available: bool = True

    def since(self, earlier: MetricsSnapshot) -> dict[str, float]:
        """What happened between two snapshots.

        Counters reset to zero when the router unloads and reloads a model, which it does on
        its own schedule. A negative delta therefore means "the model was reloaded partway
        through", and reporting it as a negative token count would be worse than useless --
        so it is reported as `None`-free zero and flagged by `reset_detected`.
        """
        if not (self.available and earlier.available):
            return {}
        delta: dict[str, float] = {}
        reset = False
        for key, value in self.values.items():
            previous = earlier.values.get(key, 0.0)
            if value < previous:
                reset = True
                delta[key] = 0.0
            else:
                delta[key] = round(value - previous, 3)
        delta["reset_detected"] = 1.0 if reset else 0.0
        return delta


def snapshot(base_url: str, model: str, timeout: float = 5.0) -> MetricsSnapshot:
    """Read the router's counters for one model.

    Never raises: a measurement instrument that can fail a run is worse than no instrument.
    An unavailable snapshot produces an empty delta and says so in the report.
    """
    url = f"{base_url.rstrip('/').removesuffix('/v1')}/metrics?model={model}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, ValueError):
        return MetricsSnapshot(values={}, available=False)

    values: dict[str, float] = {}
    for line in body.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        name, _, raw = line.partition(" ")
        if name in COUNTERS:
            try:
                values[_SHORT[name]] = float(raw)
            except ValueError:
                continue
    return MetricsSnapshot(values=values, available=bool(values))


def summarise(delta: dict[str, float]) -> dict[str, Any]:
    """Turn raw counter deltas into the numbers a report should show."""
    if not delta:
        return {"available": False}
    prompt = delta.get("prompt_tokens", 0.0)
    cached = delta.get("prompt_tokens_cached", 0.0)
    generated = delta.get("generated_tokens", 0.0)
    total_prompt = prompt + cached
    return {
        "available": True,
        # The headline for this project: prompt tokens are what a 16K window spends, and
        # generated tokens are what 6-52 tok/s charges for.
        "prompt_tokens": int(prompt),
        "prompt_tokens_cached": int(cached),
        "generated_tokens": int(generated),
        "total_tokens": int(total_prompt + generated),
        "cache_hit_rate": round(cached / total_prompt, 3) if total_prompt else 0.0,
        "decodes": int(delta.get("decodes", 0.0)),
        "reset_detected": bool(delta.get("reset_detected", 0.0)),
    }
