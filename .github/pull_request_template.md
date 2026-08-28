## What changed

<!-- Describe the outcome and why it belongs in Achilles. -->

## Evidence

<!-- Tests, benchmarks, reproduction steps, screenshots, or evaluation results. -->

## Authority and safety boundary

<!-- What can this change read, write, execute, authorize, expose, or persist? -->

## Rollback

<!-- How can the change be disabled or reverted without losing authoritative state? -->

## Checklist

- [ ] I ran `uv run pytest -q`.
- [ ] I ran `uv run ruff check .`.
- [ ] I added or updated tests for observable behavior.
- [ ] Documentation states both what is implemented and what remains unsupported.
- [ ] New dependencies have an upstream, licence, purpose and rollback path.
- [ ] I did not commit credentials, local state, model weights or personal configuration.
