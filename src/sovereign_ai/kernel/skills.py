from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .migrations import Migration, MigrationRunner

CandidateStatus = Literal["proposed", "evaluated", "promoted", "rejected"]
EvaluationVerdict = Literal["pass", "fail"]

CANDIDATE_MIGRATIONS = [
    Migration(
        version=1,
        name="create_skill_candidates_table",
        sql="""
            CREATE TABLE IF NOT EXISTS skill_candidates (
                id TEXT PRIMARY KEY,
                source_run_id TEXT NOT NULL,
                objective TEXT NOT NULL,
                trajectory_json TEXT NOT NULL,
                proposed_by TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
        """,
    ),
]

EVALUATION_MIGRATIONS = [
    Migration(
        version=1,
        name="create_agent_evaluations_table",
        sql="""
            CREATE TABLE IF NOT EXISTS agent_evaluations (
                id TEXT PRIMARY KEY,
                skill_candidate_id TEXT NOT NULL,
                verdict TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                evaluated_by TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS agent_evaluations_candidate
                ON agent_evaluations(skill_candidate_id, created_at DESC);
        """,
    ),
]

VERSION_MIGRATIONS = [
    Migration(
        version=1,
        name="create_skill_versions_table",
        sql="""
            CREATE TABLE IF NOT EXISTS skill_versions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                skill_candidate_id TEXT NOT NULL,
                evaluation_id TEXT NOT NULL,
                trajectory_json TEXT NOT NULL,
                promoted_by TEXT NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(name, version)
            );
            CREATE INDEX IF NOT EXISTS skill_versions_name ON skill_versions(name, version DESC);
        """,
    ),
]


class SkillCandidateRecord(BaseModel):
    """An untrusted proposal, not a capability (docs/ARCHITECTURE.md's object-boundary
    table; `knowledge/research.md`: "A successful trajectory becomes an untrusted
    `SkillCandidate`, then replay/evaluation -- not automatic durable automation").

    Owns: the proposal itself -- which `Run` produced it, the objective it accomplished,
    and the literal step trajectory copied from that Run's result.

    Must not own: any actual capability. Proposing a candidate changes nothing about what
    any agent can do; only `promote()`, gated on a passing `AgentEvaluation`, produces a
    `SkillVersion`, and even that is inert data until something chooses to consult it --
    this pipeline does not include a "replay this skill automatically" executor.
    """

    id: str
    source_run_id: str
    objective: str
    trajectory: list[dict[str, Any]]
    proposed_by: str
    status: CandidateStatus
    created_at: float
    updated_at: float


class AgentEvaluationRecord(BaseModel):
    """Local evidence, not a vendor claim treated as truth (docs/ARCHITECTURE.md's
    object-boundary table: "Local evidence tied to profile/loop/model/skill versions" vs.
    "Vendor benchmark claims treated as local truth"). A verdict on one `SkillCandidate`,
    with whatever evidence backs it -- this project's own quality-eval discipline
    (FIXES.md F-028) applied to skills instead of models."""

    id: str
    skill_candidate_id: str
    verdict: EvaluationVerdict
    evidence: dict[str, Any] = Field(default_factory=dict)
    evaluated_by: str
    created_at: float


class SkillVersionRecord(BaseModel):
    """A signed, immutable promotion (docs/ARCHITECTURE.md's object-boundary table).
    "Signed" here means an auditable, non-repeatable, evidence-gated promotion decision
    with a recorded `promoted_by` and the `evaluation_id` that justified it -- not
    cryptographic signing, which this codebase has no existing infrastructure for and
    this fix does not introduce. `(name, version)`-keyed and genuinely immutable, mirroring
    `WorkflowDefinitionStore` (FIXES.md F-038): no update method exists at all."""

    id: str
    name: str
    version: int
    skill_candidate_id: str
    evaluation_id: str
    trajectory: list[dict[str, Any]]
    promoted_by: str
    created_at: float


class SkillPromotionError(ValueError):
    """Raised when promotion is attempted without a passing evaluation on record, or
    against a candidate that is not eligible. Distinguished from a bare ValueError so
    callers can translate it to a 400 without string-matching."""


class SkillCandidateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        MigrationRunner(self.path, CANDIDATE_MIGRATIONS).apply_pending()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> SkillCandidateRecord:
        return SkillCandidateRecord(
            id=row["id"],
            source_run_id=row["source_run_id"],
            objective=row["objective"],
            trajectory=json.loads(row["trajectory_json"]),
            proposed_by=row["proposed_by"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(
        self,
        source_run_id: str,
        objective: str,
        trajectory: list[dict[str, Any]],
        proposed_by: str,
    ) -> SkillCandidateRecord:
        candidate_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO skill_candidates
                   (id,source_run_id,objective,trajectory_json,proposed_by,status,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (candidate_id, source_run_id, objective, json.dumps(trajectory), proposed_by,
                 "proposed", now, now),
            )
        record = self.get(candidate_id)
        assert record is not None
        return record

    def get(self, candidate_id: str) -> SkillCandidateRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM skill_candidates WHERE id=?", (candidate_id,)
            ).fetchone()
        return self._record(row) if row else None

    def list(self, status: CandidateStatus | None = None) -> list[SkillCandidateRecord]:
        with self._connect() as connection:
            if status is not None:
                rows = connection.execute(
                    "SELECT * FROM skill_candidates WHERE status=? ORDER BY created_at DESC", (status,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM skill_candidates ORDER BY created_at DESC"
                ).fetchall()
        return [self._record(row) for row in rows]

    def set_status(self, candidate_id: str, status: CandidateStatus) -> SkillCandidateRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE skill_candidates SET status=?, updated_at=? WHERE id=?",
                (status, time.time(), candidate_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Unknown skill candidate: {candidate_id}")
        record = self.get(candidate_id)
        assert record is not None
        return record


class AgentEvaluationStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        MigrationRunner(self.path, EVALUATION_MIGRATIONS).apply_pending()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> AgentEvaluationRecord:
        return AgentEvaluationRecord(
            id=row["id"],
            skill_candidate_id=row["skill_candidate_id"],
            verdict=row["verdict"],
            evidence=json.loads(row["evidence_json"]),
            evaluated_by=row["evaluated_by"],
            created_at=row["created_at"],
        )

    def create(
        self,
        skill_candidate_id: str,
        verdict: EvaluationVerdict,
        evaluated_by: str,
        *,
        evidence: dict[str, Any] | None = None,
    ) -> AgentEvaluationRecord:
        evaluation_id = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO agent_evaluations
                   (id,skill_candidate_id,verdict,evidence_json,evaluated_by,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (evaluation_id, skill_candidate_id, verdict, json.dumps(evidence or {}),
                 evaluated_by, time.time()),
            )
        record = self.get(evaluation_id)
        assert record is not None
        return record

    def get(self, evaluation_id: str) -> AgentEvaluationRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_evaluations WHERE id=?", (evaluation_id,)
            ).fetchone()
        return self._record(row) if row else None

    def latest_for_candidate(self, skill_candidate_id: str) -> AgentEvaluationRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM agent_evaluations WHERE skill_candidate_id=?
                   ORDER BY created_at DESC, rowid DESC LIMIT 1""",
                (skill_candidate_id,),
            ).fetchone()
        return self._record(row) if row else None

    def list_for_candidate(self, skill_candidate_id: str) -> list[AgentEvaluationRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM agent_evaluations WHERE skill_candidate_id=?
                   ORDER BY created_at, rowid""",
                (skill_candidate_id,),
            ).fetchall()
        return [self._record(row) for row in rows]


class SkillVersionStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        MigrationRunner(self.path, VERSION_MIGRATIONS).apply_pending()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _record(row: sqlite3.Row) -> SkillVersionRecord:
        return SkillVersionRecord(
            id=row["id"],
            name=row["name"],
            version=row["version"],
            skill_candidate_id=row["skill_candidate_id"],
            evaluation_id=row["evaluation_id"],
            trajectory=json.loads(row["trajectory_json"]),
            promoted_by=row["promoted_by"],
            created_at=row["created_at"],
        )

    def create(
        self,
        name: str,
        skill_candidate_id: str,
        evaluation_id: str,
        trajectory: list[dict[str, Any]],
        promoted_by: str,
    ) -> SkillVersionRecord:
        version_id = uuid.uuid4().hex
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT MAX(version) AS v FROM skill_versions WHERE name=?", (name,)
            ).fetchone()
            version = (row["v"] or 0) + 1
            connection.execute(
                """INSERT INTO skill_versions
                   (id,name,version,skill_candidate_id,evaluation_id,trajectory_json,promoted_by,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (version_id, name, version, skill_candidate_id, evaluation_id,
                 json.dumps(trajectory), promoted_by, now),
            )
        record = self.get(version_id)
        assert record is not None
        return record

    def get(self, version_id: str) -> SkillVersionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM skill_versions WHERE id=?", (version_id,)
            ).fetchone()
        return self._record(row) if row else None

    def latest(self, name: str) -> SkillVersionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM skill_versions WHERE name=? ORDER BY version DESC LIMIT 1", (name,)
            ).fetchone()
        return self._record(row) if row else None

    def list_versions(self, name: str) -> list[SkillVersionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM skill_versions WHERE name=? ORDER BY version", (name,)
            ).fetchall()
        return [self._record(row) for row in rows]
