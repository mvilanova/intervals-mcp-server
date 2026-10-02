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
    add_or_update_event,
    get_athlete_power_curves,
    get_event_by_id,
    get_events,
    get_gear_list,
    get_sport_settings,
    update_sport_settings,
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


SPORT_SETTINGS_RIDE = {
    "id": 1,
    "types": ["Ride", "VirtualRide"],
    "ftp": 200,
    "indoor_ftp": 190,
    "lthr": 160,
    "max_hr": 180,
    "power_zones": [55, 75, 90, 105, 120, 150, 999],
    "power_zone_names": ["Recovery", "Endurance", "Tempo", "Threshold", "VO2", "Anaerobic", "Neuro"],
    "hr_zones": [130, 140, 150, 160, 170, 175, 180],
    "hr_zone_names": ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7"],
}


def _sport_settings_fake(calls, put_result=None, get_result=None):
    async def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/athlete/i1"):
            return {"icu_weight": 70.5}
        if kwargs.get("method") == "PUT":
            return put_result if put_result is not None else SPORT_SETTINGS_RIDE
        return get_result if get_result is not None else [SPORT_SETTINGS_RIDE]

    return fake_request


def test_get_sport_settings(monkeypatch):
    """get_sport_settings renders zones in watts/bpm and the athlete weight."""
    calls: list = []
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request",
        _sport_settings_fake(calls),
    )
    result = asyncio.run(get_sport_settings(athlete_id="i1"))
    assert calls[0][0] == "/athlete/i1/sport-settings"
    assert "Ride, VirtualRide" in result
    assert "FTP: 200 W" in result
    assert "Indoor FTP: 190 W" in result
    assert "LTHR: 160 bpm" in result
    assert "Max HR: 180 bpm" in result
    assert "Z1 Recovery: 0-55%  0-110 W" in result
    assert "Z4 Threshold: 90-105%  180-210 W" in result
    assert "Z7 Neuro: 150%+  300+ W" in result
    assert "Z2 Z2: 131-140 bpm" in result
    assert "Z1 Z1: <= 130 bpm" in result
    assert "Athlete weight: 70.5 kg" in result


def test_get_sport_settings_single_sport(monkeypatch):
    """A single sport uses the /sport-settings/{sport} endpoint."""
    calls: list = []
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request",
        _sport_settings_fake(calls, get_result=SPORT_SETTINGS_RIDE),
    )
    result = asyncio.run(get_sport_settings(sport="Ride", athlete_id="i1"))
    assert calls[0][0] == "/athlete/i1/sport-settings/Ride"
    assert "FTP: 200 W" in result


def test_get_sport_settings_pace(monkeypatch):
    """Threshold pace in m/s is converted using pace_units."""
    swim = {"types": ["Swim"], "threshold_pace": 1.0, "pace_units": "SECS_100M"}
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request",
        _sport_settings_fake([], get_result=[swim]),
    )
    result = asyncio.run(get_sport_settings(athlete_id="i1"))
    assert "Threshold pace: 1:40 /100m" in result


def test_get_sport_settings_empty(monkeypatch):
    """Empty result gives an informative message."""
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request",
        _sport_settings_fake([], get_result=[]),
    )
    result = asyncio.run(get_sport_settings(athlete_id="i1"))
    assert "No sport settings found" in result


def test_get_sport_settings_error(monkeypatch):
    """API errors are reported."""

    async def fake_request(*_args, **_kwargs):
        return {"error": True, "message": "Not found"}

    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request", fake_request
    )
    result = asyncio.run(get_sport_settings(sport="Nope", athlete_id="i1"))
    assert "Error fetching sport settings: Not found" in result


def test_update_sport_settings_only_passed_fields(monkeypatch):
    """Only passed fields are sent; HR zone recalculation defaults to off."""
    calls: list = []
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request",
        _sport_settings_fake(calls),
    )
    result = asyncio.run(update_sport_settings(sport="Ride", ftp=200, athlete_id="i1"))
    put_url, put_kwargs = calls[0]
    assert put_url == "/athlete/i1/sport-settings/Ride"
    assert put_kwargs["method"] == "PUT"
    assert put_kwargs["data"] == {"ftp": 200}
    assert put_kwargs["params"] == {"recalcHrZones": "false"}
    assert "Sport settings updated." in result
    assert "FTP: 200 W" in result
    assert "Z4 Threshold: 90-105%  180-210 W" in result


def test_update_sport_settings_hr_recalc(monkeypatch):
    """recalc_hr_zones is sent only as passed; lthr/max_hr alone do not enable it."""
    calls: list = []
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request",
        _sport_settings_fake(calls),
    )
    asyncio.run(update_sport_settings(sport="Run", lthr=160, max_hr=180, athlete_id="i1"))
    _, put_kwargs = calls[0]
    assert put_kwargs["data"] == {"lthr": 160, "max_hr": 180}
    assert put_kwargs["params"] == {"recalcHrZones": "false"}
    asyncio.run(
        update_sport_settings(
            sport="Run", lthr=160, max_hr=180, recalc_hr_zones=True, athlete_id="i1"
        )
    )
    assert calls[2][1]["params"] == {"recalcHrZones": "true"}


def test_update_sport_settings_validation(monkeypatch):
    """Out-of-range values and lthr >= max_hr return an error without calling the API."""
    calls: list = []
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request",
        _sport_settings_fake(calls),
    )
    for kwargs in (
        {"ftp": 49},
        {"ftp": 1001},
        {"lthr": 79},
        {"max_hr": 231},
        {"lthr": 180, "max_hr": 180},
        {"lthr": 190, "max_hr": 170},
    ):
        result = asyncio.run(update_sport_settings(sport="Ride", athlete_id="i1", **kwargs))
        assert result.startswith("Error:"), kwargs
    assert not calls
    asyncio.run(update_sport_settings(sport="Ride", ftp=50, lthr=80, max_hr=230, athlete_id="i1"))
    assert calls


def test_update_sport_settings_requires_value(monkeypatch):
    """No values passed returns an error without calling the API."""
    calls: list = []
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request",
        _sport_settings_fake(calls),
    )
    result = asyncio.run(update_sport_settings(sport="Ride", athlete_id="i1"))
    assert result.startswith("Error:")
    assert not calls


def test_update_sport_settings_api_error(monkeypatch):
    """API errors on update are reported."""
    monkeypatch.setattr(
        "intervals_mcp_server.tools.sport_settings.make_intervals_request",
        _sport_settings_fake([], put_result={"error": True, "message": "Bad request"}),
    )
    result = asyncio.run(update_sport_settings(sport="Ride", ftp=250, athlete_id="i1"))
    assert "Error updating sport settings: Bad request" in result
