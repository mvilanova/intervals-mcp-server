"""Smoke test: import the MCP server module and print registered tool names.

This script does NOT start any server; it only imports `server` so the
module-level `@mcp.tool()` decorators run and tools are registered on the
compat shim. It then prints the list of registered tool names.
"""
from __future__ import annotations

import json

from intervals_mcp_server import server


def main() -> None:
    m = server.mcp
    try:
        tools = m.get_tools()
    except Exception as e:
        print("Error retrieving tools:", e)
        raise

    names = [t.name for t in tools]
    print(json.dumps({"registered_tools": names}, indent=2))


if __name__ == "__main__":
    main()
