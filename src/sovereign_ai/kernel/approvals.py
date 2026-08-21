from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .migrations import Migration, MigrationRunner

ApprovalStatus = Literal["pending", "approved", "denied", "expired"]

MIGRATIONS = [
    Migration(
        version=1,
        name="create_approval_requests_table",
        sql="""
            CREATE TABLE IF NOT EXISTS approval_requests (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                action TEXT NOT NULL,
                scope TEXT NOT NULL,
                risk TEXT NOT NULL,
                reason TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL,
                resolver_id TEXT,
                resolution_reason TEXT,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                resolved_at REAL
            );
            CREATE INDEX IF NOT EXISTS approval_requests_status
                ON approval_requests(status, expires_at);
        """,
    ),
]


class ApprovalRequestRecord(BaseModel):
    """A structured, durable request for human sign-off (FIXES.md Tier 5;
    docs/ARCHITECTURE.md's object-boundary table).

    Owns: the decision (`status`), the `risk` and `reason` a `PolicyEngine.evaluate()` call
    produced, supporting `evidence`, an `expiry`, and who actually `resolved` it.

    Must not own: authority by itself -- resolving one approved does not execute anything;
    it only unblocks `RosterService` from issuing the `CapabilityGrant` the requester
    asked for. And it must never be satisfied implicitly: before this store existed,
    `PolicyEngine.evaluate()`'s `approval_required` flag was returned to a caller and
    forgotten the moment the HTTP response was sent -- nothing durable ever recorded that
    an action was waiting on a human, and nothing could show it to one. A chat reaction or
    an unlogged verbal "sure, go ahead" is exactly what this object exists to replace.
    """

    id: str
    subject_id: str
    action: str
    scope: str
    risk: str
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus
    resolver_id: str | None = None
    resolution_reason: str | None = None
    created_at: float
    expires_at: float
    resolved_at: float | None = None


class ApprovalRequestStore:
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
    def _record(row: sqlite3.Row) -> ApprovalRequestRecord:
        return ApprovalRequestRecord(
            id=row["id"],
            subject_id=row["subject_id"],
            action=row["action"],
            scope=row["scope"],
            risk=row["risk"],
            reason=row["reason"],
            evidence=json.loads(row["evidence_json"]),
            status=row["status"],
            resolver_id=row["resolver_id"],
            resolution_reason=row["resolution_reason"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            resolved_at=row["resolved_at"],
        )

    def create(
        self,
        subject_id: str,
        action: str,
        scope: str,
        risk: str,
        reason: str,
        *,
        evidence: dict[str, Any] | None = None,
        ttl_seconds: float = 86400.0,
    ) -> ApprovalRequestRecord:
        request_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO approval_requests
                   (id,subject_id,action,scope,risk,reason,evidence_json,status,
                    created_at,expires_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    request_id, subject_id, action, scope, risk, reason,
                    json.dumps(evidence or {}), "pending", now, now + ttl_seconds,
                ),
            )
        record = self.get(request_id)
        assert record is not None
        return record

    def get(self, request_id: str) -> ApprovalRequestRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approval_requests WHERE id=?", (request_id,)
            ).fetchone()
        return self._record(row) if row else None

    def list_pending(self) -> list[ApprovalRequestRecord]:
        self.expire_stale()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM approval_requests WHERE status='pending' ORDER BY created_at"
            ).fetchall()
        return [self._record(row) for row in rows]

    def resolve(
        self, request_id: str, resolver_id: str, approved: bool, reason: str
    ) -> ApprovalRequestRecord:
        """Resolve exactly once. Raises if the request is unknown, already resolved, or
        has expired -- an expired request cannot be silently rubber-stamped after the
        fact; the requester has to ask again."""
        self.expire_stale()
        existing = self.get(request_id)
        if existing is None:
            raise ValueError(f"Unknown approval request: {request_id}")
        if existing.status != "pending":
            raise ValueError(f"Approval request {request_id} is already '{existing.status}'")
        now = time.time()
        status: ApprovalStatus = "approved" if approved else "denied"
        with self._connect() as connection:
            connection.execute(
                """UPDATE approval_requests
                   SET status=?, resolver_id=?, resolution_reason=?, resolved_at=?
                   WHERE id=? AND status='pending'""",
                (status, resolver_id, reason, now, request_id),
            )
        record = self.get(request_id)
        assert record is not None
        return record

    def expire_stale(self) -> int:
        now = time.time()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE approval_requests SET status='expired' WHERE status='pending' AND expires_at < ?",
                (now,),
            )
            return cursor.rowcount
