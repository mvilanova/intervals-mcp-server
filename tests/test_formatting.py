"""
Unit tests for formatting utilities in intervals_mcp_server.utils.formatting.

These tests verify that the formatting functions produce expected output strings for activities, workouts, wellness entries, events, and intervals.
"""

import json
from intervals_mcp_server.utils.formatting import (
    format_activity_summary,
    format_workout,
    format_wellness_entry,
    format_event_summary,
    format_event_details,
    format_intervals,
    format_power_curves,
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


def test_format_activity_summary_prefers_start_date_local():
    """format_activity_summary must prefer start_date_local over UTC fields.

    AGENTS.md: 'a 7pm local swim shows up in the MCP as 5pm UTC on the
    same day, and a swim after 22:00 CEST shows up on the previous UTC
    day. Always cross-check with start_date_local.'
    """
    result = format_activity_summary(
        {
            "id": 1,
            "name": "Evening Swim",
            "type": "Swim",
            "startTime": "2024-06-30T21:30:00Z",       # UTC: 23:30 CEST
            "start_date_local": "2024-06-30T23:30:00",  # local time
            "duration": 1800,
        }
    )
    assert "Date: 2024-06-30 23:30:00" in result
    assert "Date: 2024-06-30 21:30:00" not in result


def test_format_activity_summary_no_local_falls_back_to_utc():
    """Without start_date_local, fall back to startTime (UTC). Regression guard."""
    result = format_activity_summary(
        {
            "id": 1,
            "name": "Morning Ride",
            "type": "Ride",
            "startTime": "2024-01-01T08:00:00Z",
            "duration": 3600,
        }
    )
    assert "Date: 2024-01-01 08:00:00" in result

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
    with open("tests/ressources/wellness_entry.json", "r", encoding="utf-8") as f:
        entry = json.load(f)
    result = format_wellness_entry(entry)

    with open("tests/ressources/wellness_entry_formatted.txt", "r", encoding="utf-8") as f:
        expected_result = f.read()
    assert result == expected_result


def test_format_wellness_entry_include_all_fields():
    """
    Test that format_wellness_entry with include_all_fields=True includes additional unknown fields.
    """
    entry = {
        "id": "2024-06-01",
        "ctl": 80,
        "weight": 75,
        "customField1": "hello",
        "customField2": 42,
        "updated": "2024-06-01T10:00:00Z",
    }
    result = format_wellness_entry(entry, include_all_fields=True)
    assert "Date: 2024-06-01" in result
    assert "Fitness (CTL): 80" in result
    assert "Weight: 75 kg" in result
    assert "Other Fields:" in result
    assert "customField1: hello" in result
    assert "customField2: 42" in result
    # "updated" is a known built-in field, should not appear in Other Fields
    assert "updated:" not in result


def test_format_wellness_entry_no_extra_fields_by_default():
    """
    Test that format_wellness_entry without include_all_fields does not include additional fields.
    """
    entry = {
        "id": "2024-06-01",
        "ctl": 80,
        "customField1": "hello",
    }
    result = format_wellness_entry(entry)
    assert "Other Fields:" not in result
    assert "customField1" not in result


def test_format_wellness_entry_macros_populated():
    """
    Test that format_wellness_entry renders native nutrition macros
    (carbohydrates, protein, fatTotal) in grams when present.
    """
    entry = {
        "id": "2026-04-08",
        "carbohydrates": 310,
        "protein": 145,
        "fatTotal": 72,
    }
    result = format_wellness_entry(entry)
    assert "Nutrition & Hydration:" in result
    assert "- Carbohydrates: 310 g" in result
    assert "- Protein: 145 g" in result
    assert "- Fat: 72 g" in result


def test_format_wellness_entry_macros_null_hidden():
    """
    Test that format_wellness_entry hides macro lines when the fields are null,
    preserving backward compatibility with older wellness records.
    """
    entry = {
        "id": "2026-04-08",
        "ctl": 80,
        "carbohydrates": None,
        "protein": None,
        "fatTotal": None,
    }
    result = format_wellness_entry(entry)
    assert "Carbohydrates" not in result
    assert "Protein" not in result
    # "Fat" could legitimately appear inside e.g. "Body Fat" elsewhere, so
    # anchor the negative assertion on the line-prefix form we would emit.
    assert "- Fat:" not in result

def test_format_event_summary():
    """
    Test that format_event_summary returns a string containing the event date and type.
    """
    event = {
        "start_date_local": "2024-01-01",
        "id": "e1",
        "name": "Event1",
        "description": "desc",
        "race": True,
    }
    summary = format_event_summary(event)
    assert "Date: 2024-01-01" in summary
    assert "Race" in summary


def test_format_event_summary_shows_sport():
    """The Type line must surface the event's sport (event['type']), not 'Other'.

    AGENTS.md: 'get_events always reports Type: Other regardless of the
    actual type value on the event. So an event with type=Run will look
    like Type: Other in the MCP response.'
    """
    summary = format_event_summary(
        {"id": "e1", "name": "Easy Run", "type": "Run", "start_date_local": "2024-01-01"}
    )
    assert "Type: Run" in summary
    assert "Type: Other" not in summary


def test_format_event_summary_annotates_race_with_sport():
    """A race event must show the sport and the Race flag, not just 'Race'."""
    summary = format_event_summary(
        {
            "id": "e1",
            "name": "Spring 10k",
            "type": "Run",
            "race": True,
            "start_date_local": "2024-04-15",
        }
    )
    assert "Type: Run" in summary
    assert "Race" in summary


def test_format_event_summary_annotates_workout_doc():
    """An event with a structured workout_doc must be flagged as a Workout."""
    summary = format_event_summary(
        {
            "id": "e1",
            "name": "VO2max",
            "type": "Ride",
            "workout_doc": {"steps": []},
            "start_date_local": "2024-01-15",
        }
    )
    assert "Type: Ride" in summary
    assert "Workout" in summary

def test_format_event_details():
    """
    Test that format_event_details returns formatted string containing event and workout details.
    """
    event = {
        "id": "e1",
        "start_date_local": "2024-01-01T08:00:00",
        "type": "Ride",
        "name": "Event1",
        "description": "desc",
        "workout_doc": {
            "description": "VO2 max",
            "duration": 3600,
            "target": "POWER",
            "steps": [{}, {}, {}],
        },
        "race": True,
        "priority": "A",
        "result": "1st",
        "calendar": {"name": "Main"},
    }
    details = format_event_details(event)
    assert "Event Details:" in details
    assert "Workout Information:" in details
    assert "2024-01-01T08:00:00" in details
    assert "VO2 max" in details
    assert "Steps: 3" in details


def test_format_event_details_uses_start_date_local():
    """format_event_details must read start_date_local, not the non-existent 'date' field.

    AGENTS.md mandates start_date_local for any human-facing text.
    """
    details = format_event_details(
        {
            "id": "e1",
            "start_date_local": "2024-06-15T19:00:00",
            "type": "Run",
            "name": "Easy Run",
        }
    )
    assert "Date: 2024-06-15T19:00:00" in details
    assert "Date: Unknown" not in details


def test_format_event_details_renders_workout_doc_section():
    """An event with a structured workout_doc must render the Workout
    Information section. The old code looked up 'workout' (no such field
    on Intervals.icu responses) and silently dropped the section.
    """
    details = format_event_details(
        {
            "id": "e1",
            "start_date_local": "2024-01-01T08:00:00",
            "type": "Ride",
            "name": "VO2",
            "workout_doc": {
                "description": "5x3min @ 130% FTP",
                "duration": 4500,
                "target": "POWER",
                "steps": [{}, {}],
            },
        }
    )
    assert "Workout Information:" in details
    assert "5x3min @ 130% FTP" in details
    assert "Duration: 4500 seconds" in details
    assert "Target: POWER" in details
    assert "Steps: 2" in details


def test_format_intervals():
    """
    Test that format_intervals returns a string containing interval analysis and the interval label.
    """
    result = format_intervals(INTERVALS_DATA)
    assert "Intervals Analysis:" in result
    assert "Rep 1" in result


def test_format_power_curves():
    """
    Test that format_power_curves returns a concise string with curve labels,
    power values, W/kg values, and activity IDs.
    """
    curves = [
        {
            "id": "s0",
            "label": "This season",
            "start": "2025-09-29T00:00:00",
            "end": "2026-03-14T00:00:00",
            "data_points": [
                {"secs": 5, "watts": 780, "activity_id": "i100", "watts_per_kg": 10.4, "wkg_activity_id": "i100"},
                {"secs": 60, "watts": 380, "activity_id": "i102", "watts_per_kg": 5.07, "wkg_activity_id": "i102"},
                {"secs": 3600, "watts": 210, "activity_id": "i107", "watts_per_kg": 2.8, "wkg_activity_id": "i107"},
            ],
        },
    ]
    result = format_power_curves(curves, "Ride", include_normalised=True)
    assert "Power Curves (Ride):" in result
    assert "This season" in result
    assert "5s: 780W" in result
    assert "10.40W/kg" in result
    assert "1m: 380W" in result
    assert "1h: 210W" in result
    assert "i100" in result
    assert "i107" in result


def test_format_power_curves_without_normalised():
    """
    Test that format_power_curves without normalised data does not include W/kg.
    """
    curves = [
        {
            "id": "s0",
            "label": "This season",
            "start": "",
            "end": "",
            "data_points": [
                {"secs": 5, "watts": 780, "activity_id": "i100"},
            ],
        },
    ]
    result = format_power_curves(curves, "Ride", include_normalised=False)
    assert "780W" in result
    assert "W/kg" not in result
