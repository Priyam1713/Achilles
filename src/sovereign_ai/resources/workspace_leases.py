from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from pydantic import BaseModel

from sovereign_ai.kernel.migrations import Migration, MigrationRunner

MIGRATIONS = [
    Migration(
        version=1,
        name="create_workspace_leases_table",
        sql="""
            CREATE TABLE IF NOT EXISTS workspace_leases (
                id TEXT PRIMARY KEY,
                root_path TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                writable INTEGER NOT NULL,
                acquired_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS workspace_leases_root
                ON workspace_leases(root_path, writable);
        """,
    ),
]


class WorkspaceLeaseRecord(BaseModel):
    id: str
    root_path: str
    subject_id: str
    writable: bool
    acquired_at: float
    expires_at: float


class WorkspaceLeaseStore:
    """Durable, run-scoped, expiring write access to one workspace root (FIXES.md Tier 5;
    docs/ARCHITECTURE.md's object-boundary table).

    Owns: a run-scoped isolated workspace or approved persistent volume, time-bounded.

    Must not own: permanent agent ownership of an arbitrary host path -- that authority is
    `execution.workspaces.WorkspaceRegistry`'s job, unchanged by this store. A lease layers
    *on top* of the registry, never replaces it: acquiring one still requires the target
    root to already be `WorkspaceRegistry`-approved (callers check `workspaces.require()`
    first, exactly as before this store existed), and this store only adds a second,
    narrower, time-bounded question -- "does *this* run currently hold write access to
    *this* root" -- for callers (delegated runs in particular) that want it.

    Mirrors `resources.gpu_leases.GPULeaseStore`'s TTL/`try_acquire`/`release`/`reap_stale`
    shape deliberately, with one real difference: a GPU lease's holder is always the
    kernel process itself, so `psutil.pid_exists()` is a meaningful staleness check. A
    workspace lease's holder is a logical `Run`, not an OS process the kernel can name a
    PID for (the work may be happening inside a WSL worker, a container, or nowhere yet).
    Staleness here is TTL expiry only -- honest about what this store can and cannot
    detect, rather than reusing a liveness check that would not mean anything here.
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
    def _record(row: sqlite3.Row) -> WorkspaceLeaseRecord:
        return WorkspaceLeaseRecord(
            id=row["id"], root_path=row["root_path"], subject_id=row["subject_id"],
            writable=bool(row["writable"]), acquired_at=row["acquired_at"],
            expires_at=row["expires_at"],
        )

    def active(self) -> list[WorkspaceLeaseRecord]:
        self.reap_stale()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM workspace_leases ORDER BY acquired_at"
            ).fetchall()
        return [self._record(row) for row in rows]

    def active_for_subject(self, subject_id: str) -> list[WorkspaceLeaseRecord]:
        self.reap_stale()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM workspace_leases WHERE subject_id=? ORDER BY acquired_at",
                (subject_id,),
            ).fetchall()
        return [self._record(row) for row in rows]

    def try_acquire(
        self, root_path: str, subject_id: str, writable: bool, ttl_seconds: float
    ) -> WorkspaceLeaseRecord | None:
        """Grant a lease if no conflicting exclusive-write lease exists on this root.

        Multiple read (`writable=False`) leases on the same root never conflict. A
        `writable=True` lease conflicts with any other lease -- read or write -- already
        held on that exact root, matching the intent of a run-scoped isolated workspace:
        while one run is writing, no other run should be reading a workspace mid-mutation.
        """
        self.reap_stale()
        with self._connect() as connection:
            if writable:
                held = connection.execute(
                    "SELECT 1 FROM workspace_leases WHERE root_path=? LIMIT 1", (root_path,)
                ).fetchone()
            else:
                held = connection.execute(
                    "SELECT 1 FROM workspace_leases WHERE root_path=? AND writable=1 LIMIT 1",
                    (root_path,),
                ).fetchone()
            if held is not None:
                return None
            lease_id = uuid.uuid4().hex
            now = time.time()
            connection.execute(
                """INSERT INTO workspace_leases(id,root_path,subject_id,writable,acquired_at,expires_at)
                   VALUES(?,?,?,?,?,?)""",
                (lease_id, root_path, subject_id, int(writable), now, now + ttl_seconds),
            )
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspace_leases WHERE id=?", (lease_id,)
            ).fetchone()
        return self._record(row)

    def release(self, lease_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM workspace_leases WHERE id=?", (lease_id,))

    def is_leased(self, lease_id: str, subject_id: str) -> bool:
        """Whether `lease_id` is currently active and held by `subject_id` -- the check an
        enforcement point makes before honoring a lease-scoped write."""
        self.reap_stale()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM workspace_leases WHERE id=? AND subject_id=? LIMIT 1",
                (lease_id, subject_id),
            ).fetchone()
        return row is not None

    def reap_stale(self) -> int:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM workspace_leases WHERE expires_at < ?", (now,)
            )
            return cursor.rowcount
