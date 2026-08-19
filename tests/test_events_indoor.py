"""
Tests for the `indoor` flag on add_or_update_event.

The flag maps to the event-level `indoor` boolean on the Intervals.icu events
API. These tests capture the payload sent to the API to assert that the field
is included only when the caller sets it, so that partial updates cannot clear
an existing flag.
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.server import (  # pylint: disable=wrong-import-position
    add_or_update_event,
)


def _capture_event_payload(monkeypatch) -> dict:
    """Patch make_intervals_request and capture the payload sent to the API."""
    captured: dict = {}

    async def fake_request(*_args, **kwargs):
        captured["data"] = kwargs.get("data")
        captured["method"] = kwargs.get("method")
        captured["url"] = kwargs.get("url")
        return {"id": "e123"}

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr("intervals_mcp_server.tools.events.make_intervals_request", fake_request)
    return captured


def test_add_or_update_event_sets_indoor_flag(monkeypatch):
    """indoor=True is sent as a top-level boolean field on the event payload."""
    captured = _capture_event_payload(monkeypatch)

    asyncio.run(
        add_or_update_event(
            athlete_id="i1",
            start_date="2024-01-15",
            name="Trainer session",
            workout_type="Ride",
            indoor=True,
        )
    )

    assert captured["data"]["indoor"] is True
    assert captured["method"] == "POST"


def test_add_or_update_event_clears_indoor_flag(monkeypatch):
    """indoor=False is sent explicitly so the flag can be cleared."""
    captured = _capture_event_payload(monkeypatch)

    asyncio.run(
        add_or_update_event(
            athlete_id="i1",
            event_id="e123",
            start_date="2024-01-15",
            name="Outdoor ride",
            workout_type="Ride",
            indoor=False,
        )
    )

    assert captured["data"]["indoor"] is False
    assert captured["method"] == "PUT"


def test_add_or_update_event_omits_indoor_when_unset(monkeypatch):
    """Omitting indoor leaves the field out of the payload so updates preserve it."""
    captured = _capture_event_payload(monkeypatch)

    asyncio.run(
        add_or_update_event(
            athlete_id="i1",
            event_id="e123",
            start_date="2024-01-15",
            name="Test Workout",
            workout_type="Ride",
        )
    )

    assert "indoor" not in captured["data"]
