"""
Unit tests for the main MCP server tool functions in intervals_mcp_server.server.

These tests use monkeypatching to mock API responses and verify the formatting and output of each tool function:
- get_activities
- get_activity_details
- get_activity_intervals
- get_activity_streams
- get_activity_messages
- add_activity_message
- get_events
- get_event_by_id
- add_or_update_event
- get_wellness_data

The tests ensure that the server's public API returns expected strings and handles data correctly.
"""

import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.server import (  # pylint: disable=wrong-import-position
    add_activity_message,
    get_activities,
    get_activity_details,
    get_activity_intervals,
    get_activity_messages,
    get_activity_streams,
    add_events_bulk,
    add_or_update_event,
    get_athlete_power_curves,
    get_event_by_id,
    get_events,
    get_gear_list,
    get_wellness_data,
    get_custom_items,
    get_custom_item_by_id,
    create_custom_item,
    update_custom_item,
    delete_custom_item,
)
from intervals_mcp_server.tools import gear as gear_module  # pylint: disable=wrong-import-position
from tests.sample_data import INTERVALS_DATA, POWER_CURVES_DATA  # pylint: disable=wrong-import-position


def _reset_gear_cache():
    """Helper to clear the module-level gear cache between tests."""
    gear_module._GEAR_RAW_CACHE.clear()  # pylint: disable=protected-access


def test_get_activities(monkeypatch):
    """
    Test get_activities returns a formatted string containing activity details when given a sample activity.
    """
    sample = {
        "name": "Morning Ride",
        "id": 123,
        "type": "Ride",
        "startTime": "2024-01-01T08:00:00Z",
        "distance": 1000,
        "duration": 3600,
    }

    async def fake_request(*_args, **_kwargs):
        return [sample]

    # Patch in both api.client and tools modules to ensure it works
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(get_activities(athlete_id="1", limit=1, include_unnamed=True))
    assert "Morning Ride" in result
    assert "Activities:" in result


def test_get_activity_details(monkeypatch):
    """
    Test get_activity_details returns a formatted string with the activity name and details.
    """
    sample = {
        "name": "Morning Ride",
        "id": 123,
        "type": "Ride",
        "startTime": "2024-01-01T08:00:00Z",
        "distance": 1000,
        "duration": 3600,
    }

    async def fake_request(*_args, **_kwargs):
        return sample

    # Patch in both api.client and tools modules to ensure it works
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(get_activity_details(123))
    assert "Activity: Morning Ride" in result


def test_get_events(monkeypatch):
    """
    Test get_events returns a formatted string containing event details when given a sample event.
    """
    event = {
        "date": "2024-01-01",
        "id": "e1",
        "name": "Test Event",
        "description": "desc",
        "race": True,
    }

    async def fake_request(*_args, **_kwargs):
        return [event]

    # Patch in both api.client and tools modules to ensure it works
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr("intervals_mcp_server.tools.events.make_intervals_request", fake_request)
    result = asyncio.run(get_events(athlete_id="1", start_date="2024-01-01", end_date="2024-01-02"))
    assert "Test Event" in result
    assert "Events:" in result


def test_get_event_by_id(monkeypatch):
    """
    Test get_event_by_id returns a formatted string with event details for a given event ID.
    """
    event = {
        "id": "e1",
        "date": "2024-01-01",
        "name": "Test Event",
        "description": "desc",
        "race": True,
    }

    async def fake_request(*_args, **_kwargs):
        return event

    # Patch in both api.client and tools modules to ensure it works
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr("intervals_mcp_server.tools.events.make_intervals_request", fake_request)
    result = asyncio.run(get_event_by_id("e1", athlete_id="1"))
    assert "Event Details:" in result
    assert "Test Event" in result


def test_get_wellness_data(monkeypatch):
    """
    Test get_wellness_data returns a formatted string containing wellness data for a given athlete.
    """
    wellness = {
        "2024-01-01": {
            "id": "2024-01-01",
            "ctl": 75,
            "sleepSecs": 28800,
        }
    }

    async def fake_request(*_args, **_kwargs):
        return wellness

    # Patch in both api.client and tools modules to ensure it works
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr("intervals_mcp_server.tools.wellness.make_intervals_request", fake_request)
    result = asyncio.run(get_wellness_data(athlete_id="1"))
    assert "Wellness Data:" in result
    assert "2024-01-01" in result


