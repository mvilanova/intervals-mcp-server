"""
Unit tests for formatting utilities in intervals_mcp_server.utils.formatting.

These tests verify that the formatting functions produce expected output strings for activities, workouts, wellness entries, events, and intervals.
"""

import json
from intervals_mcp_server.utils.formatting import (
    _detect_custom_fields,
    _format_custom_fields,
    _is_camelcase,
    format_activity_summary,
    format_workout,
    format_wellness_entry,
    format_event_summary,
    format_event_details,
    format_intervals,
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
    with open("tests/ressources/wellness_entry.json", "r", encoding="utf-8") as f:
        entry = json.load(f)
    result = format_wellness_entry(entry)

    with open("tests/ressources/wellness_entry_formatted.txt", "r", encoding="utf-8") as f:
        expected_result = f.read()
    assert result == expected_result


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


def test_is_camelcase():
    """Test _is_camelcase function with various field name patterns."""
    # Valid camelCase fields
    assert _is_camelcase("customField") is True
    assert _is_camelcase("myCustomMetric") is True
    assert _is_camelcase("avgPower") is True
    assert _is_camelcase("restingHR") is True

    # Invalid patterns (not camelCase)
    assert _is_camelcase("custom_field") is False  # snake_case
    assert _is_camelcase("CustomField") is False  # PascalCase
    assert _is_camelcase("customfield") is False  # all lowercase
    assert _is_camelcase("CUSTOMFIELD") is False  # all uppercase
    assert _is_camelcase("") is False  # empty string
    assert _is_camelcase("custom") is False  # no uppercase


def test_detect_custom_fields():
    """Test _detect_custom_fields function."""
    # Test with custom camelCase fields
    data = {
        "name": "Test Activity",
        "id": 1,
        "customField": "custom value",
        "anotherCustomMetric": 123,
        "knownField": "known value",
    }
    known_fields = {"name", "id", "knownField"}
    custom_fields = _detect_custom_fields(data, known_fields)
    assert "customField" in custom_fields
    assert "anotherCustomMetric" in custom_fields
    assert "name" not in custom_fields
    assert "id" not in custom_fields
    assert "knownField" not in custom_fields

    # Test with only known fields
    data2 = {"name": "Test", "id": 1}
    known_fields2 = {"name", "id"}
    custom_fields2 = _detect_custom_fields(data2, known_fields2)
    assert len(custom_fields2) == 0

    # Test with empty dictionary
    custom_fields3 = _detect_custom_fields({}, set())
    assert len(custom_fields3) == 0

    # Test with snake_case fields (should be excluded)
    data4 = {
        "custom_field": "value",
        "customField": "value",
    }
    custom_fields4 = _detect_custom_fields(data4, set())
    assert "customField" in custom_fields4
    assert "custom_field" not in custom_fields4

    # Test with null values
    data5 = {"customField": None, "anotherField": "value"}
    custom_fields5 = _detect_custom_fields(data5, set())
    assert "customField" in custom_fields5
    assert custom_fields5["customField"] is None


def test_format_custom_fields():
    """Test _format_custom_fields function."""
    # Test with various value types
    custom_fields = {
        "customField": "string value",
        "numericField": 123,
        "floatField": 45.67,
        "boolField": True,
        "nullField": None,
        "listField": [1, 2, 3],
    }
    formatted = _format_custom_fields(custom_fields)
    assert len(formatted) == 6
    assert any("Custom Field" in line and "string value" in line for line in formatted)
    assert any("Numeric Field" in line and "123" in line for line in formatted)
    assert any("Float Field" in line and "45.67" in line for line in formatted)
    assert any("Bool Field" in line and "True" in line for line in formatted)
    assert any("Null Field" in line and "N/A" in line for line in formatted)
    assert any("List Field" in line and "[1, 2, 3]" in line for line in formatted)

    # Test with empty dictionary
    formatted_empty = _format_custom_fields({})
    assert len(formatted_empty) == 0

    # Test that fields are sorted alphabetically
    custom_fields2 = {
        "zebraField": "z",
        "alphaField": "a",
        "betaField": "b",
    }
    formatted2 = _format_custom_fields(custom_fields2)
    assert formatted2[0].startswith("- Alpha Field")
    assert formatted2[1].startswith("- Beta Field")
    assert formatted2[2].startswith("- Zebra Field")

    # Test edge case: single character field (should not cause IndexError)
    custom_fields3 = {"a": "value"}
    formatted3 = _format_custom_fields(custom_fields3)
    assert len(formatted3) == 1
    assert "A" in formatted3[0] or "a" in formatted3[0]

    # Test edge case: empty key (defensive test - shouldn't happen in practice but guards against IndexError)
    # This tests the defensive code path when both formatted_key and key could be empty
    custom_fields4 = {"": "value"}
    formatted4 = _format_custom_fields(custom_fields4)
    # Should handle gracefully without IndexError
    assert len(formatted4) == 1
    assert "Unknown" in formatted4[0] or "value" in formatted4[0]


def test_format_activity_summary_with_custom_fields():
    """Test that format_activity_summary includes custom fields when present."""
    activity = {
        "name": "Morning Ride",
        "id": 1,
        "type": "Ride",
        "startTime": "2024-01-01T08:00:00Z",
        "distance": 1000,
        "duration": 3600,
        "customField": "custom value",
        "anotherCustomMetric": 42,
    }
    result = format_activity_summary(activity)
    assert "Activity: Morning Ride" in result
    assert "ID: 1" in result
    assert "Custom Fields:" in result
    assert "Custom Field" in result or "customField" in result
    assert "custom value" in result
    assert "42" in result

    # Test without custom fields
    activity2 = {
        "name": "Morning Ride",
        "id": 1,
        "type": "Ride",
        "startTime": "2024-01-01T08:00:00Z",
        "distance": 1000,
        "duration": 3600,
    }
    result2 = format_activity_summary(activity2)
    assert "Custom Fields:" not in result2


def test_format_wellness_entry_with_custom_fields():
    """Test that format_wellness_entry includes custom fields when present."""
    entry = {
        "id": "2024-01-01",
        "ctl": 70.0,
        "weight": 75,
        "customField": "custom value",
        "anotherCustomMetric": 99,
    }
    result = format_wellness_entry(entry)
    assert "Wellness Data:" in result
    assert "Date: 2024-01-01" in result
    assert "Custom Fields:" in result
    assert "Custom Field" in result or "customField" in result
    assert "custom value" in result
    assert "99" in result

    # Test without custom fields
    entry2 = {
        "id": "2024-01-01",
        "ctl": 70.0,
        "weight": 75,
    }
    result2 = format_wellness_entry(entry2)
    assert "Custom Fields:" not in result2
