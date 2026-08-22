from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from sovereign_ai.execution.broker import ExecutionBroker
from sovereign_ai.execution.workspaces import WorkspaceRegistry
from sovereign_ai.kernel.types import TrustLabel

from .base import Tool, ToolContext, tool_error
from .registry import ToolSpec

#: Directories that are never worth walking for an agent and are expensive to walk.
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    "target",
}

MAX_READ_CHARS = 20_000
MAX_WRITE_CHARS = 400_000


class _WorkspaceTool(Tool):
    """Shared path handling.

    Reads are gated by `WorkspaceRegistry` alone -- knowing a path never grants authority
    to read it, but reading inside an operator-registered workspace is what a workspace is
    for. Mutations go further and clear `ExecutionBroker.authorize`, which is the same
    grant-then-policy check `run_approved` applies to a shell command. That is deliberate:
    a patch is not safer than a shell line merely because it is structured.
    """

    def __init__(self, workspaces: WorkspaceRegistry, execution: ExecutionBroker | None = None):
        self.workspaces = workspaces
        self.execution = execution

    def _resolve(self, path: str, ctx: ToolContext, *, write: bool) -> Path:
        if not path:
            raise ValueError("a 'path' argument is required")
        candidate = Path(path)
        if not candidate.is_absolute() and ctx.workspace:
            candidate = Path(ctx.workspace) / candidate
        self.workspaces.require(candidate, require_write=write)
        return candidate.expanduser().resolve(strict=False)

    def _authorize_write(self, target: Path, ctx: ToolContext, description: str) -> None:
        if self.execution is None:
            raise PermissionError(
                "this tool has no ExecutionBroker and therefore cannot authorise a mutation"
            )
        self.execution.authorize(
            action="write",
            scope="workspace",
            description=f"{description}: {target}",
            trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            approved=ctx.approved,
            mutates_state=True,
            subject_id=ctx.subject_id,
        )


