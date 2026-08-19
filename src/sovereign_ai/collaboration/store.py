from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .models import CollaborationEvent, IdentityRecord, RoomRecord

GENESIS_HASH = "0" * 64


class CollaborationStore:
    """SQLite-backed rooms with an append-only, per-room tamper-evident event chain."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS collaboration_identities (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('human','agent','system')),
                    trust TEXT NOT NULL,
                    agent_json TEXT,
                    created_at_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collaboration_rooms (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    created_at_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collaboration_memberships (
                    room_id TEXT NOT NULL REFERENCES collaboration_rooms(id),
                    identity_id TEXT NOT NULL REFERENCES collaboration_identities(id),
                    joined_at_ns INTEGER NOT NULL,
                    PRIMARY KEY(room_id, identity_id)
                );
                CREATE TABLE IF NOT EXISTS collaboration_room_heads (
                    room_id TEXT PRIMARY KEY REFERENCES collaboration_rooms(id),
                    event_hash TEXT NOT NULL,
                    event_count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS collaboration_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    room_id TEXT NOT NULL REFERENCES collaboration_rooms(id),
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL REFERENCES collaboration_identities(id),
                    payload_json TEXT NOT NULL,
                    trust TEXT NOT NULL,
                    parent_event_id TEXT,
                    created_at_ns INTEGER NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT UNIQUE NOT NULL
                );
                CREATE INDEX IF NOT EXISTS collaboration_events_room_seq
                    ON collaboration_events(room_id, seq);
                CREATE INDEX IF NOT EXISTS collaboration_events_parent
                    ON collaboration_events(parent_event_id, seq);
                """
            )
            # One-time adoption for databases created before room heads existed.
            # Once present, anchors are only advanced transactionally by append_event.
            connection.execute(
                """INSERT OR IGNORE INTO collaboration_room_heads
                   (room_id,event_hash,event_count)
                   SELECT r.id,
                          COALESCE(
                            (SELECT e.event_hash FROM collaboration_events e
                             WHERE e.room_id=r.id ORDER BY e.seq DESC LIMIT 1),
                            ?
                          ),
                          (SELECT COUNT(*) FROM collaboration_events e
                           WHERE e.room_id=r.id)
                   FROM collaboration_rooms r""",
                (GENESIS_HASH,),
            )

    @staticmethod
    def _identity(row: sqlite3.Row) -> IdentityRecord:
        return IdentityRecord(
            id=row["id"],
            display_name=row["display_name"],
            kind=row["kind"],
            trust=row["trust"],
            agent=json.loads(row["agent_json"]) if row["agent_json"] else None,
            created_at_ns=row["created_at_ns"],
        )

    @staticmethod
    def _room(row: sqlite3.Row) -> RoomRecord:
        return RoomRecord(**dict(row))

    @staticmethod
    def _event(row: sqlite3.Row) -> CollaborationEvent:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        return CollaborationEvent(**item)

    @staticmethod
    def _digest(
        *,
        event_id: str,
        room_id: str,
        event_type: str,
        actor_id: str,
        payload_json: str,
        trust: str,
        parent_event_id: str | None,
        created_at_ns: int,
        previous_hash: str,
    ) -> str:
        canonical = json.dumps(
            {
                "actor_id": actor_id,
                "created_at_ns": created_at_ns,
                "event_id": event_id,
                "event_type": event_type,
                "parent_event_id": parent_event_id,
                "payload_json": payload_json,
                "previous_hash": previous_hash,
                "room_id": room_id,
                "trust": trust,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def upsert_identity(
        self,
        identity_id: str,
        display_name: str,
        kind: str,
        trust: str,
        agent: dict[str, Any] | None = None,
    ) -> IdentityRecord:
        created_at_ns = time.time_ns()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO collaboration_identities
                   (id,display_name,kind,trust,agent_json,created_at_ns)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name,
                   kind=excluded.kind,trust=excluded.trust,agent_json=excluded.agent_json""",
                (
                    identity_id,
                    display_name,
                    kind,
                    trust,
                    json.dumps(agent, sort_keys=True) if agent else None,
                    created_at_ns,
                ),
            )
        identity = self.get_identity(identity_id)
        assert identity is not None
        return identity

    def get_identity(self, identity_id: str) -> IdentityRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM collaboration_identities WHERE id=?", (identity_id,)
            ).fetchone()
        return self._identity(row) if row else None

    def identities(self) -> list[IdentityRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM collaboration_identities ORDER BY kind, display_name"
            ).fetchall()
        return [self._identity(row) for row in rows]

    def create_room(self, room_id: str, name: str, purpose: str) -> RoomRecord:
        created_at_ns = time.time_ns()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO collaboration_rooms(id,name,purpose,created_at_ns)
                   VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name,purpose=excluded.purpose""",
                (room_id, name, purpose, created_at_ns),
            )
            connection.execute(
                """INSERT OR IGNORE INTO collaboration_room_heads
                   (room_id,event_hash,event_count) VALUES(?,?,0)""",
                (room_id, GENESIS_HASH),
            )
        room = self.get_room(room_id)
        assert room is not None
        return room

    def get_room(self, room_id: str) -> RoomRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM collaboration_rooms WHERE id=?", (room_id,)
            ).fetchone()
        return self._room(row) if row else None

    def rooms(self) -> list[RoomRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM collaboration_rooms ORDER BY created_at_ns, name"
            ).fetchall()
        return [self._room(row) for row in rows]

    def add_member(self, room_id: str, identity_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO collaboration_memberships
                   (room_id,identity_id,joined_at_ns) VALUES(?,?,?)""",
                (room_id, identity_id, time.time_ns()),
            )

    def members(self, room_id: str) -> list[IdentityRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT i.* FROM collaboration_identities i
                   JOIN collaboration_memberships m ON m.identity_id=i.id
                   WHERE m.room_id=? ORDER BY i.kind, i.display_name""",
                (room_id,),
            ).fetchall()
        return [self._identity(row) for row in rows]

    def is_member(self, room_id: str, identity_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT 1 FROM collaboration_memberships
                   WHERE room_id=? AND identity_id=?""",
                (room_id, identity_id),
            ).fetchone()
        return row is not None

    def append_event(
        self,
        room_id: str,
        event_type: str,
        actor_id: str,
        payload: dict[str, Any],
        *,
        parent_event_id: str | None = None,
        event_id: str | None = None,
    ) -> CollaborationEvent:
        if not self.is_member(room_id, actor_id):
            raise PermissionError(f"{actor_id} is not a member of room {room_id}")
        identity = self.get_identity(actor_id)
        assert identity is not None
        event_id = event_id or uuid.uuid4().hex
        created_at_ns = time.time_ns()
        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        with self._lock, self._connect() as connection:
            previous = connection.execute(
                """SELECT event_hash FROM collaboration_events
                   WHERE room_id=? ORDER BY seq DESC LIMIT 1""",
                (room_id,),
            ).fetchone()
            previous_hash = previous["event_hash"] if previous else GENESIS_HASH
            event_hash = self._digest(
                event_id=event_id,
                room_id=room_id,
                event_type=event_type,
                actor_id=actor_id,
                payload_json=payload_json,
                trust=identity.trust,
                parent_event_id=parent_event_id,
                created_at_ns=created_at_ns,
                previous_hash=previous_hash,
            )
            connection.execute(
                """INSERT INTO collaboration_events
                   (event_id,room_id,event_type,actor_id,payload_json,trust,parent_event_id,
                    created_at_ns,previous_hash,event_hash)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    event_id,
                    room_id,
                    event_type,
                    actor_id,
                    payload_json,
                    identity.trust,
                    parent_event_id,
                    created_at_ns,
                    previous_hash,
                    event_hash,
                ),
            )
            connection.execute(
                """UPDATE collaboration_room_heads
                   SET event_hash=?,event_count=event_count+1 WHERE room_id=?""",
                (event_hash, room_id),
            )
            row = connection.execute(
                "SELECT * FROM collaboration_events WHERE event_id=?", (event_id,)
            ).fetchone()
        assert row is not None
        return self._event(row)

    def events(self, room_id: str, limit: int = 100) -> list[CollaborationEvent]:
        limit = max(1, min(limit, 500))
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM (
                     SELECT * FROM collaboration_events WHERE room_id=?
                     ORDER BY seq DESC LIMIT ?
                   ) ORDER BY seq""",
                (room_id, limit),
            ).fetchall()
        return [self._event(row) for row in rows]

    def get_event(self, event_id: str) -> CollaborationEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM collaboration_events WHERE event_id=?", (event_id,)
            ).fetchone()
        return self._event(row) if row else None

    def latest_canvas(self, room_id: str) -> CollaborationEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM collaboration_events
                   WHERE room_id=? AND event_type='canvas.updated'
                   ORDER BY seq DESC LIMIT 1""",
                (room_id,),
            ).fetchone()
        return self._event(row) if row else None

    def verify_chain(self, room_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM collaboration_events WHERE room_id=? ORDER BY seq", (room_id,)
            ).fetchall()
            anchor = connection.execute(
                "SELECT * FROM collaboration_room_heads WHERE room_id=?", (room_id,)
            ).fetchone()
        previous_hash = GENESIS_HASH
        for row in rows:
            expected = self._digest(
                event_id=row["event_id"],
                room_id=row["room_id"],
                event_type=row["event_type"],
                actor_id=row["actor_id"],
                payload_json=row["payload_json"],
                trust=row["trust"],
                parent_event_id=row["parent_event_id"],
                created_at_ns=row["created_at_ns"],
                previous_hash=previous_hash,
            )
            if row["previous_hash"] != previous_hash or row["event_hash"] != expected:
                return {"valid": False, "events": len(rows), "broken_at": row["event_id"]}
            previous_hash = row["event_hash"]
        if (
            anchor is None
            or anchor["event_hash"] != previous_hash
            or anchor["event_count"] != len(rows)
        ):
            return {
                "valid": False,
                "events": len(rows),
                "broken_at": "room-head-anchor",
                "head": previous_hash,
            }
        return {"valid": True, "events": len(rows), "head": previous_hash, "anchored": True}