def test_get_wellness_data_renders_macros(monkeypatch):
    """
    Integration test: native nutrition macros (carbohydrates, protein,
    fatTotal) flow from the API response through get_wellness_data into the
    formatted output.
    """
    wellness = [
        {
            "id": "2026-04-08",
            "carbohydrates": 310,
            "protein": 145,
            "fatTotal": 72,
        }
    ]

    async def fake_request(*_args, **_kwargs):
        return wellness

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr("intervals_mcp_server.tools.wellness.make_intervals_request", fake_request)
    result = asyncio.run(get_wellness_data(athlete_id="1"))
    assert "Wellness Data:" in result
    assert "2026-04-08" in result
    assert "Nutrition & Hydration:" in result
    assert "- Carbohydrates: 310 g" in result
    assert "- Protein: 145 g" in result
    assert "- Fat: 72 g" in result


def test_get_wellness_data_include_all_fields(monkeypatch):
    """
    Test get_wellness_data with include_all_fields=True returns a formatted string including additional fields.
    """
    wellness = [
        {
            "id": "2024-01-01",
            "ctl": 75,
            "sleepSecs": 28800,
            "customField": "custom_value",
        }
    ]

    async def fake_request(*_args, **_kwargs):
        return wellness

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr("intervals_mcp_server.tools.wellness.make_intervals_request", fake_request)
    result = asyncio.run(get_wellness_data(athlete_id="1", include_all_fields=True))
    assert "Wellness Data:" in result
    assert "2024-01-01" in result
    assert "Fitness (CTL): 75" in result
    assert "Other Fields:" in result
    assert "customField: custom_value" in result


def test_get_activity_intervals(monkeypatch):
    """
    Test get_activity_intervals returns a formatted string with interval analysis for a given activity.
    """

    async def fake_request(*_args, **_kwargs):
        return INTERVALS_DATA

    # Patch in both api.client and tools modules to ensure it works
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(get_activity_intervals("123"))
    assert "Intervals Analysis:" in result
    assert "Rep 1" in result


def test_get_activity_streams(monkeypatch):
    """
    Test get_activity_streams returns a formatted string with stream data for a given activity.
    """
    sample_streams = [
        {
            "type": "time",
            "name": "time",
            "data": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "data2": [],
            "valueType": "time_units",
            "valueTypeIsArray": False,
            "anomalies": None,
            "custom": False,
        },
        {
            "type": "watts",
            "name": "watts",
            "data": [150, 155, 160, 165, 170, 175, 180, 185, 190, 195, 200],
            "data2": [],
            "valueType": "power_units",
            "valueTypeIsArray": False,
            "anomalies": None,
            "custom": False,
        },
        {
            "type": "heartrate",
            "name": "heartrate",
            "data": [120, 125, 130, 135, 140, 145, 150, 155, 160, 165, 170],
            "data2": [],
            "valueType": "hr_units",
            "valueTypeIsArray": False,
            "anomalies": None,
            "custom": False,
        },
    ]

    async def fake_request(*_args, **_kwargs):
        return sample_streams

    # Patch in both api.client and tools modules to ensure it works
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(get_activity_streams("i107537962"))
    assert "Activity Streams" in result
    assert "time" in result
    assert "watts" in result
    assert "heartrate" in result
    assert "Data Points: 11" in result


def test_add_or_update_event(monkeypatch):
    """
    Test add_or_update_event successfully posts an event and returns the response data.
    """
    expected_response = {
        "id": "e123",
        "start_date_local": "2024-01-15T00:00:00",
        "category": "WORKOUT",
        "name": "Test Workout",
        "type": "Ride",
    }

    async def fake_post_request(*_args, **_kwargs):
        return expected_response

    # Patch in both api.client and tools modules to ensure it works
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_post_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.events.make_intervals_request", fake_post_request
    )
    result = asyncio.run(
        add_or_update_event(
            athlete_id="i1", start_date="2024-01-15", name="Test Workout", workout_type="Ride"
        )
    )
    assert "Successfully created event id:" in result
    assert "e123" in result


def _bulk_capture(monkeypatch, response):
    """Patch the events request function and capture the calls."""
    calls: list[dict] = []

    async def fake_request(*_args, **kwargs):
        calls.append(kwargs)
        return response

    monkeypatch.setattr("intervals_mcp_server.tools.events.make_intervals_request", fake_request)
    return calls


