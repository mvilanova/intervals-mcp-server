"""Call the get_activities tool directly for a quick connectivity check.

This script loads `.env` if present, imports the `get_activities` tool
from the server module, and invokes it. Run it with the project venv so the
editable package and dependencies are available.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv


def ensure_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)


async def main():
    ensure_env()

    # Import server last so env vars are loaded before it runs any validation
    from intervals_mcp_server import server

    # Use the tool directly
    try:
        # Limit the request to a single day: 25-10-2025
        # Set include_unnamed=True to avoid the shim fetching older activities
        # when there are fewer named activities than the requested limit.
        result = await server.get_activities(
            start_date="2025-10-25",
            end_date="2025-10-25",
            include_unnamed=True,
            limit=100,
        )
        print("Result:\n", result)
    except Exception as e:
        print("Error invoking get_activities:", e)


if __name__ == "__main__":
    asyncio.run(main())
