from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .migrations import Migration, MigrationRunner

AgentProfileStatus = Literal["active", "retired"]

MIGRATIONS = [
    Migration(
        version=1,
        name="create_agent_profiles_table",
        sql="""
            CREATE TABLE IF NOT EXISTS agent_profiles (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                routing_preferences_json TEXT NOT NULL DEFAULT '{}',
                memory_scopes_json TEXT NOT NULL DEFAULT '[]',
                budgets_json TEXT NOT NULL DEFAULT '{}',
                authority_ceiling_json TEXT NOT NULL DEFAULT '[]',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
        """,
    ),
]


class AgentProfileRecord(BaseModel):
    """A durable logical coworker -- outlives every model, harness, prompt and sandbox
    assigned to it (docs/ARCHITECTURE.md, "Persistent agency and the roster domain";
    knowledge/research.md D-008, FIXES.md Tier 5).

    Owns: identity, role, routing preferences, memory scopes, budgets, and an authority
    *ceiling* -- the maximum a run acting for this profile could ever be granted.

    Must not own: a running model, live credentials, or active permissions. A profile
    saying it *may* request `execute:workspace` does not mean any run currently holds
    that authority -- see `CapabilityGrant`, which is the only thing that actually
    authorizes an action, is always narrower than the ceiling, and always expires.
    """

    id: str
    display_name: str
    role: str
    status: AgentProfileStatus = "active"
    routing_preferences: dict[str, Any] = Field(default_factory=dict)
    memory_scopes: list[str] = Field(default_factory=list)
    budgets: dict[str, Any] = Field(default_factory=dict)
    authority_ceiling: list[str] = Field(default_factory=list)
    created_at: float
    updated_at: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentProfileAlreadyExists(ValueError):
    """Raised by create() so the API layer can return 409 without string-matching."""


class AgentProfileStore:
    """Durable roster of agent profiles. Mirrors CollaborationStore's non-upserting
    create/authorized-update split (FIXES.md F-003) so a profile's authority ceiling can
    never be silently redefined by reposting its id."""

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
    def _record(row: sqlite3.Row) -> AgentProfileRecord:
        return AgentProfileRecord(
            id=row["id"],
            display_name=row["display_name"],
            role=row["role"],
            status=row["status"],
            routing_preferences=json.loads(row["routing_preferences_json"]),
            memory_scopes=json.loads(row["memory_scopes_json"]),
            budgets=json.loads(row["budgets_json"]),
            authority_ceiling=json.loads(row["authority_ceiling_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def create(
        self,
        profile_id: str,
        display_name: str,
        role: str,
        *,
        routing_preferences: dict[str, Any] | None = None,
        memory_scopes: list[str] | None = None,
        budgets: dict[str, Any] | None = None,
        authority_ceiling: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentProfileRecord:
        if self.get(profile_id) is not None:
            raise AgentProfileAlreadyExists(f"Agent profile already exists: {profile_id}")
        now = time.time()
        with self._connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO agent_profiles
                       (id,display_name,role,status,routing_preferences_json,memory_scopes_json,
                        budgets_json,authority_ceiling_json,created_at,updated_at,metadata_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        profile_id,
                        display_name,
                        role,
                        "active",
                        json.dumps(routing_preferences or {}),
                        json.dumps(memory_scopes or []),
                        json.dumps(budgets or {}),
                        json.dumps(authority_ceiling or []),
                        now,
                        now,
                        json.dumps(metadata or {}),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise AgentProfileAlreadyExists(f"Agent profile already exists: {profile_id}") from exc
        record = self.get(profile_id)
        assert record is not None
        return record

    def get(self, profile_id: str) -> AgentProfileRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_profiles WHERE id=?", (profile_id,)
            ).fetchone()
        return self._record(row) if row else None

    def list(self) -> list[AgentProfileRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_profiles ORDER BY display_name"
            ).fetchall()
        return [self._record(row) for row in rows]

    def set_status(self, profile_id: str, status: AgentProfileStatus) -> AgentProfileRecord:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE agent_profiles SET status=?, updated_at=? WHERE id=?",
                (status, time.time(), profile_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Unknown agent profile: {profile_id}")
        record = self.get(profile_id)
        assert record is not None
        return record

    def has_ceiling(self, profile_id: str, action_scope: str) -> bool:
        """Whether a profile's authority ceiling could ever cover `action_scope`
        (formatted `"{action}:{scope}"`, matching `authority_ceiling` entries, e.g.
        `"execute:workspace"`).

        This is a *possibility* check only -- true does not authorize anything. It exists
        so RosterService can reject a delegation's requested grants up front when they
        exceed what the delegating profile could ever hold, before spending a policy
        evaluation or an approval round-trip on a request that can never succeed.
        """
        profile = self.get(profile_id)
        return profile is not None and action_scope in profile.authority_ceiling
