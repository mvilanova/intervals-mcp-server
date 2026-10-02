"""Tests for the optional format="json" output of the list tools."""

import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.server import (  # pylint: disable=wrong-import-position
    get_activities,
    get_events,
    get_wellness_data,
)


def _patch(monkeypatch, module: str, payload):
    async def fake_request(*_args, **_kwargs):
        return payload

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(f"intervals_mcp_server.tools.{module}.make_intervals_request", fake_request)

    async def no_gear(*_args, **_kwargs):
        return None

    # Avoid real gear lookups (they would hit the network and share an event loop)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.resolve_gear_for_activities", no_gear
    )


ACTIVITY = {
    "name": "Morning Ride",
    "id": 123,
    "type": "Ride",
    "startTime": "2024-01-01T08:00:00Z",
    "distance": 1000,
    "duration": 3600,
    "icu_average_watts": 210,
}


def test_activities_json(monkeypatch):
    _patch(monkeypatch, "activities", [ACTIVITY])
    result = asyncio.run(get_activities(athlete_id="1", limit=1, format="json"))
    data = json.loads(result)
    assert data[0]["name"] == "Morning Ride"
    assert data[0]["id"] == 123
    assert data[0]["distance_m"] == 1000
    assert data[0]["duration_s"] == 3600
    assert data[0]["average_power_w"] == 210
    assert "moving_time_s" not in data[0]


def test_activities_text_default_unchanged(monkeypatch):
    _patch(monkeypatch, "activities", [ACTIVITY])
    default = asyncio.run(get_activities(athlete_id="1", limit=1))
    explicit = asyncio.run(get_activities(athlete_id="1", limit=1, format="text"))
    assert default == explicit
    assert default.startswith("Activities:")


def test_activities_json_empty(monkeypatch):
    _patch(monkeypatch, "activities", [])
    assert asyncio.run(get_activities(athlete_id="1", format="json")) == "[]"


def test_events_json(monkeypatch):
    event = {
        "date": "2024-01-01",
        "id": "e1",
        "name": "Race",
        "description": "d",
        "category": "RACE_A",
    }
    _patch(monkeypatch, "events", [event])
    data = json.loads(asyncio.run(get_events(athlete_id="1", format="json")))
    assert data == [
        {
            "id": "e1",
            "date": "2024-01-01",
            "name": "Race",
            "description": "d",
            "category": "RACE_A",
            "kind": "race",
        }
    ]


def test_wellness_json_list_and_dict(monkeypatch):
    entry = {
        "id": "2026-04-08",
        "restingHR": 48,
        "sleepSecs": 27000,
        "hrv": 70.5,
        "locked": None,
        "x": 1,
    }
    _patch(monkeypatch, "wellness", [entry])
    data = json.loads(asyncio.run(get_wellness_data(athlete_id="1", format="json")))
    assert data == [{"date": "2026-04-08", "resting_hr": 48, "sleep_secs": 27000, "hrv": 70.5}]

    data = json.loads(
        asyncio.run(get_wellness_data(athlete_id="1", format="json", include_all_fields=True))
    )
    assert data[0]["other_fields"] == {"x": 1}

    _patch(monkeypatch, "wellness", {"2026-04-09": {"weight": 70}})
    data = json.loads(asyncio.run(get_wellness_data(athlete_id="1", format="json")))
    assert data == [{"date": "2026-04-09", "weight": 70}]


def test_invalid_format(monkeypatch):
    _patch(monkeypatch, "activities", [ACTIVITY])
    for tool in (get_activities, get_events, get_wellness_data):
        result = asyncio.run(tool(athlete_id="1", format="xml"))  # type: ignore[arg-type]
        assert result.startswith("Error: invalid format 'xml'")
        assert "text, json" in result


def test_events_text_golden(monkeypatch):
    """Default text output is byte-for-byte what the pre-existing formatter produced."""
    event = {
        "date": "2024-01-01",
        "id": "e1",
        "name": "Test Event",
        "description": "desc",
        "race": True,
    }
    _patch(monkeypatch, "events", [event])
    expected = (
        "Events:\n\nDate: 2024-01-01\nID: e1\nType: Race\nName: Test Event\nDescription: desc\n\n"
    )
    assert asyncio.run(get_events(athlete_id="1")) == expected