def test_add_events_bulk_happy_path(monkeypatch):
    """Valid entries are sent in one bulk request; ids are matched by order."""
    calls = _bulk_capture(monkeypatch, [{"id": 11}, {"id": 12}])
    result = json.loads(
        asyncio.run(
            add_events_bulk(
                athlete_id="i1",
                events=[
                    {
                        "name": "Easy run",
                        "start_date": "2025-01-06",
                        "workout_type": "Run",
                        "moving_time": 2700,
                        "workout_doc": {"steps": [{"duration": 600, "text": "Warmup"}]},
                    },
                    {
                        "name": "Rest",
                        "start_date": "2025-01-07",
                        "category": "NOTE",
                        "description": "Full rest",
                    },
                ],
            )
        )
    )
    assert len(calls) == 1
    assert calls[0]["url"] == "/athlete/i1/events/bulk"
    assert calls[0]["method"] == "POST"
    assert calls[0]["params"] == {"upsert": False, "upsertOnUid": False, "updatePlanApplied": False}
    body = calls[0]["data"]
    assert body[0]["category"] == "WORKOUT"
    assert body[0]["type"] == "Run"
    assert body[0]["start_date_local"] == "2025-01-06T00:00:00"
    assert body[0]["moving_time"] == 2700
    assert "Warmup" in body[0]["description"]
    assert body[1]["category"] == "NOTE"
    assert body[1]["description"] == "Full rest"
    assert result["created"] == [
        {"index": 0, "id": 11, "name": "Easy run", "start_date_local": None},
        {"index": 1, "id": 12, "name": "Rest", "start_date_local": None},
    ]
    assert result["errors"] == []


def test_add_events_bulk_matches_single_event_body(monkeypatch):
    """Bulk workout body is identical to the body add_or_update_event sends."""
    calls = _bulk_capture(monkeypatch, [{"id": 1}])
    asyncio.run(
        add_or_update_event(
            athlete_id="i1", start_date="2025-01-06", name="Easy run", workout_type="Run"
        )
    )
    asyncio.run(
        add_events_bulk(
            athlete_id="i1",
            events=[{"name": "Easy run", "start_date": "2025-01-06", "workout_type": "Run"}],
        )
    )
    assert calls[0]["data"] == calls[1]["data"][0]


def test_add_events_bulk_invalid_entries_not_sent(monkeypatch):
    """If any entry is invalid, nothing is sent and all errors are reported per index."""
    calls = _bulk_capture(monkeypatch, [{"id": 5}])
    result = json.loads(
        asyncio.run(
            add_events_bulk(
                athlete_id="i1",
                events=[
                    {"name": "Bad date", "start_date": "06.01.2025", "workout_type": "Run"},
                    {"name": "Ok", "start_date": "2025-01-06", "workout_type": "Run"},
                    {"start_date": "2025-01-06", "workout_type": "Run"},
                    {"name": "No type", "start_date": "2025-01-06"},
                    {"name": "Note", "start_date": "2025-01-06", "category": "NOTE"},
                    {"name": "Typo", "start_date": "2025-01-06", "workout_type": "Run", "foo": 1},
                    {"name": "Color", "start_date": "2025-01-06", "workout_type": "Run", "color": "red"},
                    {"name": "N", "start_date": "2025-01-06", "category": "NOTE", "description": "d", "distance": 5},
                    {
                        "name": "Both",
                        "start_date": "2025-01-06",
                        "workout_type": "Run",
                        "description": "x",
                        "workout_doc": {"steps": []},
                    },
                    {
                        "name": "BadDoc",
                        "start_date": "2025-01-06",
                        "workout_type": "Run",
                        "workout_doc": {"steps": [42]},
                    },
                ],
            )
        )
    )
    assert calls == []
    assert result["created"] == []
    assert result["created_count"] == 0
    assert [e["index"] for e in result["errors"]] == [0, 2, 3, 4, 5, 6, 7, 8, 9]


def test_add_events_bulk_reports_all_problems_of_an_entry(monkeypatch):
    """Every problem of one entry is reported, not only the first one."""
    calls = _bulk_capture(monkeypatch, [])
    result = json.loads(
        asyncio.run(
            add_events_bulk(
                athlete_id="i1",
                events=[{"name": "Missing date and type", "moving_time": "1h"}],
            )
        )
    )
    assert calls == []
    error = result["errors"][0]["error"]
    assert "'start_date' is required" in error
    assert "'workout_type' is required for category WORKOUT" in error
    assert "'moving_time' must be an integer" in error


