from __future__ import annotations

import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ShadowCommit:
    sha: str
    label: str


class ShadowRepository:
    """A git repository that watches a workspace without ever touching its own history.

    Adapted from Cline's checkpoint design (Apache-2.0; recorded in `NOTICE`), because
    `knowledge/research.md` D-021 identified the same gap: this project's `CheckpointStore`
    snapshots *job state*, not *file state*, so nothing could undo an edit an agent made.
    That is what makes unattended operation unreasonable, not the edit itself.

    The mechanism is a separate `--git-dir` under `state/` pointed at the workspace as its
    `--work-tree`. The user's own `.git` is never read, written, staged or committed to, and
    the shadow repository is not a remote of anything. Restoring is therefore always a local,
    reversible operation on files -- never a rewrite of the user's history.

    It is an **undo and audit mechanism, not a security boundary**: it holds whatever the
    workspace holds, so a workspace policy would keep secrets out of must not be shadowed.
    """

    def __init__(self, state_dir: str | Path, workspace: str | Path):
        self.workspace = Path(workspace).expanduser().resolve(strict=False)
        digest = hashlib.sha256(str(self.workspace).encode("utf-8")).hexdigest()[:16]
        self.git_dir = Path(state_dir).expanduser().resolve(strict=False) / "shadow" / digest

    @staticmethod
    def available() -> bool:
        return shutil.which("git") is not None

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "git",
                "--git-dir",
                str(self.git_dir),
                "--work-tree",
                str(self.workspace),
                *args,
            ],
            capture_output=True,
            text=True,
            check=check,
            timeout=120,
        )

    def ensure(self) -> None:
        if not self.available():
            raise RuntimeError("git is not installed; shadow checkpoints are unavailable")
        if not self.workspace.is_dir():
            raise FileNotFoundError(f"workspace does not exist: {self.workspace}")
        if (self.git_dir / "HEAD").exists():
            return
        self.git_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", "--quiet", "--bare", str(self.git_dir)],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        # A bare repo has no work tree of its own; these make the borrowed one behave.
        self._run("config", "core.bare", "false")
        self._run("config", "core.worktree", str(self.workspace))
        self._run("config", "user.email", "shadow@achilles.local")
        self._run("config", "user.name", "Achilles shadow checkpoints")

    def snapshot(self, label: str) -> ShadowCommit | None:
        """Commit the workspace's current state. Returns ``None`` when nothing changed."""
        self.ensure()
        self._run("add", "-A")
        status = self._run("status", "--porcelain")
        staged = self._run("diff", "--cached", "--name-only")
        if not status.stdout.strip() and not staged.stdout.strip():
            return None
        self._run("commit", "--quiet", "--allow-empty-message", "-m", label)
        sha = self._run("rev-parse", "HEAD").stdout.strip()
        return ShadowCommit(sha=sha, label=label)

    def history(self, limit: int = 50) -> list[ShadowCommit]:
        if not (self.git_dir / "HEAD").exists():
            return []
        result = self._run(
            "log", f"--max-count={limit}", "--pretty=format:%H%x1f%s", check=False
        )
        commits: list[ShadowCommit] = []
        for line in result.stdout.splitlines():
            if "\x1f" not in line:
                continue
            sha, _, label = line.partition("\x1f")
            commits.append(ShadowCommit(sha=sha, label=label))
        return commits

    def restore(self, sha: str) -> None:
        """Put the workspace files back as they were at `sha`.

        Deliberately `checkout <sha> -- .` rather than `reset --hard`: it restores file
        content without moving the shadow branch, so the states recorded after this one are
        still in the log and the restore is itself undoable.
        """
        self.ensure()
        self._run("checkout", sha, "--", ".")
