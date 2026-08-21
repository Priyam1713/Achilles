from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

from pydantic import BaseModel

from .migrations import Migration, MigrationRunner

MIGRATIONS = [
    Migration(
        version=1,
        name="create_capability_grants_table",
        sql="""
            CREATE TABLE IF NOT EXISTS capability_grants (
                id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                action TEXT NOT NULL,
                scope TEXT NOT NULL,
                granted_by TEXT NOT NULL,
                approval_request_id TEXT,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                revoked_at REAL
            );
            CREATE INDEX IF NOT EXISTS capability_grants_subject
                ON capability_grants(subject_id, action, scope);
        """,
    ),
    Migration(
        version=2,
        name="add_delegation_id_column",
        sql="""
            ALTER TABLE capability_grants ADD COLUMN delegation_id TEXT;
            CREATE INDEX IF NOT EXISTS capability_grants_delegation
                ON capability_grants(delegation_id);
        """,
    ),
]


class CapabilityGrantRecord(BaseModel):
    """The only object that actually authorizes an action (docs/ARCHITECTURE.md's
    object-boundary table; FIXES.md Tier 5).

    Owns: an expiring subject/action/scope authorization and the provenance of how it was
    approved (`granted_by`, and `approval_request_id` when a human resolved an
    `ApprovalRequest` to produce it).

    Must not own: a reusable secret or unbounded host permission. A grant is always
    narrower than its subject's `AgentProfile.authority_ceiling`, always time-bounded, and
    always revocable before it expires. Nothing in this kernel should ever check "is this
    subject generally allowed to do this" against anything other than an active row here.
    """

    id: str
    subject_id: str
    action: str
    scope: str
    granted_by: str
    approval_request_id: str | None = None
    delegation_id: str | None = None
    created_at: float
    expires_at: float
    revoked_at: float | None = None


class CapabilityGrantStore:
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
    def _record(row: sqlite3.Row) -> CapabilityGrantRecord:
        return CapabilityGrantRecord(
            id=row["id"],
            subject_id=row["subject_id"],
            action=row["action"],
            scope=row["scope"],
            granted_by=row["granted_by"],
            approval_request_id=row["approval_request_id"],
            delegation_id=row["delegation_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
        )

    def issue(
        self,
        subject_id: str,
        action: str,
        scope: str,
        granted_by: str,
        *,
        approval_request_id: str | None = None,
        delegation_id: str | None = None,
        ttl_seconds: float = 3600.0,
    ) -> CapabilityGrantRecord:
        grant_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO capability_grants
                   (id,subject_id,action,scope,granted_by,approval_request_id,delegation_id,
                    created_at,expires_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (grant_id, subject_id, action, scope, granted_by, approval_request_id,
                 delegation_id, now, now + ttl_seconds),
            )
        record = self.get(grant_id)
        assert record is not None
        return record

    def get(self, grant_id: str) -> CapabilityGrantRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM capability_grants WHERE id=?", (grant_id,)
            ).fetchone()
        return self._record(row) if row else None

    def revoke(self, grant_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE capability_grants SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                (time.time(), grant_id),
            )

    def revoke_for_delegation(self, delegation_id: str) -> int:
        """Revoke every grant tagged with this delegation. Used when a delegation with
        multiple requested grants gets one approved and a later one denied -- "a
        delegation with any denied requested grant does not partially proceed" means the
        already-issued grant must not outlive the rejection. Matches on `delegation_id`
        rather than re-deriving action/scope, so an unrelated grant that happens to share
        the same action/scope is never touched."""
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE capability_grants SET revoked_at=?
                   WHERE delegation_id=? AND revoked_at IS NULL""",
                (time.time(), delegation_id),
            )
            return cursor.rowcount

    def is_active(self, subject_id: str, action: str, scope: str) -> bool:
        """The one check every enforcement point should call: does an unexpired,
        unrevoked grant exist for exactly this subject/action/scope. No implicit
        wildcards -- a grant for `scope="workspace:/a"` never covers `scope="workspace:/b"`."""
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                """SELECT 1 FROM capability_grants
                   WHERE subject_id=? AND action=? AND scope=?
                   AND revoked_at IS NULL AND expires_at > ? LIMIT 1""",
                (subject_id, action, scope, now),
            ).fetchone()
        return row is not None

    def active_for_subject(self, subject_id: str) -> list[CapabilityGrantRecord]:
        now = time.time()
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM capability_grants
                   WHERE subject_id=? AND revoked_at IS NULL AND expires_at > ?
                   ORDER BY created_at""",
                (subject_id, now),
            ).fetchall()
        return [self._record(row) for row in rows]