def test_add_events_bulk_workout_description(monkeypatch):
    """A WORKOUT description without workout_doc is sent as the workout text."""
    calls = _bulk_capture(monkeypatch, [{"id": 1, "name": "Server name", "start_date_local": "2025-01-06T00:00:00"}])
    result = json.loads(
        asyncio.run(
            add_events_bulk(
                athlete_id="i1",
                events=[
                    {
                        "name": "Mine",
                        "start_date": "2025-01-06",
                        "workout_type": "Run",
                        "description": "- 10m 60%",
                    }
                ],
            )
        )
    )
    assert calls[0]["data"][0]["description"] == "- 10m 60%"
    assert result["created"][0]["name"] == "Server name"
    assert result["created"][0]["start_date_local"] == "2025-01-06T00:00:00"


def test_add_events_bulk_all_invalid_makes_no_request(monkeypatch):
    """No API call is made when every entry is invalid."""
    calls = _bulk_capture(monkeypatch, [])
    result = json.loads(asyncio.run(add_events_bulk(athlete_id="i1", events=[{"name": "x"}])))
    assert calls == []
    assert result["created"] == []
    assert result["error_count"] == 1


def test_add_events_bulk_empty_list(monkeypatch):
    """An empty list returns an error without a request."""
    calls = _bulk_capture(monkeypatch, [])
    result = asyncio.run(add_events_bulk(athlete_id="i1", events=[]))
    assert result.startswith("Error")
    assert calls == []


def test_add_events_bulk_api_error(monkeypatch):
    """A failing bulk request is reported as an API error."""
    _bulk_capture(monkeypatch, {"error": True, "message": "boom"})
    result = asyncio.run(
        add_events_bulk(
            athlete_id="i1",
            events=[{"name": "Ok", "start_date": "2025-01-06", "workout_type": "Run"}],
        )
    )
    assert "Error creating events in bulk: boom" in result
    assert "may have been partially or fully created" in result


def test_get_activity_messages(monkeypatch):
    """Test get_activity_messages returns formatted messages for an activity."""
    sample_messages = [
        {
            "id": 1,
            "name": "Niko",
            "created": "2024-06-15T10:30:00Z",
            "type": "NOTE",
            "content": "Legs felt heavy today",
        },
        {
            "id": 2,
            "name": "Coach",
            "created": "2024-06-15T11:00:00Z",
            "type": "TEXT",
            "content": "Good effort despite that!",
        },
    ]

    async def fake_request(*_args, **_kwargs):
        return sample_messages

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(get_activity_messages(activity_id="i123"))
    assert "Legs felt heavy today" in result
    assert "Good effort despite that!" in result
    assert "Niko" in result
    assert "Coach" in result


def test_get_activity_messages_error(monkeypatch):
    """Test get_activity_messages handles API errors gracefully."""

    async def fake_request(*_args, **_kwargs):
        return {"error": True, "message": "Activity not found"}

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(get_activity_messages(activity_id="i999"))
    assert "Error fetching activity messages" in result
    assert "Activity not found" in result


def test_get_activity_messages_empty(monkeypatch):
    """Test get_activity_messages returns appropriate message when no messages exist."""

    async def fake_request(*_args, **_kwargs):
        return []

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(get_activity_messages(activity_id="i123"))
    assert "No messages found" in result


def test_add_activity_message(monkeypatch):
    """Test add_activity_message posts a message and returns confirmation."""

    async def fake_request(*_args, **kwargs):
        assert kwargs.get("method") == "POST"
        assert kwargs.get("data") == {"content": "Great run!"}
        return {"id": 42, "new_chat": None}

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(add_activity_message(activity_id="i123", content="Great run!"))
    assert "Successfully added message" in result
    assert "42" in result


def test_add_activity_message_missing_id(monkeypatch):
    """Test add_activity_message warns when response has no ID."""

    async def fake_request(*_args, **_kwargs):
        return {"new_chat": None}

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(add_activity_message(activity_id="i123", content="Hello"))
    assert "appears to have been added" in result
    assert "verify manually" in result


def test_add_activity_message_unexpected_response(monkeypatch):
    """Test add_activity_message handles unexpected non-dict response."""

    async def fake_request(*_args, **_kwargs):
        return None

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(add_activity_message(activity_id="i123", content="Hello"))
    assert "Unexpected response" in result


