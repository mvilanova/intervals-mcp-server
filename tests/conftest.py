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
from collections.abc import Callable
from typing import Any

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")


@pytest.fixture
def patch_request(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., dict[str, Any]]:
    """
    Create a test helper that patches `make_intervals_request` in
    `intervals_mcp_server.api.client` and, when requested, in
    `intervals_mcp_server.tools.<module>`.

    The fixture returns a callable `_patch(payload, tool_module=None)` that:
    - Installs an async replacement which returns the provided `payload` when called.
    - Records the most recent call's positional arguments under `captured["args"]`
      and keyword arguments under `captured["kwargs"]`, and returns that `captured` dict.

    Returns:
        _patch (callable): Function with signature `_patch(payload, tool_module=None) -> dict[str, Any]`.
    """

    def _patch(payload: Any, tool_module: str | None = None) -> dict[str, Any]:
        """
        Create and install a fake `make_intervals_request` that records its last call and returns the provided payload.

        Parameters:
            payload (Any): The value to return when the fake `make_intervals_request` is invoked.
            tool_module (str | None): Optional tool module name; when provided, also patches
                `intervals_mcp_server.tools.<tool_module>.make_intervals_request`.

        Returns:
            dict[str, Any]: A `captured` dictionary updated on each invocation with:
                - `args`: tuple of positional arguments from the last call.
                - `kwargs`: dict of keyword arguments from the last call.
        """
        captured: dict[str, Any] = {}

        async def fake(*args, **kwargs):
            """
            Record the latest call's positional and keyword arguments into the enclosing `captured` dict and return the preset payload.

            Parameters:
                *args: Positional arguments passed by the caller; stored in `captured["args"]`.
                **kwargs: Keyword arguments passed by the caller; stored in `captured["kwargs"]`.

            Returns:
                The original `payload` value supplied to the surrounding patch helper.
            """
            captured["args"] = args
            captured["kwargs"] = kwargs
            return payload

        monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake)
        if tool_module is not None:
            monkeypatch.setattr(
                f"intervals_mcp_server.services.{tool_module}.make_intervals_request",
                fake,
            )
        return captured

    return _patch
