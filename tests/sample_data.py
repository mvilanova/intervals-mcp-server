"""
Sample data for testing Intervals.icu MCP server functions.

This module contains test data structures used across the test suite.
"""

SAMPLE_ACTIVITY = {
    "name": "Morning Ride",
    "id": 123,
    "type": "Ride",
    "startTime": "2024-01-01T08:00:00Z",
    "distance": 1000,
    "duration": 3600,
}

SAMPLE_EVENT = {
    "id": "e1",
    "date": "2024-01-01",
    "name": "Test Event",
    "description": "desc",
    "race": True,
}

INTERVALS_DATA = {
    "id": "i1",
    "analyzed": True,
    "icu_intervals": [
        {
            "type": "work",
            "label": "Rep 1",
            "elapsed_time": 60,
            "moving_time": 60,
            "distance": 100,
            "average_watts": 200,
            "max_watts": 300,
            "average_watts_kg": 3.0,
            "max_watts_kg": 5.0,
            "weighted_average_watts": 220,
            "intensity": 0.8,
            "training_load": 10,
            "average_heartrate": 150,
            "max_heartrate": 160,
            "average_cadence": 90,
            "max_cadence": 100,
            "average_speed": 6,
            "max_speed": 8,
        }
    ],
}
