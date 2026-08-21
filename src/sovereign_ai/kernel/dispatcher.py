from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .jobs import JobRecord, JobStore
from .runs import RunRecord, RunStore

Executor = Callable[[JobRecord, RunRecord], Awaitable[dict[str, Any]]]


class QueueFullError(RuntimeError):
    """Raised by `submit` when the bounded queue is at capacity.

    This is deliberate backpressure (FIXES.md F-010), not a bug to work around: a caller
    that keeps submitting into a full queue should see an explicit rejection it can retry
    or surface to a user, never an unboundedly growing pile of in-process tasks.
    """


class JobDispatcher:
    """Bounded, durable job execution.

    Replaces unbounded `asyncio.create_task()` per submission with a fixed pool of worker
    coroutines pulling from a capacity-limited queue. Each submission creates a new `Run`
    attempt (see `runs.py`) rather than mutating the `Job` in place, so a retry is a new
    attempt with its own record, not a rewritten history.

    The dispatcher itself has no idea what a "chat" or "specialist" job actually does --
    that lives in the injected `executor`, which keeps this class testable without a real
    kernel, and keeps kernel-specific execution logic in one place (`job_executor.py`)
    instead of duplicated between this dispatcher and any other caller.
    """

    def __init__(
        self,
        jobs: JobStore,
        runs: RunStore,
        executor: Executor,
        *,
        max_concurrency: int = 4,
        queue_max: int = 100,
    ):
        self.jobs = jobs
        self.runs = runs
        self._executor = executor
        self._max_concurrency = max(1, max_concurrency)
        self._queue: asyncio.Queue[tuple[str, JobRecord]] = asyncio.Queue(maxsize=max(1, queue_max))
        self._workers: list[asyncio.Task[None]] = []
        # Keyed by job_id, not run_id: only one attempt is ever in flight for a given job
        # at a time, and DELETE /jobs/{job_id} needs to find it by the id callers already
        # have.
        self._active_tasks: dict[str, asyncio.Task[None]] = {}

    def start(self) -> None:
        if self._workers:
            return
        self._workers = [
            asyncio.create_task(self._worker_loop(), name=f"soai-dispatcher-{i}")
            for i in range(self._max_concurrency)
        ]

    async def shutdown(self) -> None:
        for worker in self._workers:
            worker.cancel()
        for task in list(self._active_tasks.values()):
            task.cancel()
        pending = [*self._workers, *self._active_tasks.values()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._workers = []
        self._active_tasks.clear()

    def submit(self, job: JobRecord) -> RunRecord:
        """Create a new Run attempt for `job` and enqueue it.

        Raises `QueueFullError` if the bounded queue has no room; the caller (the API
        layer) is expected to turn that into an explicit failure response, not silently
        retry into an unbounded backlog.
        """
        attempt = self.runs.next_attempt(job.id)
        run = self.runs.create(job.id, attempt, job.request, job.metadata)
        try:
            self._queue.put_nowait((run.id, job))
        except asyncio.QueueFull as exc:
            error = "dispatcher queue is full; try again shortly"
            self.runs.finish(run.id, "failed", error=error)
            self.jobs.finish(job.id, "failed", error=error)
            raise QueueFullError(error) from exc
        return run

    def cancel(self, job_id: str) -> bool:
        task = self._active_tasks.get(job_id)
        if task is None:
            return False
        task.cancel()
        return True

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)

    async def _worker_loop(self) -> None:
        while True:
            run_id, job = await self._queue.get()
            try:
                await self._run_one(run_id, job)
            finally:
                self._queue.task_done()

    async def _run_one(self, run_id: str, job: JobRecord) -> None:
        run = self.runs.get(run_id)
        if run is None:
            return
        self.runs.mark_running(run_id)
        self.jobs.mark_running(job.id)
        task = asyncio.current_task()
        assert task is not None
        self._active_tasks[job.id] = task
        try:
            result = await self._executor(job, run)
            self.runs.finish(run_id, "succeeded", result=result)
            self.jobs.finish(job.id, "succeeded", result=result)
        except asyncio.CancelledError:
            error = "cancelled by user"
            self.runs.finish(run_id, "cancelled", error=error)
            self.jobs.finish(job.id, "cancelled", error=error)
            raise
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.runs.finish(run_id, "failed", error=error)
            self.jobs.finish(job.id, "failed", error=error)
        finally:
            self._active_tasks.pop(job.id, None)
