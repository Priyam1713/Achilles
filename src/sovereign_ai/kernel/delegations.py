from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .migrations import Migration, MigrationRunner

DelegationStatus = Literal[
    "proposed", "awaiting_approval", "approved", "rejected", "running", "completed", "failed"
]

MIGRATIONS = [
    Migration(
        version=1,
        name="create_delegations_table",
        sql="""
            CREATE TABLE IF NOT EXISTS delegations (
                id TEXT PRIMARY KEY,
                parent_subject_id TEXT NOT NULL,
                objective TEXT NOT NULL,
                inputs_json TEXT NOT NULL DEFAULT '{}',
                expected_artifacts_json TEXT NOT NULL DEFAULT '[]',
                acceptance_tests_json TEXT NOT NULL DEFAULT '[]',
                requested_grants_json TEXT NOT NULL DEFAULT '[]',
                deadline REAL,
                budget_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL,
                child_job_id TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS delegations_parent
                ON delegations(parent_subject_id, status);
        """,
    ),
]


class DelegationRecord(BaseModel):
    """A structured parent-child work contract (docs/ARCHITECTURE.md's object-boundary
    table; FIXES.md Tier 5).

    Owns: the objective, inputs, expected artifacts, acceptance tests, the grants it is
    *requesting* (not holding), a deadline and a budget.

    Must not own: authority merely because one agent requested it. Proposing a delegation
    never issues a `CapabilityGrant` by itself -- `RosterService.propose_delegation()`
    always runs each requested grant through the same `PolicyEngine.evaluate()` every
    other action in this kernel goes through, and creates an `ApprovalRequest` instead of
    a grant whenever policy says one is required. Only once every requested grant is
    actually held does the delegation's child `Job` get created and dispatched -- "every
    delegated child is an ordinary job with a bounded grant set" (knowledge/research.md's
    minimal implementation sequence, step 3), not a second execution path.
    """

    id: str
    parent_subject_id: str
    objective: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_artifacts: list[str] = Field(default_factory=list)
    acceptance_tests: list[str] = Field(default_factory=list)
    requested_grants: list[dict[str, Any]] = Field(default_factory=list)
    deadline: float | None = None
    budget: dict[str, Any] = Field(default_factory=dict)
    status: DelegationStatus
    child_job_id: str | None = None
    created_at: float
    updated_at: float


class DelegationStore:
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
    def _record(row: sqlite3.Row) -> DelegationRecord:
        return DelegationRecord(
            id=row["id"],
            parent_subject_id=row["parent_subject_id"],
            objective=row["objective"],
            inputs=json.loads(row["inputs_json"]),
            expected_artifacts=json.loads(row["expected_artifacts_json"]),
            acceptance_tests=json.loads(row["acceptance_tests_json"]),
            requested_grants=json.loads(row["requested_grants_json"]),
            deadline=row["deadline"],
            budget=json.loads(row["budget_json"]),
            status=row["status"],
            child_job_id=row["child_job_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(
        self,
        parent_subject_id: str,
        objective: str,
        *,
        inputs: dict[str, Any] | None = None,
        expected_artifacts: list[str] | None = None,
        acceptance_tests: list[str] | None = None,
        requested_grants: list[dict[str, Any]] | None = None,
        deadline: float | None = None,
        budget: dict[str, Any] | None = None,
    ) -> DelegationRecord:
        delegation_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO delegations
                   (id,parent_subject_id,objective,inputs_json,expected_artifacts_json,
                    acceptance_tests_json,requested_grants_json,deadline,budget_json,
                    status,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    delegation_id, parent_subject_id, objective,
                    json.dumps(inputs or {}), json.dumps(expected_artifacts or []),
                    json.dumps(acceptance_tests or []), json.dumps(requested_grants or []),
                    deadline, json.dumps(budget or {}), "proposed", now, now,
                ),
            )
        record = self.get(delegation_id)
        assert record is not None
        return record

    def get(self, delegation_id: str) -> DelegationRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM delegations WHERE id=?", (delegation_id,)
            ).fetchone()
        return self._record(row) if row else None

    def list_for_subject(self, parent_subject_id: str) -> list[DelegationRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM delegations WHERE parent_subject_id=? ORDER BY created_at DESC",
                (parent_subject_id,),
            ).fetchall()
        return [self._record(row) for row in rows]

    def set_status(
        self, delegation_id: str, status: DelegationStatus, *, child_job_id: str | None = None
    ) -> DelegationRecord:
        now = time.time()
        with self._connect() as connection:
            if child_job_id is not None:
                connection.execute(
                    "UPDATE delegations SET status=?, child_job_id=?, updated_at=? WHERE id=?",
                    (status, child_job_id, now, delegation_id),
                )
            else:
                connection.execute(
                    "UPDATE delegations SET status=?, updated_at=? WHERE id=?",
                    (status, now, delegation_id),
                )
        record = self.get(delegation_id)
        if record is None:
            raise ValueError(f"Unknown delegation: {delegation_id}")
        return record
