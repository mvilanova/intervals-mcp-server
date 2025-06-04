"""
Sample data for testing Intervals.icu MCP server functions.

This module contains test data structures used across the test suite.
"""

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
