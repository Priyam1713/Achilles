from __future__ import annotations

import difflib
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxChange:
    """One file the run wants to change, and what it wants to do to it."""

    relative: str
    kind: str  # created | modified | deleted
    before: str | None
    after: str | None


@dataclass
class DiffSandbox:
    """Changes accumulate outside the workspace and apply atomically, once approved.

    Adapted from Plandex (`knowledge/harness-research.md`), which `research.md` wave 8 called
    possibly the best single idea in Tier 3 — because it answers two of wave 7's severity-1
    findings with one mechanism:

    * **X-03, approvals with no evidence.** Today a human authorises `write:workspace` in
      advance and never sees the change. With a sandbox they approve *the actual diff*, after
      reading it.
    * **X-04, no diff view anywhere.** The diff already exists as an object, so rendering one
      stops being a feature to build.

    It also changes what a grant is *for*. Writing into the sandbox needs no authority
    because it touches nothing real; **applying** does. That is a better boundary than the
    one we had: exploration is free, commitment is deliberate.

    **What it does not cover, and must not be assumed to:** execution. `run_command` runs a
    real program against the real filesystem, so a sandboxed run still gates commands exactly
    as before. This is a file-mutation sandbox, not a container — `docs/AUTOMATION.md` and
    the OpenShell/Docker path remain the answer for execution isolation.
    """

    root: Path
    workspace: Path
    touched: set[str] = field(default_factory=set)
    deleted: set[str] = field(default_factory=set)

    @classmethod
    def create(cls, state_dir: str | Path, run_id: str, workspace: str | Path) -> DiffSandbox:
        root = Path(state_dir) / "sandboxes" / run_id
        root.mkdir(parents=True, exist_ok=True)
        return cls(root=root, workspace=Path(workspace).expanduser().resolve(strict=False))

    # -- path mapping ------------------------------------------------------------------

    def _relative(self, path: str | Path) -> str | None:
        target = Path(path).expanduser().resolve(strict=False)
        try:
            return target.relative_to(self.workspace).as_posix()
        except ValueError:
            # Outside the sandboxed workspace: not this sandbox's business, and silently
            # capturing it would hide a write the operator should see.
            return None

    def overlay_path(self, path: str | Path) -> Path | None:
        relative = self._relative(path)
        return None if relative is None else self.root / relative

    def read_path(self, path: str | Path) -> Path:
        """Where a read should actually look.

        The overlay wins, so an agent sees its own pending changes and can build on them.
        A run that could not read what it just wrote would be unable to make two edits to
        one file.
        """
        relative = self._relative(path)
        if relative is None or relative in self.deleted:
            return Path(path)
        candidate = self.root / relative
        return candidate if candidate.is_file() else Path(path)

    def exists(self, path: str | Path) -> bool:
        relative = self._relative(path)
        if relative is not None and relative in self.deleted:
            return False
        return self.read_path(path).is_file()

    # -- recording ---------------------------------------------------------------------

    def stage_write(self, path: str | Path, content: str) -> Path | None:
        relative = self._relative(path)
        if relative is None:
            return None
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.touched.add(relative)
        self.deleted.discard(relative)
        return target

    def stage_delete(self, path: str | Path) -> bool:
        relative = self._relative(path)
        if relative is None:
            return False
        self.deleted.add(relative)
        self.touched.discard(relative)
        overlay = self.root / relative
        if overlay.is_file():
            overlay.unlink()
        return True

    # -- review and commit -------------------------------------------------------------

    def changes(self) -> list[SandboxChange]:
        result: list[SandboxChange] = []
        for relative in sorted(self.touched):
            original = self.workspace / relative
            before = original.read_text(encoding="utf-8", errors="replace") if original.is_file() else None
            after = (self.root / relative).read_text(encoding="utf-8", errors="replace")
            result.append(
                SandboxChange(
                    relative=relative,
                    kind="modified" if before is not None else "created",
                    before=before,
                    after=after,
                )
            )
        for relative in sorted(self.deleted):
            original = self.workspace / relative
            if original.is_file():
                result.append(
                    SandboxChange(
                        relative=relative,
                        kind="deleted",
                        before=original.read_text(encoding="utf-8", errors="replace"),
                        after=None,
                    )
                )
        return result

    def diff(self) -> str:
        """A unified diff of everything staged. This is the evidence an approval needs."""
        blocks: list[str] = []
        for change in self.changes():
            before = (change.before or "").splitlines(keepends=True)
            after = (change.after or "").splitlines(keepends=True)
            blocks.extend(
                difflib.unified_diff(
                    before,
                    after,
                    fromfile=f"a/{change.relative}" if change.before is not None else "/dev/null",
                    tofile=f"b/{change.relative}" if change.after is not None else "/dev/null",
                )
            )
        return "".join(blocks)

    def apply(self) -> list[str]:
        """Commit every staged change to the real workspace.

        The caller is responsible for having authorised this -- `apply` is the action a
        human approves, and it is the only point at which the workspace changes.
        """
        applied: list[str] = []
        for change in self.changes():
            target = self.workspace / change.relative
            if change.kind == "deleted":
                if target.is_file():
                    target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(change.after or "", encoding="utf-8")
            applied.append(change.relative)
        self.discard()
        return applied

    def discard(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)
        self.touched.clear()
        self.deleted.clear()
