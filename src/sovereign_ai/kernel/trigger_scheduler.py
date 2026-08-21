from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from .jobs import JobRecord
from .triggers import RecurringTriggerStore
from .workflow_service import WorkflowService

logger = logging.getLogger(__name__)


class TriggerScheduler:
    """Polls for due `RecurringTrigger`s and starts their workflow (FIXES.md Tier 5).

    Mirrors `JobDispatcher`'s own `start()`/`shutdown()` background-task shape
    deliberately -- this is the same category of thing (a long-lived asyncio loop owned
    by the API-layer app instance, not part of `SovereignKernel` itself, for the same
    reason `JobDispatcher` isn't: `SovereignKernel` should stay usable without a running
    event loop, e.g. from the `sovereign` CLI's synchronous commands).

    A trigger firing only ever calls the existing `WorkflowService.start()` -- the exact
    same call a human-initiated `POST /workflows/definitions/{id}/start` makes. This is
    a second way to *initiate* a workflow instance on a schedule, never a second way to
    *run* one; no execution logic is duplicated here.
    """

    def __init__(
        self,
        triggers: RecurringTriggerStore,
        workflows: WorkflowService,
        submit_callback: Callable[[JobRecord], Any],
        *,
        poll_interval_seconds: float = 5.0,
    ):
        self.triggers = triggers
        self.workflows = workflows
        self._submit_callback = submit_callback
        self.poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name="soai-trigger-scheduler")

    async def shutdown(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                # A bookkeeping failure in one poll must never stop future polls -- the
                # same "best-effort side effect, never take down the caller" contract
                # job_executor's own workflow-advance hook follows.
                logger.exception("trigger scheduler tick failed")
            await asyncio.sleep(self.poll_interval_seconds)

    def tick(self, *, now: float | None = None) -> list[JobRecord]:
        """Run one poll synchronously -- exposed separately from `_loop` so a test (or a
        caller that wants deterministic control instead of wall-clock polling) can invoke
        exactly one check without waiting on `poll_interval_seconds`. `now` is threaded
        straight through to the store so a test can assert against a fixed instant
        instead of a real-time interval short enough to be flaky against test overhead."""
        submitted: list[JobRecord] = []
        for trigger in self.triggers.due(now=now):
            try:
                _, jobs = self.workflows.start(trigger.workflow_definition_id)
            except ValueError:
                # The definition this trigger names no longer exists (or never did).
                # Disable it rather than retrying forever against something that can
                # never succeed -- the same "don't spin on a request that can't work"
                # reasoning RosterService applies to an authority-ceiling violation.
                self.triggers.set_enabled(trigger.id, False)
                continue
            self.triggers.mark_ran(trigger.id, now=now)
            for job in jobs:
                self._submit_callback(job)
                submitted.append(job)
        return submitted
