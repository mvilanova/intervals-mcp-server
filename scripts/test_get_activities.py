"""Call the get_activities tool directly for a quick connectivity check.

This script loads `.env` if present, imports the `get_activities` tool
from the server module, and invokes it. Run it with the project venv so the
editable package and dependencies are available.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client


def ensure_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)


async def call_local(start_date: str, end_date: str, limit: int, include_unnamed: bool) -> None:
    ensure_env()

    # Import server after loading env so validation runs with the right vars.
    from intervals_mcp_server import server

    result = await server.get_activities(
        start_date=start_date,
        end_date=end_date,
        include_unnamed=include_unnamed,
        limit=limit,
    )
    print("Result:\n", result)


async def call_remote(
    base_url: str,
    start_date: str,
    end_date: str,
    limit: int,
    include_unnamed: bool,
) -> None:
    sse_url = base_url.rstrip("/") + "/sse/"
    print(f"Connecting to {sse_url} via MCP SSE...")

    async with sse_client(sse_url, timeout=10.0, sse_read_timeout=300.0) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            arguments = {
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
                "include_unnamed": include_unnamed,
            }

            try:
                result = await session.call_tool("get_activities", arguments=arguments)
            except Exception as exc:  # noqa: BLE001 - surface raw failure for debugging
                print("Error calling tool:", exc)
                return

            if result.isError:
                print("Server reported an error response.")

            texts: list[str] = []
            for content in result.content:
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


async def main():
    parser = argparse.ArgumentParser(description="Test get_activities locally or via MCP SSE.")
    parser.add_argument("--base-url", help="Optional ngrok HTTPS base URL to call via SSE.")
    parser.add_argument("--start-date", default="2025-10-25")
    parser.add_argument("--end-date", default="2025-10-25")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--include-unnamed",
        dest="include_unnamed",
        action="store_true",
        help="Include unnamed activities (default).",
    )
    parser.add_argument(
        "--exclude-unnamed",
        dest="include_unnamed",
        action="store_false",
        help="Exclude unnamed activities from the response.",
    )
    parser.set_defaults(include_unnamed=True)
    args = parser.parse_args()

    if args.base_url:
        await call_remote(
            base_url=args.base_url,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            include_unnamed=args.include_unnamed,
        )
    else:
        await call_local(
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            include_unnamed=args.include_unnamed,
        )


if __name__ == "__main__":
    asyncio.run(main())
