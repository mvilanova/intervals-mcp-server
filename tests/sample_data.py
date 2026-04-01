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

POWER_CURVES_DATA = {
    "list": [
        {
            "id": "s0",
            "label": "This season",
            "start_date_local": "2025-09-29T00:00:00",
            "end_date_local": "2026-03-14T00:00:00",
            "days": 167,
            "weight": 75.0,
            "secs": [1, 2, 3, 4, 5, 10, 15, 30, 60, 120, 300, 600, 1200, 3600],
            "values": [900, 850, 820, 800, 780, 650, 550, 450, 380, 320, 280, 260, 245, 210],
            "activity_id": [
                "i100", "i100", "i100", "i100", "i100",
                "i101", "i101", "i101", "i102",
                "i103", "i104", "i105", "i106", "i107",
            ],
            "watts_per_kg": [
                12.0, 11.33, 10.93, 10.67, 10.4,
                8.67, 7.33, 6.0, 5.07,
                4.27, 3.73, 3.47, 3.27, 2.8,
            ],
            "wkg_activity_id": [
                "i100", "i100", "i100", "i100", "i100",
                "i101", "i101", "i101", "i102",
                "i103", "i104", "i105", "i106", "i107",
            ],
        },
        {
            "id": "s1",
            "label": "Last season",
            "start_date_local": "2024-09-29T00:00:00",
            "end_date_local": "2025-09-28T00:00:00",
            "days": 365,
            "weight": 76.0,
            "secs": [1, 2, 3, 4, 5, 10, 15, 30, 60, 120, 300, 600, 1200, 3600],
            "values": [870, 830, 800, 770, 750, 630, 520, 430, 360, 300, 265, 250, 235, 200],
            "activity_id": [
                "i200", "i200", "i200", "i200", "i200",
                "i201", "i201", "i201", "i202",
                "i203", "i204", "i205", "i206", "i207",
            ],
            "watts_per_kg": [
                11.45, 10.92, 10.53, 10.13, 9.87,
                8.29, 6.84, 5.66, 4.74,
                3.95, 3.49, 3.29, 3.09, 2.63,
            ],
            "wkg_activity_id": [
                "i200", "i200", "i200", "i200", "i200",
                "i201", "i201", "i201", "i202",
                "i203", "i204", "i205", "i206", "i207",
            ],
        },
    ]
}
