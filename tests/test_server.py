"""
Unit tests for the main MCP server tool functions in intervals_mcp_server.server.

These tests use monkeypatching to mock API responses and verify the formatting and output of each tool function:
- get_activities
- get_activity_details
- get_events
- get_event_by_id
- get_wellness_data
- get_activity_intervals
- create_workout

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
    create_workout,
    get_activities,
    get_activity_details,
    get_activity_intervals,
    get_current_date_info,
    get_events,
    get_event_by_id,
    get_wellness_data,
    get_workout_format_examples,
)
from tests.sample_data import INTERVALS_DATA  # pylint: disable=wrong-import-position


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

    monkeypatch.setattr("intervals_mcp_server.server.make_intervals_request", fake_request)
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

    monkeypatch.setattr("intervals_mcp_server.server.make_intervals_request", fake_request)
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

    monkeypatch.setattr("intervals_mcp_server.server.make_intervals_request", fake_request)
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

    monkeypatch.setattr("intervals_mcp_server.server.make_intervals_request", fake_request)
    result = asyncio.run(get_event_by_id("e1", athlete_id="1"))
    assert "Event Details:" in result
    assert "Test Event" in result


def test_get_wellness_data(monkeypatch):
    """
    Test get_wellness_data returns a formatted string containing wellness data for a given athlete.
    """
    wellness = {
        "2024-01-01": {
            "id": "w1",
            "date": "2024-01-01",
            "ctl": 75,
            "sleepSecs": 28800,
        }
    }

    async def fake_request(*_args, **_kwargs):
        return wellness

    monkeypatch.setattr("intervals_mcp_server.server.make_intervals_request", fake_request)
    result = asyncio.run(get_wellness_data(athlete_id="1"))
    assert "Wellness Data:" in result
    assert "2024-01-01" in result


def test_get_activity_intervals(monkeypatch):
    """
    Test get_activity_intervals returns a formatted string with interval analysis for a given activity.
    """

    async def fake_request(*_args, **_kwargs):
        return INTERVALS_DATA

    monkeypatch.setattr("intervals_mcp_server.server.make_intervals_request", fake_request)
    result = asyncio.run(get_activity_intervals("123"))
    assert "Intervals Analysis:" in result
    assert "Rep 1" in result


def test_create_workout_success(monkeypatch):
    """
    Test create_workout returns a success message when the workout is created successfully.
    """
    mock_response = {
        "id": 12345,
        "name": "Test Workout",
        "start_date_local": "2024-01-15",
        "category": "WORKOUT",
        "description": "5m z1\n3x\n- 1m z5\n- 2m z1\n5m z1",
    }

    async def fake_post_request(*args, **kwargs):
        return mock_response

    monkeypatch.setattr("intervals_mcp_server.server.make_intervals_post_request", fake_post_request)

    result = asyncio.run(
        create_workout(
            name="Test Workout",
            description="5m z1\n3x\n- 1m z5\n- 2m z1\n5m z1",
            date="2024-01-15",
            athlete_id="i123456",
        )
    )

    assert "Successfully created workout 'Test Workout' on 2024-01-15 (Event ID: 12345)" in result


def test_create_workout_api_error(monkeypatch):
    """
    Test create_workout returns an error message when the API returns an error.
    """
    mock_error_response = {"error": True, "message": "Invalid date format"}

    async def fake_post_request(*args, **kwargs):
        return mock_error_response

    monkeypatch.setattr("intervals_mcp_server.server.make_intervals_post_request", fake_post_request)

    result = asyncio.run(
        create_workout(
            name="Test Workout",
            description="5m z1",
            date="2024-01-15",
            athlete_id="i123456",
        )
    )

    assert "Error creating workout: Invalid date format" in result


def test_create_workout_invalid_date():
    """
    Test create_workout returns an error for invalid date format.
    """
    result = asyncio.run(
        create_workout(
            name="Test Workout",
            description="5m z1",
            date="2024/01/15",  # Invalid format
            athlete_id="i123456",
        )
    )

    assert "Error: Date must be in YYYY-MM-DD format." in result


def test_create_workout_invalid_category():
    """
    Test create_workout returns an error for invalid category.
    """
    result = asyncio.run(
        create_workout(
            name="Test Workout",
            description="5m z1",
            date="2024-01-15",
            athlete_id="i123456",
            category="INVALID_CATEGORY",
        )
    )

    assert "Error: Invalid category." in result


def test_create_workout_invalid_color():
    """
    Test create_workout returns an error for invalid color format.
    """
    result = asyncio.run(
        create_workout(
            name="Test Workout",
            description="5m z1",
            date="2024-01-15",
            athlete_id="i123456",
            color="red",  # Invalid hex format
        )
    )

    assert "Error: Color must be a hex color code like #FF0000" in result


def test_create_workout_no_athlete_id(monkeypatch):
    """
    Test create_workout returns an error when no athlete ID is provided.
    """
    # Mock the ATHLETE_ID to be empty
    monkeypatch.setattr("intervals_mcp_server.server.ATHLETE_ID", "")

    result = asyncio.run(create_workout(name="Test Workout", description="5m z1", date="2024-01-15"))

    assert (
        "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables." in result
    )


def test_get_current_date_info():
    """
    Test get_current_date_info returns current date and time information
    """
    from datetime import datetime

    result = asyncio.run(get_current_date_info())

    # Verify the structure
    assert isinstance(result, dict)
    assert "current_date" in result
    assert "day_of_week" in result
    assert "week_number" in result
    assert "days_until_weekend" in result
    assert "is_weekend" in result
    assert "year" in result
    assert "month" in result
    assert "day" in result

    # Verify data types and ranges
    assert isinstance(result["current_date"], str)
    assert isinstance(result["day_of_week"], str)
    assert isinstance(result["week_number"], int)
    assert isinstance(result["days_until_weekend"], int)
    assert isinstance(result["is_weekend"], bool)
    assert isinstance(result["year"], int)
    assert isinstance(result["month"], int)
    assert isinstance(result["day"], int)

    # Verify reasonable ranges
    assert 0 <= result["days_until_weekend"] <= 6
    assert 1 <= result["month"] <= 12
    assert 1 <= result["day"] <= 31
    assert result["year"] >= 2025

    # Verify date format
    datetime.strptime(result["current_date"], "%Y-%m-%d")  # Should not raise

    # Verify day of week is valid
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert result["day_of_week"] in valid_days


def test_get_workout_format_examples():
    """
    Test get_workout_format_examples returns workout format examples from workout_samples.md
    """
    result = asyncio.run(get_workout_format_examples())

    # Check that it contains key content from workout_samples.md
    assert "Intervals.icu Workout Samples" in result
    assert "Bike Workouts" in result
    assert "Run Workouts" in result
    assert "Swim Workouts" in result
    assert "z1" in result  # Power/pace zones
    assert "%" in result  # Percentage notation
    assert "3x" in result  # Interval notation
