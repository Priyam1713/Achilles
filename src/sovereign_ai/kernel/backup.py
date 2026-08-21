from __future__ import annotations

import sqlite3
import time
from pathlib import Path


def backup_database(path: str | Path, backup_dir: str | Path) -> Path:
    """Write a consistent point-in-time copy of a SQLite database.

    Uses SQLite's own online backup API (`Connection.backup`) rather than copying the file
    on disk. A raw file copy taken while a WAL-mode writer is active can capture a torn
    snapshot -- the main file without its not-yet-checkpointed WAL segment. The backup API
    is safe to run concurrently with writers.
    """
    source_path = Path(path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest_path = backup_dir / f"{source_path.stem}-{stamp}{source_path.suffix}"

    source = sqlite3.connect(source_path)
    try:
        dest = sqlite3.connect(dest_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    return dest_path


def restore_database(backup_path: str | Path, target_path: str | Path) -> None:
    """Overwrite `target_path` with the contents of `backup_path`.

    The caller is responsible for ensuring no other process holds `target_path` open --
    this checkpoints the target's WAL before restoring but does not attempt live-swap
    coordination across processes beyond that.
    """
    backup_path = Path(backup_path)
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    target = sqlite3.connect(target_path)
    try:
        target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        backup = sqlite3.connect(backup_path)
        try:
            backup.backup(target)
        finally:
            backup.close()
    finally:
        target.close()
