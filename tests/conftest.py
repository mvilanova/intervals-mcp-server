"""Shared pytest configuration for the intervals_mcp_server test suite.

Auto-loaded by pytest before collection. Centralizes the sys.path / env
bootstrap that the server module needs at import time, and exposes a
`patch_request` fixture that replaces the ~22 hand-rolled monkeypatch
blocks scattered across test files.
"""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Any

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")


@pytest.fixture
def patch_request(monkeypatch):
    """Patch `make_intervals_request` in both `api.client` and a tools module.

    Every test in `test_server.py` needs the same dual monkeypatch: the
    function is imported into `intervals_mcp_server.api.client` and then
    re-bound into each `intervals_mcp_server.tools.<module>` namespace.
    Patching only the source leaves the tool's bound reference stale.

    Usage:
        captured = patch_request(payload, "activities")
        result = asyncio.run(get_activities(...))
        assert captured["kwargs"]["method"] == "POST"

    The returned dict is populated on every call with the most recent
    positional `args` and keyword `kwargs`; tests that don't care about
    the call shape can ignore the return value.
    """

    def _patch(payload: Any, tool_module: str | None = None) -> dict[str, Any]:
        captured: dict[str, Any] = {}

        async def fake(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return payload

        monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake)
        if tool_module is not None:
            monkeypatch.setattr(
                f"intervals_mcp_server.tools.{tool_module}.make_intervals_request",
                fake,
            )
        return captured

    return _patch