def test_add_activity_message_error(monkeypatch):
    """Test add_activity_message handles API errors."""

    async def fake_request(*_args, **_kwargs):
        return {"error": True, "message": "Not found"}

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    result = asyncio.run(add_activity_message(activity_id="i999", content="Hello"))
    assert "Error adding message" in result


def test_get_athlete_power_curves(monkeypatch):
    """
    Test get_athlete_power_curves returns formatted power curve data with both seasons.
    """

    async def fake_request(*_args, **_kwargs):
        return POWER_CURVES_DATA

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.power_curves.make_intervals_request", fake_request
    )
    result = asyncio.run(
        get_athlete_power_curves(
            activity_type="Ride",
            athlete_id="i1",
        )
    )
    assert "Power Curves (Ride):" in result
    assert "This season" in result
    assert "Last season" in result
    assert "5s:" in result
    assert "W/kg" in result
    assert "i100" in result


def test_get_athlete_power_curves_custom_durations(monkeypatch):
    """
    Test get_athlete_power_curves with custom durations returns only those durations.
    """

    async def fake_request(*_args, **_kwargs):
        return POWER_CURVES_DATA

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.power_curves.make_intervals_request", fake_request
    )
    result = asyncio.run(
        get_athlete_power_curves(
            activity_type="Ride",
            durations=[5, 60],
            athlete_id="i1",
        )
    )
    assert "5s:" in result
    assert "1m:" in result
    # Should not contain durations we didn't request
    assert "15s:" not in result
    assert "10m:" not in result


def test_get_athlete_power_curves_without_normalised(monkeypatch):
    """
    Test get_athlete_power_curves without normalised data excludes W/kg values.
    """

    async def fake_request(*_args, **_kwargs):
        return POWER_CURVES_DATA

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.power_curves.make_intervals_request", fake_request
    )
    result = asyncio.run(
        get_athlete_power_curves(
            activity_type="Ride",
            include_normalised=False,
            athlete_id="i1",
        )
    )
    assert "W/kg" not in result
    assert "780W" in result


def test_get_athlete_power_curves_date_validation(monkeypatch):
    """
    Test get_athlete_power_curves validates date parameters.
    """

    async def fake_request(*_args, **_kwargs):
        return POWER_CURVES_DATA

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.power_curves.make_intervals_request", fake_request
    )
    # Only start_date without end_date should fail
    result = asyncio.run(
        get_athlete_power_curves(
            activity_type="Ride",
            start_date="2026-01-01",
            athlete_id="i1",
        )
    )
    assert "Error" in result
    assert "start_date and end_date must be provided together" in result


def test_get_athlete_power_curves_no_curves_selected(monkeypatch):
    """
    Test get_athlete_power_curves returns error when no curves selected.
    """

    async def fake_request(*_args, **_kwargs):
        return POWER_CURVES_DATA

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.power_curves.make_intervals_request", fake_request
    )
    result = asyncio.run(
        get_athlete_power_curves(
            activity_type="Ride",
            this_season=False,
            last_season=False,
            athlete_id="i1",
        )
    )
    assert "Error" in result
    assert "At least one curve must be selected" in result


def test_get_custom_items(monkeypatch):
    """
    Test get_custom_items returns a formatted string containing custom item details.
    """
    custom_items = [
        {"id": 1, "name": "HR Zones", "type": "ZONES", "description": "Heart rate zones"},
        {"id": 2, "name": "Power Chart", "type": "FITNESS_CHART", "description": None},
    ]

    async def fake_request(*_args, **_kwargs):
        return custom_items

    # Patch in both api.client and tools modules to ensure it works
    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.custom_items.make_intervals_request", fake_request
    )
    result = asyncio.run(get_custom_items(athlete_id="1"))
    assert "Custom Items:" in result
    assert "HR Zones" in result
    assert "ZONES" in result
    assert "Power Chart" in result


def test_get_custom_item_by_id(monkeypatch):
    """
    Test get_custom_item_by_id returns formatted details of a single custom item.
    """
    custom_item = {
        "id": 1,
        "name": "HR Zones",
        "type": "ZONES",
        "description": "Heart rate zones",
        "visibility": "PRIVATE",
        "index": 0,
    }

    async def fake_request(*_args, **_kwargs):
        return custom_item

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.custom_items.make_intervals_request", fake_request
    )
    result = asyncio.run(get_custom_item_by_id(item_id=1, athlete_id="1"))
    assert "Custom Item Details:" in result
    assert "HR Zones" in result
    assert "ZONES" in result
    assert "Heart rate zones" in result
    assert "PRIVATE" in result


