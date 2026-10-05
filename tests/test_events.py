"""
Tests for the payloads the event tools send to Intervals.icu (no network).

An update must only send the fields the caller passed: a PUT with null values or a
default category would clear descriptions or turn notes into workouts.
"""

# pylint: disable=missing-function-docstring

import asyncio
import os
import pathlib
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.tools import events as events_module  # pylint: disable=wrong-import-position  # noqa: E402
from intervals_mcp_server.tools.events import add_or_update_event, add_or_update_note  # pylint: disable=wrong-import-position  # noqa: E402


def _capture_requests(monkeypatch):
    """Replace the API call and record url, method and payload of every request."""
    calls = []

    async def fake_request(url, api_key=None, params=None, method="GET", data=None):  # pylint: disable=unused-argument
        calls.append({"url": url, "method": method, "data": data})
        return {"id": "e1"}

    monkeypatch.setattr(events_module, "make_intervals_request", fake_request)
    return calls


def test_request_drops_none_values_on_put(monkeypatch):
    calls = _capture_requests(monkeypatch)
    payload = {"name": "X", "description": None, "moving_time": None, "distance": None, "type": "Ride"}
    asyncio.run(events_module._create_or_update_event_request("i1", None, payload, None, "e1"))  # pylint: disable=protected-access
    assert calls == [{"url": "/athlete/i1/events/e1", "method": "PUT", "data": {"name": "X", "type": "Ride"}}]


def test_update_with_name_and_type_keeps_description_date_and_category(monkeypatch):
    calls = _capture_requests(monkeypatch)
    result = asyncio.run(add_or_update_event(name="Renamed", workout_type="Ride", athlete_id="i1", event_id="e1"))
    assert result == "Successfully updated event id: e1"
    assert calls == [{"url": "/athlete/i1/events/e1", "method": "PUT", "data": {"name": "Renamed", "type": "Ride"}}]


def test_update_without_workout_type_only_renames(monkeypatch):
    calls = _capture_requests(monkeypatch)
    asyncio.run(add_or_update_event(name="Renamed", athlete_id="i1", event_id="e1"))
    assert calls[0]["data"] == {"name": "Renamed"}


def test_update_sends_explicitly_passed_fields(monkeypatch):
    calls = _capture_requests(monkeypatch)
    asyncio.run(
        add_or_update_event(
            name="Gravel race",
            athlete_id="i1",
            event_id="e1",
            start_date="2026-10-25",
            moving_time=18000,
            category="RACE_B",
        )
    )
    assert calls[0]["data"] == {
        "start_date_local": "2026-10-25T00:00:00",
        "category": "RACE_B",
        "name": "Gravel race",
        "moving_time": 18000,
    }


def test_create_defaults_to_workout_today_and_inferred_type(monkeypatch):
    calls = _capture_requests(monkeypatch)
    result = asyncio.run(add_or_update_event(name="Easy Run", athlete_id="i1"))
    assert result == "Successfully created event id: e1"
    assert calls == [
        {
            "url": "/athlete/i1/events",
            "method": "POST",
            "data": {
                "start_date_local": datetime.now().strftime("%Y-%m-%d") + "T00:00:00",
                "category": "WORKOUT",
                "name": "Easy Run",
                "type": "Run",
            },
        }
    ]


def test_update_rejects_invalid_date(monkeypatch):
    calls = _capture_requests(monkeypatch)
    result = asyncio.run(add_or_update_event(name="X", athlete_id="i1", event_id="e1", start_date="25.10.2026"))
    assert result.startswith("Error: Invalid date format")
    assert not calls


def test_note_create_sets_category_date_and_default_color(monkeypatch):
    calls = _capture_requests(monkeypatch)
    asyncio.run(add_or_update_note(name="Rest", description="Ruhetag", start_date="2026-09-28", athlete_id="i1"))
    assert calls[0]["method"] == "POST"
    assert calls[0]["data"] == {
        "category": "NOTE",
        "name": "Rest",
        "description": "Ruhetag",
        "start_date_local": "2026-09-28T00:00:00",
        "color": "green",
    }


def test_note_update_keeps_category_color_and_date(monkeypatch):
    calls = _capture_requests(monkeypatch)
    asyncio.run(add_or_update_note(name="Rest", description="Neu", athlete_id="i1", event_id="n1"))
    assert calls == [{"url": "/athlete/i1/events/n1", "method": "PUT", "data": {"name": "Rest", "description": "Neu"}}]
