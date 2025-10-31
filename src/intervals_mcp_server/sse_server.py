"""Wrapper to run the MCP server with an HTTP/SSE transport.

This module imports the existing `server` module which registers tools
on the compatibility shim `mcp` and then re-creates a real
`mcp.server.fastmcp.FastMCP` instance, re-registering the same tool
callables. It exports `mcp` (the real FastMCP instance) so the `mcp`
CLI can import and run it with the SSE transport:

  mcp run -t sse src/intervals_mcp_server/sse_server.py:mcp

This avoids changing the main `server.py` while allowing the project
to listen on TCP (port 8000 by default) for ChatGPT's SSE connector.
"""
from __future__ import annotations

from typing import Any

# Import the module so it registers tools on the shim `mcp` object.
from intervals_mcp_server import server as server_module  # noqa: E402


def _build_real_mcp() -> Any:
    """Create a real FastMCP server and re-register tools from the shim.

    Returns an instance of mcp.server.fastmcp.FastMCP ready to run.
    """
    try:
        from mcp.server.fastmcp import FastMCP as RealFastMCP  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("The `mcp` package is required to run an SSE server.") from exc

    # Build the real FastMCP instance using the same lifespan from server
    real = RealFastMCP("intervals-icu", lifespan=server_module.lifespan)

    # The server_module.mcp is the compatibility shim which collected the tools.
    shim_mcp = getattr(server_module, "mcp", None)
    if shim_mcp is None:
        raise RuntimeError("Could not find shim mcp in server module")

    for tool in shim_mcp.get_tools():
        # Register the callable on the real FastMCP instance. The FastMCP
        # API offers a decorator-style registration; calling tool() and
        # immediately decorating works reliably.
        real.tool()(tool.func)

    return real


# Export the real FastMCP instance as `mcp` so the `mcp` CLI can import it.
mcp = _build_real_mcp()


__all__ = ["mcp"]