def test_create_custom_item(monkeypatch):
    """
    Test create_custom_item returns a success message with formatted item details.
    """
    created_item = {
        "id": 10,
        "name": "New Chart",
        "type": "FITNESS_CHART",
        "description": "A new fitness chart",
        "visibility": "PRIVATE",
    }

    async def fake_request(*_args, **_kwargs):
        return created_item

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.custom_items.make_intervals_request", fake_request
    )
    result = asyncio.run(
        create_custom_item(name="New Chart", item_type="FITNESS_CHART", athlete_id="1")
    )
    assert "Successfully created custom item:" in result
    assert "New Chart" in result
    assert "FITNESS_CHART" in result


def test_create_custom_item_with_string_content(monkeypatch):
    """
    Test create_custom_item correctly parses content when passed as a JSON string.
    """
    captured: dict = {}

    async def fake_request(*_args, **kwargs):
        captured["data"] = kwargs.get("data")
        return {
            "id": 11,
            "name": "Activity Field",
            "type": "ACTIVITY_FIELD",
            "content": {"expression": "icu_training_load"},
        }

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.custom_items.make_intervals_request", fake_request
    )
    result = asyncio.run(
        create_custom_item(
            name="Activity Field",
            item_type="ACTIVITY_FIELD",
            athlete_id="1",
            content='{"expression": "icu_training_load"}',  # type: ignore[arg-type]
        )
    )
    assert "Successfully created custom item:" in result
    # Verify the content was parsed from string to dict before being sent
    assert isinstance(captured["data"]["content"], dict)
    assert captured["data"]["content"]["expression"] == "icu_training_load"


def test_update_custom_item(monkeypatch):
    """
    Test update_custom_item returns a success message with formatted item details.
    """
    updated_item = {
        "id": 1,
        "name": "Updated Chart",
        "type": "FITNESS_CHART",
        "description": "Updated description",
        "visibility": "PUBLIC",
    }

    async def fake_request(*_args, **_kwargs):
        return updated_item

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.custom_items.make_intervals_request", fake_request
    )
    result = asyncio.run(
        update_custom_item(item_id=1, name="Updated Chart", athlete_id="1")
    )
    assert "Successfully updated custom item:" in result
    assert "Updated Chart" in result
    assert "PUBLIC" in result


def test_delete_custom_item(monkeypatch):
    """
    Test delete_custom_item returns the API response.
    """

    async def fake_request(*_args, **_kwargs):
        return {}

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.custom_items.make_intervals_request", fake_request
    )
    result = asyncio.run(delete_custom_item(item_id=1, athlete_id="1"))
    assert "Successfully deleted" in result


def test_create_custom_item_with_invalid_json_content(monkeypatch):
    """
    Test create_custom_item returns an error message when content is an invalid JSON string.
    """

    async def fake_request(*_args, **_kwargs):
        return {}

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.custom_items.make_intervals_request", fake_request
    )
    result = asyncio.run(
        create_custom_item(
            name="Bad Item",
            item_type="FITNESS_CHART",
            athlete_id="1",
            content="not valid json",  # type: ignore[arg-type]
        )
    )
    assert "Error: content must be valid JSON when passed as a string." in result


# ---------------------------------------------------------------------------
# Gear tools
# ---------------------------------------------------------------------------


def test_get_gear_list(monkeypatch):
    """
    Test get_gear_list returns a formatted catalog with id, type, name and stats.
    """
    _reset_gear_cache()

    sample_gear = [
        {
            "id": "b1",
            "type": "Bike",
            "name": "Litening Air",
            "default_for_type": "Ride",
            "activities": 100,
            "distance": 4_155_700,
            "retired": False,
        },
        {
            "id": "b2",
            "type": "Bike",
            "name": "Retired bike",
            "activities": 50,
            "distance": 2_000_000,
            "retired": True,
        },
    ]

    async def fake_request(*_args, **_kwargs):
        return sample_gear

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.gear.make_intervals_request", fake_request
    )

    result = asyncio.run(get_gear_list(athlete_id="i1"))

    assert "Gear catalog for athlete i1:" in result
    assert "Litening Air" in result
    assert "b1" in result
    assert "Retired bike" in result
    assert "yes" in result  # retired flag rendered
    assert "Ride" in result  # default_for_type rendered


