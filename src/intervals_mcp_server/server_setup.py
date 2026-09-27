"""
Server setup and initialization for Intervals.icu MCP Server.

This module handles transport configuration and server startup logic.
"""

import os
import logging
from typing import Any

from mcp.server.mcpserver import MCPServer  # pylint: disable=import-error

from intervals_mcp_server.utils.types import TransportAliases

logger = logging.getLogger("intervals_icu_mcp_server")


def setup_transport() -> TransportAliases:
    """
    Setup and validate the MCP transport configuration.

    Reads MCP_TRANSPORT environment variable and validates it against
    supported transport types.

    Returns:
        TransportAliases: The selected transport type.

    Raises:
        ValueError: If the transport type is not supported.
    """
    transport_env = os.getenv("MCP_TRANSPORT", TransportAliases.STDIO.value).lower()
    try:
        transport_alias = TransportAliases(transport_env)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in TransportAliases)
        raise ValueError(f"Unsupported MCP_TRANSPORT value. Use one of: {allowed}.") from exc

    # Map HTTP to STREAMABLE_HTTP
    selected_transport = (
        TransportAliases.STREAMABLE_HTTP
        if transport_alias == TransportAliases.HTTP
        else transport_alias
    )

    return selected_transport


def _transport_settings() -> dict[str, Any]:
    """
    Read HTTP transport settings from the environment.

    mcp<2 read these FASTMCP_* variables into FastMCP.settings automatically. mcp>=2
    takes them as arguments to run() instead, so read them here to keep existing
    configurations working.
    """
    return {
        "host": os.getenv("FASTMCP_HOST", "127.0.0.1"),
        "port": int(os.getenv("FASTMCP_PORT", "8000")),
        "sse_path": os.getenv("FASTMCP_SSE_PATH", "/sse"),
        "message_path": os.getenv("FASTMCP_MESSAGE_PATH", "/messages/"),
        "streamable_http_path": os.getenv("FASTMCP_STREAMABLE_HTTP_PATH", "/mcp"),
    }


def start_server(mcp_instance: MCPServer, transport: TransportAliases) -> None:
    """
    Start the MCP server with the specified transport.

    Args:
        mcp_instance (MCPServer): The MCPServer instance to start.
        transport (TransportAliases): The transport type to use.
    """
    settings = _transport_settings()
    host = settings["host"]
    port = settings["port"]

    if transport == TransportAliases.STDIO:
        logger.info("Starting MCP server with stdio transport.")
        mcp_instance.run()
    elif transport == TransportAliases.SSE:
        mount_path = os.getenv("MCP_SSE_MOUNT_PATH")
        logger.info(
            "Starting MCP server with SSE transport at http://%s:%s%s (messages: %s).",
            host,
            port,
            settings["sse_path"],
            settings["message_path"],
        )
        if mount_path:
            # mcp>=2 dropped run(mount_path=...); the SSE transport now derives the
            # message endpoint advertised to clients from the ASGI root_path instead.
            import uvicorn  # pylint: disable=import-outside-toplevel

            app = mcp_instance.sse_app(
                sse_path=settings["sse_path"], message_path=settings["message_path"], host=host
            )
            uvicorn.run(
                app,
                host=host,
                port=port,
                root_path=mount_path.rstrip("/"),
                log_level=mcp_instance.settings.log_level.lower(),
            )
        else:
            mcp_instance.run(
                transport="sse",
                host=host,
                port=port,
                sse_path=settings["sse_path"],
                message_path=settings["message_path"],
            )
    else:  # STREAMABLE_HTTP
        logger.info(
            "Starting MCP server with Streamable HTTP transport at http://%s:%s%s.",
            host,
            port,
            settings["streamable_http_path"],
        )
        mcp_instance.run(
            transport="streamable-http",
            host=host,
            port=port,
            streamable_http_path=settings["streamable_http_path"],
        )
