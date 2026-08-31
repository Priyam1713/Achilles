from __future__ import annotations

import argparse

from sovereign_ai.agents.mcp_bridge import mcp


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    mcp.settings.host = "127.0.0.1"
    mcp.settings.port = args.port
    mcp.settings.streamable_http_path = "/mcp"
    mcp.settings.stateless_http = True
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