class ReadFileTool(_WorkspaceTool):
    spec = ToolSpec(
        id="read_file",
        description="Read a UTF-8 text file inside an approved workspace",
        capabilities=["coding", "reading", "files"],
        risk_scope="workspace",
        schema={
            "args": {"path": "<absolute path>", "offset": 0, "limit": 0},
            "note": "offset/limit are 1-indexed line bounds; omit both to read from the start",
        },
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        target = self._resolve(str(args.get("path", "")), ctx, write=False)
        if not target.is_file():
            return tool_error(f"not a file: {target}")
        text = target.read_text(encoding="utf-8", errors="replace")
        offset = int(args.get("offset") or 0)
        limit = int(args.get("limit") or 0)
        if offset or limit:
            lines = text.splitlines()
            start = max(0, offset - 1) if offset else 0
            end = start + limit if limit else len(lines)
            selected = lines[start:end]
            body = "\n".join(selected)
            return {
                "path": str(target),
                "content": body[:MAX_READ_CHARS],
                "truncated": len(body) > MAX_READ_CHARS,
                "first_line": start + 1,
                "last_line": start + len(selected),
                "total_lines": len(lines),
            }
        return {
            "path": str(target),
            "content": text[:MAX_READ_CHARS],
            "truncated": len(text) > MAX_READ_CHARS,
            "total_lines": text.count("\n") + 1 if text else 0,
        }


class ListDirectoryTool(_WorkspaceTool):
    spec = ToolSpec(
        id="list_directory",
        description="List the entries of a directory inside an approved workspace",
        capabilities=["coding", "reading", "files"],
        risk_scope="workspace",
        schema={"args": {"path": "<absolute path>"}},
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        raw = str(args.get("path") or ctx.workspace or "")
        target = self._resolve(raw, ctx, write=False)
        if not target.is_dir():
            return tool_error(f"not a directory: {target}")
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
        return {"path": str(target), "entries": entries[:200], "total": len(entries)}


class WriteFileTool(_WorkspaceTool):
    spec = ToolSpec(
        id="write_file",
        description="Create or overwrite a text file inside an approved writable workspace",
        capabilities=["coding", "editing", "files"],
        risk_scope="workspace",
        schema={
            "args": {"path": "<absolute path>", "content": "<full file text>"},
            "note": "mutating: needs an active write grant or human approval",
        },
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        content = args.get("content")
        if not isinstance(content, str):
            return tool_error("write_file requires a string 'content'")
        if len(content) > MAX_WRITE_CHARS:
            return tool_error(f"content exceeds {MAX_WRITE_CHARS} characters")
        target = self._resolve(str(args.get("path", "")), ctx, write=True)
        self._authorize_write(target, ctx, "write_file")
        existed = target.is_file()
        previous = target.read_text(encoding="utf-8", errors="replace") if existed else ""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "path": str(target),
            "created": not existed,
            "bytes_written": len(content.encode("utf-8")),
            "previous_lines": previous.count("\n") + 1 if previous else 0,
            "lines": content.count("\n") + 1 if content else 0,
        }


class EditFileTool(_WorkspaceTool):
    """Exact-string search/replace.

    `D-021` recorded Codex's `apply_patch` envelope as the format to adopt. This is a
    deliberate, recorded narrowing of that decision rather than a silent one: Aider's own
    evidence is that edit format should be chosen per model, and an exact unique-match
    replacement is the format a 9B-class local model produces correctly most often -- there
    are no line numbers to miscount and no hunk headers to fabricate. A uniqueness check
    turns an ambiguous edit into a refusal instead of a wrong edit, which matters more here
    than expressiveness. The context-anchored patch envelope remains open work.
    """

    spec = ToolSpec(
        id="edit_file",
        description="Replace an exact string in a file (must match exactly once unless replace_all)",
        capabilities=["coding", "editing", "files"],
        risk_scope="workspace",
        schema={
            "args": {
                "path": "<absolute path>",
                "old_string": "<exact text to find>",
                "new_string": "<replacement text>",
                "replace_all": False,
            },
            "note": "mutating: needs an active write grant or human approval",
        },
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        old = args.get("old_string")
        new = args.get("new_string")
        if not isinstance(old, str) or not old:
            return tool_error("edit_file requires a non-empty 'old_string'")
        if not isinstance(new, str):
            return tool_error("edit_file requires a string 'new_string'")
        if old == new:
            return tool_error("old_string and new_string are identical")
        target = self._resolve(str(args.get("path", "")), ctx, write=True)
        if not target.is_file():
            return tool_error(f"not a file: {target}")
        text = target.read_text(encoding="utf-8", errors="replace")
        occurrences = text.count(old)
        if occurrences == 0:
            return tool_error("old_string not found in file", occurrences=0)
        replace_all = bool(args.get("replace_all", False))
        if occurrences > 1 and not replace_all:
            return tool_error(
                "old_string is not unique; include more surrounding context "
                "or pass replace_all=true",
                occurrences=occurrences,
            )
        self._authorize_write(target, ctx, "edit_file")
        updated = text.replace(old, new) if replace_all else text.replace(old, new, 1)
        target.write_text(updated, encoding="utf-8")
        return {
            "path": str(target),
            "replacements": occurrences if replace_all else 1,
            "lines_before": text.count("\n") + 1,
            "lines_after": updated.count("\n") + 1,
        }


class DeleteFileTool(_WorkspaceTool):
    spec = ToolSpec(
        id="delete_file",
        description="Delete a file inside an approved writable workspace",
        capabilities=["files", "editing"],
        risk_scope="workspace",
        schema={
            "args": {"path": "<absolute path>"},
            "note": "high risk: policy requires explicit human approval",
        },
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        target = self._resolve(str(args.get("path", "")), ctx, write=True)
        if not target.is_file():
            return tool_error(f"not a file: {target}")
        if self.execution is None:
            raise PermissionError("delete_file has no ExecutionBroker to authorise against")
        # Deliberately its own action: configs/policies.yaml rates delete:workspace high and
        # approval-required, which write:workspace is not.
        self.execution.authorize(
            action="delete",
            scope="workspace",
            description=f"delete_file: {target}",
            trust=TrustLabel.UNTRUSTED_MODEL_OUTPUT,
            approved=ctx.approved,
            mutates_state=True,
            subject_id=ctx.subject_id,
        )
        target.unlink()
        return {"path": str(target), "deleted": True}


class GlobTool(_WorkspaceTool):
    spec = ToolSpec(
        id="glob",
        description="Find files by name pattern under a workspace directory",
        capabilities=["coding", "search", "files"],
        risk_scope="workspace",
        schema={"args": {"pattern": "**/*.py", "path": "<directory, optional>"}},
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        pattern = str(args.get("pattern") or "")
        if not pattern:
            return tool_error("glob requires a 'pattern'")
        root = self._resolve(str(args.get("path") or ctx.workspace or ""), ctx, write=False)
        if not root.is_dir():
            return tool_error(f"not a directory: {root}")
        matches: list[str] = []
        for candidate in root.rglob("*"):
            if any(part in SKIP_DIRS for part in candidate.parts):
                continue
            if not candidate.is_file():
                continue
            rel = candidate.relative_to(root).as_posix()
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(candidate.name, pattern):
                matches.append(str(candidate))
                if len(matches) >= 300:
                    break
        matches.sort()
        return {"root": str(root), "pattern": pattern, "matches": matches, "count": len(matches)}


class GrepTool(_WorkspaceTool):
    """Content search without shelling out.

    Every serious harness has a first-class search tool; this project had only
    `run_command`, which meant every search was a shell execution subject to the execution
    policy and dependent on whichever grep the host happened to have. Searching is a read,
    and should be gated like one.
    """

    spec = ToolSpec(
        id="grep",
        description="Search file contents by regular expression under a workspace directory",
        capabilities=["coding", "search", "files"],
        risk_scope="workspace",
        schema={
            "args": {
                "pattern": "<regex>",
                "path": "<directory, optional>",
                "glob": "*.py",
                "max_results": 100,
            }
        },
    )

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        pattern = str(args.get("pattern") or "")
        if not pattern:
            return tool_error("grep requires a 'pattern'")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return tool_error(f"invalid regular expression: {exc}")
        root = self._resolve(str(args.get("path") or ctx.workspace or ""), ctx, write=False)
        if not root.is_dir():
            return tool_error(f"not a directory: {root}")
        name_filter = str(args.get("glob") or "")
        max_results = max(1, min(int(args.get("max_results") or 100), 500))

        hits: list[dict[str, Any]] = []
        files_scanned = 0
        for candidate in sorted(root.rglob("*")):
            if len(hits) >= max_results:
                break
            if any(part in SKIP_DIRS for part in candidate.parts) or not candidate.is_file():
                continue
            if name_filter and not (
                fnmatch.fnmatch(candidate.name, name_filter)
                or fnmatch.fnmatch(candidate.relative_to(root).as_posix(), name_filter)
            ):
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="strict")
            except (UnicodeDecodeError, OSError):
                continue  # binary or unreadable: skipping is the honest behaviour
            files_scanned += 1
            for number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    hits.append(
                        {"path": str(candidate), "line": number, "text": line.strip()[:300]}
                    )
                    if len(hits) >= max_results:
                        break
        return {
            "root": str(root),
            "pattern": pattern,
            "files_scanned": files_scanned,
            "matches": hits,
            "count": len(hits),
            "truncated": len(hits) >= max_results,
        }
