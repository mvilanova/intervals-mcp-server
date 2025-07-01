"""
Unit tests for formatting utilities in intervals_mcp_server.utils.formatting.

These tests verify that the formatting functions produce expected output strings for activities, workouts, wellness entries, events, and intervals.
"""

from intervals_mcp_server.utils.formatting import (
    format_activity_summary,
    format_workout,
    format_wellness_entry,
    format_event_summary,
    format_event_details,
    format_intervals,
    format_athlete_data,
)
from tests.sample_data import INTERVALS_DATA


def test_format_activity_summary():
    """
    Test that format_activity_summary returns a string containing the activity name and ID.
    """
    data = {
        "name": "Morning Ride",
        "id": 1,
        "type": "Ride",
        "startTime": "2024-01-01T08:00:00Z",
        "distance": 1000,
        "duration": 3600,
    }
    result = format_activity_summary(data)
    assert "Activity: Morning Ride" in result
    assert "ID: 1" in result


def test_format_workout():
    """
    Test that format_workout returns a string containing the workout name and interval count.
    """
    workout = {
        "name": "Workout1",
        "description": "desc",
        "sport": "Ride",
        "duration": 3600,
        "tss": 50,
        "intervals": [1, 2, 3],
    }
    result = format_workout(workout)
    assert "Workout: Workout1" in result
    assert "Intervals: 3" in result


def test_format_wellness_entry():
    """
    Test that format_wellness_entry returns a string containing the date and fitness (CTL).
    """
    entry = {
        "date": "2024-01-01",
        "ctl": 70,
        "sleepSecs": 28800,
        "weight": 70,
    }
    result = format_wellness_entry(entry)
    assert "Date: 2024-01-01" in result
    assert "Fitness (CTL): 70" in result


def test_format_event_summary():
    """
    Test that format_event_summary returns a string containing the event date and type.
    """
    event = {
        "date": "2024-01-01",
        "id": "e1",
        "name": "Event1",
        "description": "desc",
        "race": True,
    }
    summary = format_event_summary(event)
    assert "Date: 2024-01-01" in summary
    assert "Type: Race" in summary


def test_format_event_details():
    """
    Test that format_event_details returns a string containing event and workout details.
    """
    event = {
        "id": "e1",
        "date": "2024-01-01",
        "name": "Event1",
        "description": "desc",
        "workout": {
            "id": "w1",
            "sport": "Ride",
            "duration": 3600,
            "tss": 50,
            "intervals": [1, 2],
        },
        "race": True,
        "priority": "A",
        "result": "1st",
        "calendar": {"name": "Main"},
    }
    details = format_event_details(event)
    assert "Event Details:" in details
    assert "Workout Information:" in details


def test_format_intervals():
    """
    Test that format_intervals returns a string containing interval analysis and the interval label.
    """
    result = format_intervals(INTERVALS_DATA)
    assert "Intervals Analysis:" in result
    assert "Rep 1" in result


def test_format_athlete_data():
    """
    Test that format_athlete_data returns a formatted Markdown string with athlete information.
    """

    athlete = {
        "id": "i123456",
        "name": "Test Athlete",
        "sex": "M",
        "city": "Munich",
        "country": "Germany",
        "icu_weight": 70.0,
        "height": 1.75,
        "icu_resting_hr": 45,
        "timezone": "Europe/Berlin",
        "bio": "Test bio",
        "sportSettings": [
            {
                "types": ["Ride"],
                "ftp": 250,
                "lthr": 160,
                "max_hr": 185,
                "power_zones": [55, 75, 90, 105, 120, 150, 999],
                "power_zone_names": ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7"],
                "hr_zones": [130, 145, 155, 165, 170, 175, 185],
                "hr_zone_names": ["HR1", "HR2", "HR3", "HR4", "HR5", "HR6", "HR7"],
            }
        ],
    }

    result = format_athlete_data(athlete)

    # Check basic structure
    assert "# Athlete Profile: Test Athlete" in result
    assert "## Basic Information" in result
    assert "## Sport-Specific Training Zones" in result

    # Check basic info
    assert "**ID**: i123456" in result
    assert "**Gender**: M" in result
    assert "Munich" in result and "Germany" in result
    assert "70.0 kg" in result
    assert "1.75 m" in result
    assert "45 bpm" in result

    # Check sport settings
    assert "Cycling" in result
    assert "FTP: 250 watts" in result
    assert "LTHR: 160 bpm" in result
    assert "Max HR: 185 bpm" in result

    # Check bio
    assert "Test bio" in result


def test_format_athlete_data_empty():
    """
    Test that format_athlete_data handles empty/invalid input gracefully.
    """

    assert format_athlete_data({}) == "No athlete data available"
    assert format_athlete_data(None) == "No athlete data available"
    assert format_athlete_data("invalid") == "No athlete data available"
