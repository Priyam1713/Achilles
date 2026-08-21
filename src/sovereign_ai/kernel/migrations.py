from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Migration:
    """One versioned, ordered schema change. `sql` may contain multiple statements."""

    version: int
    name: str
    sql: str


class MigrationRunner:
    """Tracks and applies versioned schema changes to one SQLite database.

    Every store in this project used to open with an ad-hoc `CREATE TABLE IF NOT EXISTS`.
    That is safe only for a table that does not exist yet -- it has no way to express "add
    a column," "rename a table," or "backfill a value" on a database that already has the
    old shape, without either destroying existing data or silently doing nothing. This
    runner makes schema evolution an explicit, ordered, tracked sequence instead, recorded
    in a `schema_migrations` table so `current_version()` is always a real fact about the
    database on disk, not an assumption about what code happens to be running.
    """

    def __init__(self, path: str | Path, migrations: list[Migration]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrations = sorted(migrations, key=lambda m: m.version)
        self._validate_versions()

    def _validate_versions(self) -> None:
        versions = [m.version for m in self._migrations]
        if len(set(versions)) != len(versions):
            raise ValueError(f"duplicate migration version in {self.path.name}: {versions}")
        if versions and versions != list(range(1, len(versions) + 1)):
            raise ValueError(
                f"migrations for {self.path.name} must be contiguous starting at 1, got {versions}"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at REAL NOT NULL
               )"""
        )
        return connection

    def current_version(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
        return row[0] or 0

    def apply_pending(self) -> list[int]:
        """Apply every migration newer than the database's recorded version, in order.

        A migration's `schema_migrations` row is written only after its SQL has run
        successfully, so a failed migration is never falsely recorded as applied.

        Honest limit: Python's `sqlite3.Cursor.executescript()` issues an implicit commit
        of any pending transaction before it runs and does not itself provide all-or-nothing
        rollback across the statements inside one migration's script -- if a multi-statement
        migration fails on its second statement, the first may already be committed even
        though the migration correctly is not recorded as applied. Write migration SQL
        idempotently (`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) so simply
        re-running `apply_pending()` after fixing the failure is always safe, rather than
        relying on this runner for transactional multi-statement atomicity it cannot give.
        """
        applied: list[int] = []
        current = self.current_version()
        for migration in self._migrations:
            if migration.version <= current:
                continue
            with self._connect() as connection:
                connection.executescript(migration.sql)
                connection.execute(
                    "INSERT INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
                    (migration.version, migration.name, time.time()),
                )
            applied.append(migration.version)
        return applied
