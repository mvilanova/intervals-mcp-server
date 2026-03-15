"""
Shared MCP instance module.

This module provides a shared FastMCP instance that can be imported by both
the server module and tool modules without creating cyclic imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Starts as None, set to a real FastMCP instance by server.py before any tool runs.
# Typed as FastMCP (not FastMCP | None) so tool modules get proper type checking
# on @mcp.tool() calls. The type: ignore suppresses the None assignment mismatch.
mcp: FastMCP = None  # type: ignore[assignment]  # pylint: disable=invalid-name
