from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .migrations import Migration, MigrationRunner

WorkflowInstanceStatus = Literal["running", "completed", "failed"]
StepStatus = Literal["pending", "queued", "succeeded", "failed"]

DEFINITION_MIGRATIONS = [
    Migration(
        version=1,
        name="create_workflow_definitions_table",
        sql="""
            CREATE TABLE IF NOT EXISTS workflow_definitions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                steps_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(name, version)
            );
            CREATE INDEX IF NOT EXISTS workflow_definitions_name
                ON workflow_definitions(name, version DESC);
        """,
    ),
]

INSTANCE_MIGRATIONS = [
    Migration(
        version=1,
        name="create_workflow_instances_table",
        sql="""
            CREATE TABLE IF NOT EXISTS workflow_instances (
                id TEXT PRIMARY KEY,
                definition_id TEXT NOT NULL,
                status TEXT NOT NULL,
                step_states_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS workflow_instances_definition
                ON workflow_instances(definition_id, status);
        """,
    ),
]


class WorkflowStep(BaseModel):
    id: str
    job_kind: Literal["chat", "specialist", "media", "agent"]
    request_template: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class WorkflowDefinitionRecord(BaseModel):
    """An immutable, versioned DAG factory (docs/ARCHITECTURE.md's object-boundary table;
    FIXES.md Tier 5).

    Owns: the step graph itself -- which job kind and request template each step uses,
    and which other steps it depends on.

    Must not own: mutable in-flight state. There is deliberately no update method on this
    store; a change to the graph is a new version under the same `name`, never an edit to
    an existing `(name, version)` row -- a running `WorkflowInstance` references a
    specific version, so its graph can never shift underneath it mid-execution.
    """

    id: str
    name: str
    version: int
    steps: list[WorkflowStep]
    created_at: float


class WorkflowInstanceRecord(BaseModel):
    """One in-flight (or finished) execution of a `WorkflowDefinition`.

    Owns: which step is pending/queued/succeeded/failed, and which `Job` id each queued
    step created.

    Must not own: the graph itself -- that always comes from the immutable
    `WorkflowDefinitionRecord` this instance references by id.
    """

    id: str
    definition_id: str
    status: WorkflowInstanceStatus
    step_states: dict[str, dict[str, Any]]
    created_at: float
    updated_at: float


class WorkflowValidationError(ValueError):
    """Raised by WorkflowDefinitionStore.create() for a malformed DAG -- unknown
    dependency ids or a cycle. Distinguished from a bare ValueError so callers can
    translate it to a 400 without string-matching."""


def _validate_dag(steps: list[WorkflowStep]) -> None:
    if not steps:
        raise WorkflowValidationError("A workflow must have at least one step")
    ids = {step.id for step in steps}
    if len(ids) != len(steps):
        raise WorkflowValidationError("Step ids must be unique within a workflow")
    for step in steps:
        unknown = set(step.depends_on) - ids
        if unknown:
            raise WorkflowValidationError(
                f"Step {step.id!r} depends on unknown step id(s): {sorted(unknown)}"
            )
    # Kahn's algorithm: a topological sort exists iff the graph is acyclic.
    remaining = {step.id: set(step.depends_on) for step in steps}
    resolved: set[str] = set()
    while remaining:
        ready = [step_id for step_id, deps in remaining.items() if deps <= resolved]
        if not ready:
            raise WorkflowValidationError(
                f"Workflow steps contain a dependency cycle: {sorted(remaining)}"
            )
        for step_id in ready:
            resolved.add(step_id)
            del remaining[step_id]


class WorkflowDefinitionStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        MigrationRunner(self.path, DEFINITION_MIGRATIONS).apply_pending()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> WorkflowDefinitionRecord:
        return WorkflowDefinitionRecord(
            id=row["id"],
            name=row["name"],
            version=row["version"],
            steps=[WorkflowStep(**item) for item in json.loads(row["steps_json"])],
            created_at=row["created_at"],
        )

    def create(self, name: str, steps: list[WorkflowStep]) -> WorkflowDefinitionRecord:
        _validate_dag(steps)
        definition_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT MAX(version) AS v FROM workflow_definitions WHERE name=?", (name,)
            ).fetchone()
            version = (row["v"] or 0) + 1
            connection.execute(
                """INSERT INTO workflow_definitions(id,name,version,steps_json,created_at)
                   VALUES(?,?,?,?,?)""",
                (
                    definition_id, name, version,
                    json.dumps([step.model_dump() for step in steps]), now,
                ),
            )
        record = self.get(definition_id)
        assert record is not None
        return record

    def get(self, definition_id: str) -> WorkflowDefinitionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_definitions WHERE id=?", (definition_id,)
            ).fetchone()
        return self._record(row) if row else None

    def latest(self, name: str) -> WorkflowDefinitionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_definitions WHERE name=? ORDER BY version DESC LIMIT 1",
                (name,),
            ).fetchone()
        return self._record(row) if row else None

    def list_versions(self, name: str) -> list[WorkflowDefinitionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM workflow_definitions WHERE name=? ORDER BY version", (name,)
            ).fetchall()
        return [self._record(row) for row in rows]


class WorkflowInstanceStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        MigrationRunner(self.path, INSTANCE_MIGRATIONS).apply_pending()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> WorkflowInstanceRecord:
        return WorkflowInstanceRecord(
            id=row["id"],
            definition_id=row["definition_id"],
            status=row["status"],
            step_states=json.loads(row["step_states_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(
        self, definition_id: str, step_states: dict[str, dict[str, Any]]
    ) -> WorkflowInstanceRecord:
        instance_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO workflow_instances
                   (id,definition_id,status,step_states_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?)""",
                (instance_id, definition_id, "running", json.dumps(step_states), now, now),
            )
        record = self.get(instance_id)
        assert record is not None
        return record

    def get(self, instance_id: str) -> WorkflowInstanceRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_instances WHERE id=?", (instance_id,)
            ).fetchone()
        return self._record(row) if row else None

    def update(
        self, instance_id: str, status: WorkflowInstanceStatus, step_states: dict[str, dict[str, Any]]
    ) -> WorkflowInstanceRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE workflow_instances
                   SET status=?, step_states_json=?, updated_at=? WHERE id=?""",
                (status, json.dumps(step_states), time.time(), instance_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Unknown workflow instance: {instance_id}")
        record = self.get(instance_id)
        assert record is not None
        return record

    def list_for_definition(self, definition_id: str) -> list[WorkflowInstanceRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM workflow_instances WHERE definition_id=? ORDER BY created_at DESC",
                (definition_id,),
            ).fetchall()
        return [self._record(row) for row in rows]
