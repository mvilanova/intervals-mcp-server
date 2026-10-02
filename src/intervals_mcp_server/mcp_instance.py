"""
Shared MCP instance module.

This module provides a shared FastMCP instance that can be imported by both
the server module and tool modules without creating cyclic imports.
"""

import os
from collections.abc import Mapping
from typing import Any

from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error

from intervals_mcp_server.api.client import setup_api_client

# FastMCP passes explicit defaults (e.g. host="127.0.0.1", port=8000) to its
# settings model, which take precedence over FASTMCP_* environment variables.
# We therefore read the documented variables ourselves and pass them explicitly.
_ENV_STRING_SETTINGS = {
    "FASTMCP_HOST": "host",
    "FASTMCP_LOG_LEVEL": "log_level",
    "FASTMCP_MOUNT_PATH": "mount_path",
    "FASTMCP_SSE_PATH": "sse_path",
    "FASTMCP_STREAMABLE_HTTP_PATH": "streamable_http_path",
}


def fastmcp_settings_from_env(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Build FastMCP keyword arguments from FASTMCP_* environment variables.

    Only variables that are set (and non-empty) are returned, so FastMCP's own
    defaults still apply otherwise.

    Raises:
        ValueError: If FASTMCP_PORT is set but is not a valid integer.
    """
    env = os.environ if environ is None else environ
    settings: dict[str, Any] = {}

    for var, key in _ENV_STRING_SETTINGS.items():
        value = env.get(var, "").strip()
        if value:
            settings[key] = value.upper() if key == "log_level" else value

    port = env.get("FASTMCP_PORT", "").strip()
    if port:
        try:
            settings["port"] = int(port)
        except ValueError as exc:
            raise ValueError(f"FASTMCP_PORT must be an integer, got {port!r}") from exc

    return settings


mcp: FastMCP = FastMCP(  # pylint: disable=invalid-name
    "intervals-icu", lifespan=setup_api_client, **fastmcp_settings_from_env()
)
