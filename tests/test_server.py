"""
Unit tests for the main MCP server tool functions in intervals_mcp_server.server.

These tests use the `patch_request` fixture (defined in conftest.py) to mock
API responses and verify the formatting/output of each tool function.

Tools exercised:
- get_activities, get_activity_details, get_activity_intervals,
  get_activity_streams, get_activity_messages, add_activity_message
- get_events, get_event_by_id, add_or_update_event
- get_wellness_data
- get_custom_items, get_custom_item_by_id, create_custom_item,
  update_custom_item, delete_custom_item
"""

from __future__ import annotations

import asyncio

import pytest

from intervals_mcp_server.server import (
    add_activity_message,
    add_or_update_event,
    create_custom_item,
    delete_custom_item,
    get_activities,
    get_activity_details,
    get_activity_intervals,
    get_activity_messages,
    get_activity_streams,
    get_custom_item_by_id,
    get_custom_items,
    get_event_by_id,
    get_events,
    get_wellness_data,
    update_custom_item,
)
from tests.sample_data import INTERVALS_DATA, SAMPLE_ACTIVITY, SAMPLE_EVENT


# Most tools follow the same shape: feed a payload through the patched API
# and assert that the formatted string contains a set of substrings. Cases
# where the invocation kwargs vary are expressed as a `lambda` payload.
@pytest.mark.parametrize(
    "payload, tool_module, invoke, expected_substrings",
    [
        (
            [SAMPLE_ACTIVITY],
            "activities",
            lambda: get_activities(athlete_id="1", limit=1, include_unnamed=True),
            ["Morning Ride", "Activities:"],
        ),
        (
            SAMPLE_ACTIVITY,
            "activities",
            lambda: get_activity_details(123),
            ["Activity: Morning Ride"],
        ),
        (
            [SAMPLE_EVENT],
            "events",
            lambda: get_events(athlete_id="1", start_date="2024-01-01", end_date="2024-01-02"),
            ["Test Event", "Events:"],
        ),
        (
            SAMPLE_EVENT,
            "events",
            lambda: get_event_by_id("e1", athlete_id="1"),
            ["Event Details:", "Test Event"],
        ),
        (
            {"2024-01-01": {"id": "2024-01-01", "ctl": 75, "sleepSecs": 28800}},
            "wellness",
            lambda: get_wellness_data(athlete_id="1"),
            ["Wellness Data:", "2024-01-01"],
        ),
        (
            [
                {"id": 1, "name": "HR Zones", "type": "ZONES", "description": "Heart rate zones"},
                {"id": 2, "name": "Power Chart", "type": "FITNESS_CHART", "description": None},
            ],
            "custom_items",
            lambda: get_custom_items(athlete_id="1"),
            ["Custom Items:", "HR Zones", "ZONES", "Power Chart"],
        ),
        (
            {
                "id": 1,
                "name": "HR Zones",
                "type": "ZONES",
                "description": "Heart rate zones",
                "visibility": "PRIVATE",
                "index": 0,
            },
            "custom_items",
            lambda: get_custom_item_by_id(item_id=1, athlete_id="1"),
            ["Custom Item Details:", "HR Zones", "ZONES", "Heart rate zones", "PRIVATE"],
        ),
        (
            {
                "id": 1,
                "name": "Updated Chart",
                "type": "FITNESS_CHART",
                "description": "Updated description",
                "visibility": "PUBLIC",
            },
            "custom_items",
            lambda: update_custom_item(item_id=1, name="Updated Chart", athlete_id="1"),
            ["Successfully updated custom item:", "Updated Chart", "PUBLIC"],
        ),
    ],
    ids=[
        "get_activities",
        "get_activity_details",
        "get_events",
        "get_event_by_id",
        "get_wellness_data",
        "get_custom_items",
        "get_custom_item_by_id",
        "update_custom_item",
    ],
)
def test_tool_formats_output(patch_request, payload, tool_module, invoke, expected_substrings):
    """Tools render their API payloads into strings containing the expected substrings."""
    patch_request(payload, tool_module)
    result = asyncio.run(invoke())
    for substring in expected_substrings:
        assert substring in result, f"Expected {substring!r} in:\n{result}"


def test_get_wellness_data_renders_macros(patch_request):
    """Native nutrition macros (carbohydrates, protein, fatTotal) flow into the formatted output."""
    patch_request(
        [{"id": "2026-04-08", "carbohydrates": 310, "protein": 145, "fatTotal": 72}],
        "wellness",
    )
    result = asyncio.run(get_wellness_data(athlete_id="1"))
    assert "Wellness Data:" in result
    assert "2026-04-08" in result
    assert "Nutrition & Hydration:" in result
    assert "- Carbohydrates: 310 g" in result
    assert "- Protein: 145 g" in result
    assert "- Fat: 72 g" in result


def test_get_wellness_data_include_all_fields(patch_request):
    """include_all_fields=True surfaces unknown fields under 'Other Fields:'."""
    patch_request(
        [{"id": "2024-01-01", "ctl": 75, "sleepSecs": 28800, "customField": "custom_value"}],
        "wellness",
    )
    result = asyncio.run(get_wellness_data(athlete_id="1", include_all_fields=True))
    assert "Wellness Data:" in result
    assert "Fitness (CTL): 75" in result
    assert "Other Fields:" in result
    assert "customField: custom_value" in result


