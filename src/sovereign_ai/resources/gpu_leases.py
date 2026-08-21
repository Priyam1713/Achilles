from __future__ import annotations

import os
import sqlite3
import time
import uuid
from pathlib import Path

import psutil
from pydantic import BaseModel

from sovereign_ai.kernel.migrations import Migration, MigrationRunner

MIGRATIONS = [
    Migration(
        version=1,
        name="create_gpu_leases_table",
        sql="""
            CREATE TABLE IF NOT EXISTS gpu_leases (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                exclusive INTEGER NOT NULL,
                pid INTEGER NOT NULL,
                acquired_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );
        """,
    ),
]


class GPULeaseRecord(BaseModel):
    id: str
    owner: str
    exclusive: bool
    pid: int
    acquired_at: float
    expires_at: float


class GPULeaseStore:
    """Durable, cross-process record of who currently holds the GPU (FIXES.md F-011).

    An in-memory semaphore only coordinates callers inside one Python process. It cannot
    detect a second `sovereign serve` process, and a kernel restart forgets every lease
    even if the worker process that held it is still alive and still holding real VRAM.
    This store makes lease state a fact on disk: any process holding an exclusive lease is
    visible to any other process asking, by PID, with a TTL so a crashed holder cannot wedge
    the GPU forever, and reap_stale() distinguishes "still running" leases from orphans left
    behind by a process that no longer exists.

    Scope: leases are always acquired by the kernel process (via GPUArbiter) before it makes
    an HTTP call into a specialist/media worker, and released when that call returns -- the
    worker itself never calls this store directly. `pid` therefore always names the kernel
    process, which is why `psutil.pid_exists()` is meaningful here even though workers run
    inside WSL, a different PID namespace: the leaseholder is always the Windows-side kernel,
    never the worker. A caller that reaches a worker's own HTTP port directly, bypassing the
    kernel's brokers entirely, is not covered by this store -- that is a separate, larger
    problem (authenticating/gating each worker's own endpoint) tracked as a follow-up, not
    solved here.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        MigrationRunner(self.path, MIGRATIONS).apply_pending()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> GPULeaseRecord:
        return GPULeaseRecord(
            id=row["id"], owner=row["owner"], exclusive=bool(row["exclusive"]),
            pid=row["pid"], acquired_at=row["acquired_at"], expires_at=row["expires_at"],
        )

    def active(self) -> list[GPULeaseRecord]:
        self.reap_stale()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM gpu_leases ORDER BY acquired_at").fetchall()
        return [self._record(row) for row in rows]

    def try_acquire(self, owner: str, exclusive: bool, ttl_seconds: float) -> GPULeaseRecord | None:
        """Grant a lease if none conflicts, else return None (caller decides whether to wait).

        Non-exclusive leases never conflict with each other, matching the semantics of the
        original in-process semaphore, where only `exclusive=True` callers serialize.
        """
        self.reap_stale()
        with self._connect() as connection:
            if exclusive:
                held = connection.execute(
                    "SELECT 1 FROM gpu_leases WHERE exclusive=1 LIMIT 1"
                ).fetchone()
                if held is not None:
                    return None
            lease_id = uuid.uuid4().hex
            now = time.time()
            connection.execute(
                "INSERT INTO gpu_leases(id,owner,exclusive,pid,acquired_at,expires_at) VALUES(?,?,?,?,?,?)",
                (lease_id, owner, int(exclusive), os.getpid(), now, now + ttl_seconds),
            )
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM gpu_leases WHERE id=?", (lease_id,)).fetchone()
        return self._record(row)

    def release(self, lease_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM gpu_leases WHERE id=?", (lease_id,))

    def reap_stale(self) -> int:
        """Remove leases past their TTL, and leases whose owning process no longer exists.

        The second case is the one an in-memory semaphore structurally cannot catch: a
        kernel process that was killed (not shut down cleanly) leaves no trace in a fresh
        process's memory, but its lease row on disk still names a PID -- reaping checks
        that PID against reality instead of trusting the clock alone.
        """
        now = time.time()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM gpu_leases").fetchall()
            stale_ids = [
                row["id"] for row in rows
                if row["expires_at"] < now or not psutil.pid_exists(row["pid"])
            ]
            if stale_ids:
                connection.executemany(
                    "DELETE FROM gpu_leases WHERE id=?", [(lease_id,) for lease_id in stale_ids]
                )
        return len(stale_ids)
