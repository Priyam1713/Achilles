from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


class WorkspaceRegistry:
    """Explicit capability list for directories agents may mount as writable workspaces.

    Merely knowing a filesystem path never grants authority to operate on it.
    """

    def __init__(self, state_path: Path):
        self.path = state_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        if not self.path.exists():
            self._write({"workspaces": {}})

    @staticmethod
    def _canonical(path: str | Path) -> Path:
        return Path(path).expanduser().resolve(strict=False)

    def _read(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"workspaces": {}}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def add(
        self, path: str | Path, *, label: str | None = None, writable: bool = True
    ) -> dict[str, Any]:
        root = self._canonical(path)
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Workspace directory does not exist: {root}")
        with self._lock:
            data = self._read()
            entry = {"path": str(root), "label": label or root.name, "writable": bool(writable)}
            data.setdefault("workspaces", {})[str(root)] = entry
            self._write(data)
        return entry

    def remove(self, path: str | Path) -> None:
        root = str(self._canonical(path))
        with self._lock:
            data = self._read()
            data.setdefault("workspaces", {}).pop(root, None)
            self._write(data)

    def list(self) -> list[dict[str, Any]]:
        return list(self._read().get("workspaces", {}).values())

    def resolve(self, path: str | Path, *, require_write: bool = False) -> dict[str, Any] | None:
        target = self._canonical(path)
        # Longest matching approved root wins when nested workspaces exist.
        matches: list[tuple[int, dict[str, Any]]] = []
        for entry in self.list():
            root = self._canonical(entry["path"])
            try:
                target.relative_to(root)
            except ValueError:
                continue
            if require_write and not entry.get("writable", False):
                continue
            matches.append((len(root.parts), entry))
        return max(matches, default=(0, None), key=lambda x: x[0])[1]

    def require(self, path: str | Path, *, require_write: bool = False) -> dict[str, Any]:
        match = self.resolve(path, require_write=require_write)
        if not match:
            mode = "writable " if require_write else ""
            raise PermissionError(
                f"Path is not inside an approved {mode}workspace: {self._canonical(path)}"
            )
        return match
