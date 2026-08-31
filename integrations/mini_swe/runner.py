from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any

import requests
import yaml
from minisweagent import package_dir
from minisweagent.agents.default import DefaultAgent
from minisweagent.exceptions import Submitted
from minisweagent.models.litellm_model import LitellmModel
from minisweagent.utils.serialize import recursive_merge
from pydantic import BaseModel


class AchillesEnvironmentConfig(BaseModel):
    cwd: str
    kernel_url: str
    session_token: str
    subject_id: str
    run_id: str
    timeout: int = 60


class AchillesEnvironment:
    """mini-SWE-agent bash environment backed only by Achilles' governed tool plane."""

    def __init__(self, **kwargs: Any):
        self.config = AchillesEnvironmentConfig(**kwargs)

    def execute(self, action: dict, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        command = str(action.get("command", ""))
        try:
            response = requests.post(
                f"{self.config.kernel_url.rstrip('/')}/tools/run_command",
                headers={
                    "Authorization": f"Bearer {self.config.session_token}",
                    "content-type": "application/json",
                },
                json={
                    "args": {
                        "argv": ["bash", "-lc", command],
                        "mutates_state": True,
                    },
                    "workspace": cwd or self.config.cwd,
                    "subject_id": self.config.subject_id,
                    "run_id": self.config.run_id,
                },
                timeout=timeout or self.config.timeout,
            )
            if response.status_code == 403:
                detail = response.json().get("detail", "policy refused this action")
                output = {"output": f"denied: {detail}", "returncode": -1, "exception_info": ""}
            else:
                response.raise_for_status()
                result = response.json().get("result", {})
                text = str(result.get("stdout", ""))
                if result.get("stderr"):
                    text += f"\n[stderr]\n{result['stderr']}"
                output = {
                    "output": text,
                    "returncode": int(result.get("returncode", -1)),
                    "exception_info": "",
                }
        except Exception as exc:
            output = {
                "output": "",
                "returncode": -1,
                "exception_info": f"Achilles command bridge failed: {type(exc).__name__}: {exc}",
            }
        self._check_finished(output, command)
        return output

    @staticmethod
    def _check_finished(output: dict[str, Any], command: str) -> None:
        lines = str(output.get("output", "")).lstrip().splitlines(keepends=True)
        if (
            command.strip() == "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
            and output["returncode"] == 0
        ):
            sentinel_index = next(
                (
                    index
                    for index, line in enumerate(lines)
                    if line.strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
                ),
                len(lines),
            )
            submission = "".join(lines[sentinel_index + 1 :]) if sentinel_index < len(lines) else ""
            raise Submitted(
                {
                    "role": "exit",
                    "content": submission,
                    "extra": {"exit_status": "Submitted", "submission": submission},
                }
            )

    def get_template_vars(self, **kwargs: Any) -> dict[str, Any]:
        return recursive_merge(self.config.model_dump(), platform.uname()._asdict(), kwargs)

    def serialize(self) -> dict[str, Any]:
        return {
            "info": {
                "config": {
                    "environment": self.config.model_dump(mode="json"),
                    "environment_type": f"{type(self).__module__}.{type(self).__name__}",
                }
            }
        }


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
    parser.add_argument("--step-limit", type=int, default=18)
    parser.add_argument("--output-path")
    args = parser.parse_args()

    config = yaml.safe_load((Path(package_dir) / "config" / "mini.yaml").read_text())
    agent_config = dict(config["agent"])
    agent_config.pop("mode", None)
    agent_config.update(
        {
            "step_limit": args.step_limit,
            "cost_limit": 0,
            "output_path": Path(args.output_path) if args.output_path else None,
        }
    )
    model_config = dict(config["model"])
    model_config.update(
        {
            "model_name": f"openai/{args.model}",
            "cost_tracking": "ignore_errors",
            "model_kwargs": dict(config["model"].get("model_kwargs", {}))
            | {
                "custom_llm_provider": "openai",
                "api_base": args.base_url,
                "api_key": "local-backend-no-key-required",
                "max_tokens": 4096,
            },
        }
    )
    model = LitellmModel(**model_config)
    environment = AchillesEnvironment(
        cwd=args.workspace,
        kernel_url=args.kernel_url,
        session_token=args.session_token,
        subject_id=args.subject_id,
        run_id=args.run_id,
    )
    agent = DefaultAgent(model, environment, **agent_config)
    task = args.task.replace(args.workspace, ".")
    task += "\n\nThe repository is the shell's current working directory. Use relative paths."
    result = agent.run(task)
    print("SOAI_MINI_RESULT=" + json.dumps(result, separators=(",", ":")))
    return 0 if result.get("exit_status") == "Submitted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
