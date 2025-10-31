"""Minimal MCP SSE client for quick tool invocations.

This script connects to an MCP server that exposes an SSE transport (like the
ngrok tunnel you just tested) and lets you list tools or call a tool with
arguments. Example usage:

    python scripts/quick_mcp_client.py --base-url https://<id>.ngrok-free.dev list

    python scripts/quick_mcp_client.py --base-url https://<id>.ngrok-free.dev \
        call get_activities start_date=2025-10-25 end_date=2025-10-25 limit=5

Arguments can be passed as key=value pairs (simple coercion for bool/int/float)
or key:=<json> for explicit JSON parsing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client


def _load_env() -> None:
    """Load .env alongside the project if present."""

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _coerce_scalar(value: str) -> Any:
    """Coerce plain key=value strings to basic Python types."""

    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"

    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _parse_kv_pairs(pairs: list[str]) -> dict[str, Any]:
    """Parse CLI key=value or key:=json style arguments."""

    result: dict[str, Any] = {}
    for pair in pairs:
        if ":=" in pair:
            key, raw = pair.split(":=", 1)
            result[key] = json.loads(raw)
        elif "=" in pair:
            key, raw = pair.split("=", 1)
            result[key] = _coerce_scalar(raw)
        else:
            raise ValueError(
                f"Invalid argument format '{pair}'. Use key=value or key:=<json>."
            )
    return result


def _render_call_result(result: Any) -> None:
    """Print the textual parts of a CallToolResult."""

    if getattr(result, "isError", False):
        print("Server reported an error response.")

    texts: list[str] = []
    for content in getattr(result, "content", []):
        ctype = getattr(content, "type", "")
        if ctype == "text":
            texts.append(getattr(content, "text", ""))
        elif ctype == "resource" and getattr(content, "resource", None):
            resource = content.resource
            text_value = getattr(resource, "text", None) or getattr(resource, "content", None)
            if isinstance(text_value, str):
                texts.append(text_value)

    if texts:
        print("\n\n".join(texts))
    else:
        print("No plain-text content returned; raw result follows:")
        print(result)


async def _run_list(session: ClientSession) -> None:
    response = await session.list_tools()
    print("Available tools:")
    for tool in response.tools:
        summary = tool.description or "(no description)"
        print(f"- {tool.name}: {summary}")


async def _run_call(session: ClientSession, tool: str, arguments: dict[str, Any]) -> None:
    result = await session.call_tool(tool, arguments=arguments)
    _render_call_result(result)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Quick MCP SSE client")
    parser.add_argument("--base-url", required=True, help="HTTPS base URL (no trailing /sse)")
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Connection timeout in seconds (default: 10).",
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=300.0,
        help="SSE read timeout in seconds (default: 300).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List tools exposed by the server")

    call_parser = subparsers.add_parser("call", help="Call a specific tool")
    call_parser.add_argument("tool_name")
    call_parser.add_argument(
        "arguments",
        nargs="*",
        help="Tool arguments as key=value or key:=<json>",
    )

    args = parser.parse_args()

    _load_env()

    sse_url = args.base_url.rstrip("/") + "/sse/"
    async with sse_client(
        sse_url,
        timeout=args.timeout,
        sse_read_timeout=args.read_timeout,
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            if args.command == "list":
                await _run_list(session)
                return

            if args.command == "call":
                try:
                    parsed_args = _parse_kv_pairs(args.arguments)
                except ValueError as exc:
                    parser.error(str(exc))
                await _run_call(session, args.tool_name, parsed_args)
                return

            parser.error("Unknown command")


if __name__ == "__main__":
    asyncio.run(main())
