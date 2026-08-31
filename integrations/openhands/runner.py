from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from openhands.sdk import LLM, Agent, Conversation
from openhands.sdk.mcp.config import MCPServer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--mcp-python", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--step-limit", type=int, default=18)
    args = parser.parse_args()

    bridge_env = {
        "PYTHONPATH": str(Path(args.repo_root) / "src"),
        "SOAI_MCP_AGENT_PROFILE_ID": args.subject_id,
        "SOAI_MCP_WORKSPACE": args.workspace,
        "SOAI_MCP_RUN_ID": args.run_id,
    }
    for key in ("SOVEREIGN_CONFIG_ROOT", "SOVEREIGN_STATE_DIR", "SOVEREIGN_RUNTIME_DIR"):
        if value := os.environ.get(key):
            bridge_env[key] = value

    llm = LLM(
        model=f"openai/{args.model}",
        api_key="local-backend-no-key-required",
        base_url=args.base_url,
        api_mode="chat",
        max_output_tokens=4096,
        timeout=120,
        num_retries=1,
        retry_min_wait=1,
        retry_max_wait=2,
    )
    agent = Agent(
        llm=llm,
        tools=[],
        # Finish/Think are internal conversation controls, not authority-bearing I/O.
        include_default_tools=["FinishTool", "ThinkTool"],
        mcp_config={
            "achilles": MCPServer(
                transport="stdio",
                command=args.mcp_python,
                args=["-m", "sovereign_ai.agents.mcp_bridge"],
                env=bridge_env,
                cwd=args.repo_root,
                timeout=30,
            )
        },
    )
    conversation = Conversation(
        agent=agent,
        workspace=args.workspace,
        persistence_dir=None,
        max_iteration_per_run=args.step_limit,
        visualizer=None,
        delete_on_close=True,
    )
    try:
        task = args.task.replace(args.workspace, ".")
        task += (
            "\n\nThe repository is the current workspace. Use only the Achilles MCP "
            "tools for repository inspection, commands, and edits. Use relative paths. "
            "Call finish when the implementation is complete."
        )
        conversation.send_message(task)
        conversation.run()
        stats = conversation.conversation_stats
        result = {
            "status": str(conversation.state.execution_status),
            "events": len(conversation.state.events),
            "stats": stats.model_dump(mode="json") if hasattr(stats, "model_dump") else str(stats),
        }
        print("SOAI_OPENHANDS_RESULT=" + json.dumps(result, separators=(",", ":")))
        return 0
    finally:
        conversation.close()


if __name__ == "__main__":
    raise SystemExit(main())
