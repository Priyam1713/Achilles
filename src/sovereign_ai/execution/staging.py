from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TreeEntry:
    kind: str
    digest: str | None = None
    target: str | None = None


TreeSnapshot = dict[str, TreeEntry]


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_tree(root: Path) -> None:
    """Reject special files and symlinks that can escape the staged workspace."""
    root = root.resolve(strict=True)
    for path in [root, *root.rglob("*")]:
        rel = path.relative_to(root)
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            target = os.readlink(path)
            if os.path.isabs(target):
                raise ValueError(
                    f"Absolute symlink is not allowed in staged workspace: {rel} -> {target}"
                )
            resolved = (path.parent / target).resolve(strict=False)
            if not _inside(root, resolved):
                raise ValueError(
                    f"Escaping symlink is not allowed in staged workspace: {rel} -> {target}"
                )
        elif stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode):
            continue
        else:
            raise ValueError(f"Special file is not allowed in staged workspace: {rel}")


def snapshot_tree(root: Path) -> TreeSnapshot:
    root = root.resolve(strict=True)
    validate_tree(root)
    out: TreeSnapshot = {".": TreeEntry("dir")}
    for path in sorted(root.rglob("*"), key=lambda p: str(p.relative_to(root)).casefold()):
        rel = path.relative_to(root).as_posix()
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            out[rel] = TreeEntry("symlink", target=os.readlink(path))
        elif stat.S_ISDIR(st.st_mode):
            out[rel] = TreeEntry("dir")
        elif stat.S_ISREG(st.st_mode):
            out[rel] = TreeEntry("file", digest=_sha256(path))
        else:  # validate_tree already rejects this, kept fail-closed.
            raise ValueError(f"Unsupported file type: {rel}")
    return out


def _remove_path(path: Path) -> None:
    try:
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.exists():
            shutil.rmtree(path)
    except FileNotFoundError:
        pass


def _clear_children(root: Path) -> None:
    for child in list(root.iterdir()):
        _remove_path(child)


def _copy_tree_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        if child.is_symlink():
            os.symlink(os.readlink(child), target, target_is_directory=child.is_dir())
        elif child.is_dir():
            shutil.copytree(child, target, symlinks=True)
        else:
            shutil.copy2(child, target)


def reconcile_workspace(
    workspace: Path, staged: Path, expected_before: TreeSnapshot
) -> dict[str, int]:
    """Commit a staged workspace only if the host tree has not changed concurrently.

    A complete backup is taken before applying the diff. Any apply failure restores the
    original tree. This favors integrity over speed because OpenShell is the high-assurance
    backend, not the low-latency path.
    """
    workspace = workspace.resolve(strict=True)
    staged = staged.resolve(strict=True)
    validate_tree(staged)

    current = snapshot_tree(workspace)
    if current != expected_before:
        raise RuntimeError(
            "Workspace changed outside the sandbox; refusing to overwrite concurrent host edits"
        )

    after = snapshot_tree(staged)
    if after == expected_before:
        return {"created": 0, "modified": 0, "deleted": 0}

    created = sum(1 for k in after if k not in expected_before and k != ".")
    deleted = sum(1 for k in expected_before if k not in after and k != ".")
    modified = sum(
        1 for k in after if k in expected_before and k != "." and after[k] != expected_before[k]
    )

    # Backup on the same parent/volume where possible. It is deleted only after verification.
    backup_parent = Path(tempfile.mkdtemp(prefix="soai-workspace-backup-"))
    backup = backup_parent / "workspace"
    try:
        shutil.copytree(workspace, backup, symlinks=True)
        try:
            _clear_children(workspace)
            _copy_tree_contents(staged, workspace)
            committed = snapshot_tree(workspace)
            if committed != after:
                raise RuntimeError("Post-commit workspace verification failed")
        except Exception as apply_error:
            try:
                _clear_children(workspace)
                _copy_tree_contents(backup, workspace)
                restored = snapshot_tree(workspace)
                if restored != expected_before:
                    raise RuntimeError("Rollback verification failed")
            except Exception as rollback_error:
                raise RuntimeError(
                    f"Workspace commit failed and rollback also failed: apply={apply_error!r}; rollback={rollback_error!r}"
                ) from rollback_error
            raise
    finally:
        shutil.rmtree(backup_parent, ignore_errors=True)

    return {"created": created, "modified": modified, "deleted": deleted}