def test_get_activity_intervals(patch_request):
    """get_activity_intervals renders interval analysis from icu_intervals payload."""
    patch_request(INTERVALS_DATA, "activities")
    result = asyncio.run(get_activity_intervals("123"))
    assert "Intervals Analysis:" in result
    assert "Rep 1" in result


def test_get_activity_streams(patch_request):
    """get_activity_streams renders per-stream summaries with data-point counts."""
    streams = [
        {
            "type": stream_type,
            "name": stream_type,
            "data": list(range(11)),
            "data2": [],
            "valueType": value_type,
            "valueTypeIsArray": False,
            "anomalies": None,
            "custom": False,
        }
        for stream_type, value_type in [
            ("time", "time_units"),
            ("watts", "power_units"),
            ("heartrate", "hr_units"),
        ]
    ]
    patch_request(streams, "activities")
    result = asyncio.run(get_activity_streams("i107537962"))
    assert "Activity Streams" in result
    for expected in ["time", "watts", "heartrate", "Data Points: 11"]:
        assert expected in result


def test_add_or_update_event(patch_request):
    """add_or_update_event returns a success message containing the new event id."""
    patch_request(
        {
            "id": "e123",
            "start_date_local": "2024-01-15T00:00:00",
            "category": "WORKOUT",
            "name": "Test Workout",
            "type": "Ride",
        },
        "events",
    )
    result = asyncio.run(
        add_or_update_event(
            athlete_id="i1", start_date="2024-01-15", name="Test Workout", workout_type="Ride"
        )
    )
    assert "Successfully created event id:" in result
    assert "e123" in result


# Variations of add_activity_message: success / partial / unexpected / error responses.
@pytest.mark.parametrize(
    "payload, activity_id, expected_substrings",
    [
        ({"id": 42, "new_chat": None}, "i123", ["Successfully added message", "42"]),
        ({"new_chat": None}, "i123", ["appears to have been added", "verify manually"]),
        (None, "i123", ["Unexpected response"]),
        ({"error": True, "message": "Not found"}, "i999", ["Error adding message"]),
    ],
    ids=["success", "missing_id", "unexpected_response", "error"],
)
def test_add_activity_message_response_handling(
    patch_request, payload, activity_id, expected_substrings
):
    """add_activity_message handles each response shape with the right message."""
    patch_request(payload, "activities")
    result = asyncio.run(add_activity_message(activity_id=activity_id, content="Hello"))
    for substring in expected_substrings:
        assert substring in result, f"Expected {substring!r} in:\n{result}"


def test_add_activity_message_posts_content(patch_request):
    """add_activity_message sends the content as POST data with method=POST."""
    captured = patch_request({"id": 42, "new_chat": None}, "activities")
    asyncio.run(add_activity_message(activity_id="i123", content="Great run!"))
    assert captured["kwargs"].get("method") == "POST"
    assert captured["kwargs"].get("data") == {"content": "Great run!"}


# Variations of get_activity_messages: happy path, API error, empty list.
@pytest.mark.parametrize(
    "payload, expected_substrings",
    [
        (
            [
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
            ],
            ["Legs felt heavy today", "Good effort despite that!", "Niko", "Coach"],
        ),
        (
            {"error": True, "message": "Activity not found"},
            ["Error fetching activity messages", "Activity not found"],
        ),
        ([], ["No messages found"]),
    ],
    ids=["happy", "error", "empty"],
)
def test_get_activity_messages(patch_request, payload, expected_substrings):
    """get_activity_messages formats happy/error/empty responses appropriately."""
    patch_request(payload, "activities")
    result = asyncio.run(get_activity_messages(activity_id="i123"))
    for substring in expected_substrings:
        assert substring in result, f"Expected {substring!r} in:\n{result}"


def test_create_custom_item(patch_request):
    """create_custom_item returns a success message with the new item details."""
    patch_request(
        {
            "id": 10,
            "name": "New Chart",
            "type": "FITNESS_CHART",
            "description": "A new fitness chart",
            "visibility": "PRIVATE",
        },
        "custom_items",
    )
    result = asyncio.run(
        create_custom_item(name="New Chart", item_type="FITNESS_CHART", athlete_id="1")
    )
    assert "Successfully created custom item:" in result
    assert "New Chart" in result
    assert "FITNESS_CHART" in result


def test_create_custom_item_with_string_content(patch_request):
    """create_custom_item parses string content into a dict before sending."""
    captured = patch_request(
        {
            "id": 11,
            "name": "Activity Field",
            "type": "ACTIVITY_FIELD",
            "content": {"expression": "icu_training_load"},
        },
        "custom_items",
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
    sent = captured["kwargs"]["data"]
    assert isinstance(sent["content"], dict)
    assert sent["content"]["expression"] == "icu_training_load"


def test_create_custom_item_with_invalid_json_content(patch_request):
    """create_custom_item returns an error when content is invalid JSON."""
    patch_request({}, "custom_items")
    result = asyncio.run(
        create_custom_item(
            name="Bad Item",
            item_type="FITNESS_CHART",
            athlete_id="1",
            content="not valid json",  # type: ignore[arg-type]
        )
    )
    assert "Error: content must be valid JSON when passed as a string." in result


def test_delete_custom_item(patch_request):
    """delete_custom_item returns a confirmation message."""
    patch_request({}, "custom_items")
    result = asyncio.run(delete_custom_item(item_id=1, athlete_id="1"))
    assert "Successfully deleted" in result
