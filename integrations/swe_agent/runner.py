from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import requests
import yaml
from sweagent.agent.agents import DefaultAgentConfig, get_agent_from_config
from sweagent.agent.problem_statement import TextProblemStatement


class _AchillesRuntime:
    async def upload(self, request: Any) -> None:
        del request

    async def execute(self, command: Any) -> SimpleNamespace:
        del command
        return SimpleNamespace(output="", exit_code=0)


class _AchillesDeployment:
    def __init__(self) -> None:
        self.runtime = _AchillesRuntime()

    async def is_alive(self, timeout: float = 10) -> bool:
        del timeout
        return True


class AchillesEnvironment:
    """SWE-agent environment whose only real execution path is Achilles."""

    def __init__(
        self,
        workspace: str,
        kernel_url: str,
        session_token: str,
        subject_id: str,
        run_id: str,
    ) -> None:
        self.workspace = workspace
        self.kernel_url = kernel_url.rstrip("/")
        self.session_token = session_token
        self.subject_id = subject_id
        self.run_id = run_id
        self.name = "achilles"
        self.repo = None
        self.deployment = _AchillesDeployment()
        self._root_files: dict[str, str] = {}
        self._env: dict[str, str] = {}

    def communicate(
        self,
        input: str,
        timeout: int | float = 60,
        *,
        check: Literal["warn", "ignore", "raise"] = "ignore",
        error_msg: str = "Command failed",
    ) -> str:
        command = input.strip()
        if command == "pwd":
            return self.workspace
        if command == "echo $PATH":
            return "/usr/local/bin:/usr/bin:/bin"
        if command == "submit":
            self._root_files["/root/model.patch"] = "Achilles retained workspace changes.\n"
            return "<<SWE_AGENT_SUBMISSION>>"
        if not command or self._is_tool_setup(command):
            return ""

        response = requests.post(
            f"{self.kernel_url}/tools/run_command",
            headers={
                "Authorization": f"Bearer {self.session_token}",
                "content-type": "application/json",
            },
            json={
                "args": {"argv": ["bash", "-lc", input], "mutates_state": True},
                "workspace": self.workspace,
                "subject_id": self.subject_id,
                "run_id": self.run_id,
            },
            timeout=timeout,
        )
        if response.status_code == 403:
            detail = response.json().get("detail", "policy refused this action")
            return f"denied: {detail}"
        response.raise_for_status()
        result = response.json().get("result", {})
        stdout = str(result.get("stdout", ""))
        stderr = str(result.get("stderr", ""))
        return stdout + (f"\n[stderr]\n{stderr}" if stderr else "")

    def _is_tool_setup(self, command: str) -> bool:
        return (
            command.startswith("export ")
            or command.startswith("cd /root/tools/")
            or command == f"cd {self.workspace}"
            or "/root/tools/submit" in command
        )

    def read_file(
        self,
        path: str,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        del encoding, errors
        try:
            return self._root_files[str(path)]
        except KeyError as exc:
            raise FileNotFoundError(path) from exc

    def write_file(self, path: str, content: str) -> None:
        self._root_files[str(path)] = content

    def set_env_variables(self, env_variables: dict[str, str]) -> None:
        self._env.update({key: str(value) for key, value in env_variables.items()})

    def interrupt_session(self) -> None:
        return None


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
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--call-limit", type=int, default=18)
    args = parser.parse_args()

    raw = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["agent"]
    raw["model"] = {
        "name": f"openai/{args.model}",
        "api_base": args.base_url,
        "api_key": "local-backend-no-key-required",
        "per_instance_cost_limit": 0,
        "total_cost_limit": 0,
        "per_instance_call_limit": args.call_limit,
        "temperature": 0.0,
        "top_p": 1.0,
        "max_input_tokens": 32768,
        "max_output_tokens": 4096,
        "retry": {"retries": 1, "min_wait": 1, "max_wait": 2},
        "completion_kwargs": {"timeout": 90},
    }
    config = DefaultAgentConfig.model_validate(raw)
    agent = get_agent_from_config(config)
    environment = AchillesEnvironment(
        args.workspace,
        args.kernel_url,
        args.session_token,
        args.subject_id,
        args.run_id,
    )
    problem = TextProblemStatement(
        text=args.task.replace(args.workspace, "."),
        extra_fields={"working_dir": "."},
    )
    result = agent.run(environment, problem, Path(args.output_dir))
    info = dict(result.info)
    payload = {
        "exit_status": info.get("exit_status"),
        "model_stats": info.get("model_stats", {}),
        "steps": len(result.trajectory),
    }
    print("SOAI_SWE_AGENT_RESULT=" + json.dumps(payload, separators=(",", ":")))
    return 0 if str(info.get("exit_status", "")).startswith("submitted") else 1


if __name__ == "__main__":
    os.environ.setdefault("LITELLM_TELEMETRY", "False")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    raise SystemExit(main())