def test_get_gear_list_empty(monkeypatch):
    """
    Test get_gear_list returns an informative message when no gear is configured.
    """
    _reset_gear_cache()

    async def fake_request(*_args, **_kwargs):
        return []

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.gear.make_intervals_request", fake_request
    )

    result = asyncio.run(get_gear_list(athlete_id="i1"))
    assert "No gear found" in result


def test_get_gear_list_cache_and_refresh(monkeypatch):
    """
    Test that get_gear_list caches the catalog and that refresh=True busts the cache.
    """
    _reset_gear_cache()

    call_count = {"n": 0}
    sample_gear = [
        {
            "id": "b1",
            "type": "Bike",
            "name": "Litening Air",
            "activities": 100,
            "distance": 4_155_700,
        }
    ]

    async def fake_request(*_args, **_kwargs):
        call_count["n"] += 1
        return sample_gear

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.gear.make_intervals_request", fake_request
    )

    # First call: cache cold, one API hit expected.
    asyncio.run(get_gear_list(athlete_id="i1"))
    assert call_count["n"] == 1

    # Second call: cache warm, no additional API hit.
    asyncio.run(get_gear_list(athlete_id="i1"))
    assert call_count["n"] == 1

    # refresh=True busts the cache and triggers a fresh fetch.
    asyncio.run(get_gear_list(athlete_id="i1", refresh=True))
    assert call_count["n"] == 2


def test_get_activity_details_resolves_gear_name(monkeypatch):
    """
    Test get_activity_details injects the resolved gear name into the formatted output
    when the activity payload contains a gear_id.
    """
    _reset_gear_cache()

    activity = {
        "name": "Morning Ride",
        "id": 123,
        "type": "Ride",
        "startTime": "2024-01-01T08:00:00Z",
        "distance": 1000,
        "duration": 3600,
        "gear_id": "b1",
    }
    gear_catalog = [{"id": "b1", "type": "Bike", "name": "Litening Air"}]

    async def fake_request(url=None, **_kwargs):
        # The activity endpoint and the gear endpoint share the same fake
        # request; route by URL pattern.
        if url and "/gear" in url:
            return gear_catalog
        return activity

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    monkeypatch.setattr(
        "intervals_mcp_server.tools.gear.make_intervals_request", fake_request
    )
    # get_activity_details does not accept athlete_id; gear resolution falls
    # back to the configured ATHLETE_ID, which is unset under CI. Provide one.
    monkeypatch.setattr(gear_module.config, "athlete_id", "1")

    result = asyncio.run(get_activity_details(123))
    assert "Activity: Morning Ride" in result
    assert "Gear:" in result
    assert "Name: Litening Air" in result
    assert "ID: b1" in result


def test_get_activities_resolves_gear_name(monkeypatch):
    """
    Test get_activities injects resolved gear names for each activity in the list.
    """
    _reset_gear_cache()

    activities = [
        {
            "name": "Ride 1",
            "id": 1,
            "type": "Ride",
            "startTime": "2024-01-01T08:00:00Z",
            "distance": 1000,
            "duration": 3600,
            "gear_id": "b1",
        },
        {
            "name": "Ride 2",
            "id": 2,
            "type": "Ride",
            "startTime": "2024-01-02T08:00:00Z",
            "distance": 2000,
            "duration": 5400,
            "gear_id": "b2",
        },
    ]
    gear_catalog = [
        {"id": "b1", "type": "Bike", "name": "Litening Air"},
        {"id": "b2", "type": "Bike", "name": "S-Works Tarmac SL8"},
    ]

    async def fake_request(url=None, **_kwargs):
        if url and "/gear" in url:
            return gear_catalog
        return activities

    monkeypatch.setattr("intervals_mcp_server.api.client.make_intervals_request", fake_request)
    monkeypatch.setattr(
        "intervals_mcp_server.tools.activities.make_intervals_request", fake_request
    )
    monkeypatch.setattr(
        "intervals_mcp_server.tools.gear.make_intervals_request", fake_request
    )

    result = asyncio.run(get_activities(athlete_id="1", limit=2, include_unnamed=True))
    assert "Ride 1" in result
    assert "Ride 2" in result
    assert "Name: Litening Air" in result
    assert "Name: S-Works Tarmac SL8" in result
