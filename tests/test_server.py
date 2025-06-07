"""
Unit tests for the main MCP server tool functions in intervals_mcp_server.server.

These tests use monkeypatching to mock API responses and verify the formatting and output of each tool function:
- get_activities
- get_activity_details
- get_events
- get_event_by_id
- get_wellness_data
- get_activity_intervals

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
    get_activities,
    get_activity_details,
    get_events,
    get_event_by_id,
    get_wellness_data,
    get_activity_intervals,
    post_events,
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


def test_post_events(monkeypatch):
    """
    Test post_events successfully posts an event and returns the response data.
    """
    expected_response = {
        "id": "e123",
        "start_date_local": "2024-01-15T00:00:00",
        "category": "WORKOUT",
        "name": "Test Workout",
        "type": "Ride"
    }
    
    sample_data = {
        "steps": [
            {"duration": "15m", "power": "80%", "description": "Warm-up"},
            {"duration": "3m", "power": "110%", "description": "High-intensity interval"},
            {"duration": "3m", "power": "80%", "description": "Recovery"},
            {"duration": "10m", "power": "80%", "description": "Cool-down"}
        ]
    }

    async def fake_post_request(*_args, **_kwargs):
        return expected_response

    monkeypatch.setattr("intervals_mcp_server.server.post_intervals_data", fake_post_request)
    result = asyncio.run(post_events(
        athlete_id="i1", 
        start_date="2024-01-15", 
        name="Test Workout", 
        data=sample_data
    ))
    assert result == expected_response


def test_post_events_type_detection(monkeypatch):
    """
    Test post_events correctly detects workout types based on name and explicit type.
    """
    test_cases = [
        # (name, data, expected_type)
        ("Morning Run", {"steps": [{"duration": "10m", "power": "80%"}]}, "Run"),
        ("Bike Intervals", {"steps": [{"duration": "10m", "power": "80%"}]}, "Ride"),
        ("Swimming Session", {"steps": [{"duration": "10m", "power": "80%"}]}, "Swim"),
        ("VO2 Max Intervals", {"steps": [{"duration": "10m", "power": "80%"}]}, "Run"),  # Should default to Run
        ("Intervals", {"steps": [{"duration": "10m", "power": "80%"}], "type": "Run"}, "Run"),  # Explicit type
        ("Bike Workout", {"steps": [{"duration": "10m", "power": "80%"}], "type": "Swim"}, "Swim"),  # Explicit type overrides name
    ]
    
    posted_data = None
    
    async def fake_post_request(data, *_args, **_kwargs):
        nonlocal posted_data
        posted_data = data
        return {"id": "e123", "type": data["type"]}
    
    monkeypatch.setattr("intervals_mcp_server.server.post_intervals_data", fake_post_request)
    
    for name, data, expected_type in test_cases:
        posted_data = None
        result = asyncio.run(post_events(
            athlete_id="i1",
            start_date="2024-01-15",
            name=name,
            data=data
        ))
        assert posted_data["type"] == expected_type, f"Expected type '{expected_type}' for workout '{name}', but got '{posted_data['type']}'"
