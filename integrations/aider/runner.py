from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import requests


def snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts or any(part.startswith(".aider") for part in relative.parts):
            continue
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError(f"unsafe workspace entry: {relative}")
        if path.is_file():
            if path.stat().st_size > 2_000_000:
                raise ValueError(f"workspace file exceeds adapter limit: {relative}")
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def invoke_tool(args: argparse.Namespace, name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{args.kernel_url.rstrip('/')}/tools/{name}",
        headers={
            "Authorization": f"Bearer {args.session_token}",
            "content-type": "application/json",
        },
        json={
            "args": tool_args,
            "workspace": args.workspace,
            "subject_id": args.subject_id,
            "run_id": args.run_id,
        },
        timeout=90,
    )
    response.raise_for_status()
    return response.json().get("result", {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--kernel-url", required=True)
    parser.add_argument("--session-token", required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--aider", required=True)
    args = parser.parse_args()

    canonical = Path(args.workspace).resolve()
    before = snapshot(canonical)
    run_root = Path(tempfile.mkdtemp(prefix="aider-shadow-"))
    shadow = run_root / "repo"
    try:
        shutil.copytree(canonical, shadow)
        subprocess.run(["git", "init", "-q"], cwd=shadow, check=True)
        subprocess.run(["git", "config", "user.name", "Achilles Arena"], cwd=shadow, check=True)
        subprocess.run(
            ["git", "config", "user.email", "arena@localhost"], cwd=shadow, check=True
        )
        subprocess.run(["git", "add", "-A"], cwd=shadow, check=True)
        subprocess.run(["git", "commit", "-qm", "arena baseline"], cwd=shadow, check=True)

        history = run_root / "chat-history.md"
        input_history = run_root / "input-history"
        empty_env = run_root / "empty.env"
        empty_env.write_text("", encoding="utf-8")
        editable = sorted(path for path in before if not path.startswith("."))
        task = args.task.replace(str(canonical), ".")
        task += (
            "\n\nThe repository is the current working directory. Use relative paths. "
            "Make the requested implementation now and do not create extra files."
        )
        command = [
            args.aider,
            "--model",
            f"openai/{args.model}",
            "--message",
            task,
            "--yes-always",
            "--no-auto-commits",
            "--no-dirty-commits",
            "--no-gitignore",
            "--no-auto-lint",
            "--no-auto-test",
            "--no-suggest-shell-commands",
            "--no-check-update",
            "--no-analytics",
            "--no-stream",
            "--no-pretty",
            "--no-fancy-input",
            "--no-multiline",
            "--no-notifications",
            "--no-detect-urls",
            "--disable-playwright",
            "--no-restore-chat-history",
            "--chat-history-file",
            str(history),
            "--input-history-file",
            str(input_history),
            "--env-file",
            str(empty_env),
            *editable,
        ]
        env = dict(os.environ)
        env.update(
            {
                "OPENAI_API_BASE": args.base_url,
                "OPENAI_API_KEY": "local-backend-no-key-required",
                "AIDER_ANALYTICS": "false",
                "LITELLM_TELEMETRY": "False",
                "DO_NOT_TRACK": "1",
                "HOME": str(run_root / "home"),
                "XDG_CONFIG_HOME": str(run_root / "config"),
            }
        )
        completed = subprocess.run(
            command,
            cwd=shadow,
            env=env,
            text=True,
            capture_output=True,
            timeout=170,
            check=False,
        )
        if completed.returncode != 0:
            print(completed.stdout[-6000:])
            print(completed.stderr[-6000:], file=os.sys.stderr)
            return completed.returncode

        after = snapshot(shadow)
        current = snapshot(canonical)
        if current != before:
            raise RuntimeError("canonical workspace changed concurrently during Aider run")
        changed = sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
        for relative in changed:
            target = canonical / relative
            source = shadow / relative
            if relative not in after:
                invoke_tool(args, "delete_file", {"path": str(target)})
                continue
            content = source.read_text(encoding="utf-8")
            result = invoke_tool(args, "write_file", {"path": str(target), "content": content})
            if result.get("error") or result.get("denied"):
                raise RuntimeError(f"Achilles rejected {relative}: {result}")
        result = {
            "changed_files": changed,
            "stdout_tail": completed.stdout[-2000:],
        }
        print("SOAI_AIDER_RESULT=" + json.dumps(result, separators=(",", ":")))
        return 0
    finally:
        shutil.rmtree(run_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
