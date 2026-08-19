from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class GPULease:
    id: str
    owner: str
    acquired_at: float
    exclusive: bool


class GPUArbiter:
    """Process-local exclusive GPU lease. Cross-process workers must also honor the kernel lease endpoint."""

    def __init__(self, max_heavy_jobs: int = 1):
        self._sem = asyncio.Semaphore(max_heavy_jobs)
        self._active: dict[str, GPULease] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def lease(self, owner: str, exclusive: bool = True) -> AsyncIterator[GPULease]:
        if exclusive:
            await self._sem.acquire()
        lease = GPULease(str(uuid.uuid4()), owner, time.time(), exclusive)
        async with self._lock:
            self._active[lease.id] = lease
        try:
            yield lease
        finally:
            async with self._lock:
                self._active.pop(lease.id, None)
            if exclusive:
                self._sem.release()

    async def active(self) -> list[GPULease]:
        async with self._lock:
            return list(self._active.values())
