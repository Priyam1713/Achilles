from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from .gpu_leases import GPULeaseRecord, GPULeaseStore


@dataclass(frozen=True)
class GPULease:
    id: str
    owner: str
    acquired_at: float
    exclusive: bool


class GPUArbiter:
    """Cross-process exclusive GPU lease (FIXES.md F-011).

    Two layers, deliberately: an in-process `asyncio.Semaphore` gives fast, fair FIFO
    ordering among concurrent callers *within this process* (no disk round-trip per
    waiter); the durable `GPULeaseStore` is the actual source of truth checked at grant
    time, so a second kernel process -- or a kernel restarted after a crash that left a
    stale lease row behind -- is a fact this arbiter can see rather than an in-memory
    semaphore that silently starts over believing the GPU is free.
    """

    def __init__(self, max_heavy_jobs: int = 1, state_dir: str | Path | None = None, ttl_seconds: float = 600.0):
        self._sem = asyncio.Semaphore(max_heavy_jobs)
        self._lock = asyncio.Lock()
        self._active: dict[str, GPULease] = {}
        self._ttl_seconds = ttl_seconds
        # A store is required for real cross-process safety, but every existing call site
        # constructs GPUArbiter with just a job count; default to a conventional state path
        # rather than making this a breaking constructor change.
        self._store = GPULeaseStore(Path(state_dir or "./state") / "gpu-leases.db")

    @asynccontextmanager
    async def lease(self, owner: str, exclusive: bool = True) -> AsyncIterator[GPULease]:
        if exclusive:
            await self._sem.acquire()
        durable: GPULeaseRecord | None = None
        try:
            if exclusive:
                durable = await self._acquire_durable(owner)
            lease_id = durable.id if durable else uuid.uuid4().hex
            lease = GPULease(lease_id, owner, time.time(), exclusive)
            async with self._lock:
                self._active[lease.id] = lease
            try:
                yield lease
            finally:
                async with self._lock:
                    self._active.pop(lease.id, None)
        finally:
            if durable is not None:
                self._store.release(durable.id)
            if exclusive:
                self._sem.release()

    async def _acquire_durable(self, owner: str) -> GPULeaseRecord:
        # The in-process semaphore already ensures only one *local* waiter reaches here at
        # a time; polling handles the remaining case, a lease genuinely held by another
        # process (or a stale one not yet reaped), without blocking the event loop.
        backoff = 0.05
        while True:
            record = self._store.try_acquire(owner, exclusive=True, ttl_seconds=self._ttl_seconds)
            if record is not None:
                return record
            await asyncio.sleep(min(backoff, 2.0))
            backoff *= 1.5

    async def active(self) -> list[GPULease]:
        async with self._lock:
            local = list(self._active.values())
        # Durable leases held by *other* processes are real too, even though this process's
        # in-memory dict has never heard of them -- surface both, not just the local view.
        local_ids = {lease.id for lease in local}
        foreign = [
            GPULease(record.id, record.owner, record.acquired_at, record.exclusive)
            for record in self._store.active()
            if record.id not in local_ids
        ]
        return local + foreign
