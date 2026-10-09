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

# Custom item definitions as returned by /athlete/{id}/custom-item (reduced).
CUSTOM_ITEMS_DATA = [
    {
        "id": 1,
        "type": "ACTIVITY_FIELD",
        "name": "Aerobic Effect",
        "content": {"code": "AerobicEffect", "type": "numeric", "units": None,
                    "fit_session_field": "total_training_effect"},
    },
    {
        "id": 2,
        "type": "ACTIVITY_FIELD",
        "name": "EPOC",
        "content": {"code": "EPOC", "type": "numeric", "units": "ml/kg", "fit_session_field": "178"},
    },
    {
        "id": 3,
        "type": "ACTIVITY_FIELD",
        "name": "Training Effect",
        "content": {
            "code": "TrainingEffectSelect",
            "type": "select",
            "options": [{"text": "Recovery", "value": 1.0}, {"text": "Base", "value": 2.0}],
        },
    },
    {
        "id": 4,
        "type": "ACTIVITY_FIELD",
        "name": "Flight Time",
        "content": {"code": "FlightTime", "type": "numeric"},
    },
    {
        "id": 5,
        "type": "ACTIVITY_FIELD",
        "name": "Sweat loss",
        "content": {"code": "Sweatloss", "type": "numeric", "units": "ml", "fit_session_field": "178"},
    },
    {
        "id": 6,
        "type": "INTERVAL_FIELD",
        "name": "Elapsed Time",
        "content": {"code": "ElapsedTime", "type": "numeric", "script": "interval.elapsed_time"},
    },
    {
        "id": 7,
        "type": "ACTIVITY_STREAM",
        "name": "Garmin Stamina",
        "description": "Stamina",
        "content": {"code": "Stamina", "type": "numeric", "units": "point", "script": "..."},
    },
    {
        "id": 8,
        "type": "INPUT_FIELD",
        "name": "Garmin Deep Sleep",
        "content": {"code": "GarminSleepDeepMinutes", "type": "numeric", "units": "min"},
    },
    {"id": 9, "type": "FITNESS_CHART", "name": "Some chart", "content": {"x": 1}},
]

# Activity payload carrying custom field values as top-level keys.
ACTIVITY_WITH_CUSTOM_FIELDS = {
    "id": "i1",
    "name": "Sweet Spot",
    "type": "Ride",
    "start_date_local": "2026-10-06T17:36:22",
    "icu_athlete_id": "i1",
    "distance": 40000,
    "elapsed_time": 4967,
    "moving_time": 4861,
    "AerobicEffect": 3.5,
    "EPOC": 129.58348,
    "TrainingEffectSelect": 2.0,
    "FlightTime": float("nan"),
    "Sweatloss": 0.0,
    "stream_types": ["time", "watts", "heartrate", "secondary_power", "Stamina"],
    "power_field_names": ["power", "Power2"],
    "icu_zone_times": [{"id": "Z1", "secs": 910}, {"id": "Z2", "secs": 1489}],
}

# Sample-aligned streams (12 samples, recording pause between index 5 and 6).
STREAMS_DATA = [
    {"type": "time", "name": None, "custom": False,
     "data": [0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 15]},
    {"type": "watts", "name": None, "custom": False,
     "data": [100, 110, 120, 130, 140, 150, 200, 210, 220, 230, 240, 250]},
    {"type": "heartrate", "name": None, "custom": False,
     "data": [120, 121, 122, None, 124, 125, 140, 141, 142, 143, 144, 145]},
    {"type": "latlng", "name": None, "custom": False,
     "data": [47.1, 47.11, 47.12, 47.13, 47.14, 47.15, 47.2, 47.21, 47.22, 47.23, 47.24, 47.25],
     "data2": [12.1, 12.11, 12.12, 12.13, 12.14, 12.15, 12.2, 12.21, 12.22, 12.23, 12.24, 12.25]},
    {"type": "hrv", "name": None, "custom": False, "valueTypeIsArray": True,
     "data": [[736], [731], [712, 680], [691], [700], [702], [650], [640], [630], [620], [610], [600]]},
    {"type": "secondary_power", "name": "Power2", "custom": False,
     "data": [98, 108, 118, 128, 138, 148, 198, 208, 218, 228, 238, 248]},
    {"type": "Stamina", "name": None, "custom": True,
     "data": [100, 100, 99, 99, 98, 98, 97, 96, 95, 94, 93, float("nan")]},
]

# Intervals with sample indices matching STREAMS_DATA.
INTERVALS_WITH_INDICES = {
    "id": "i1",
    "analyzed": True,
    "icu_intervals": [
        {"type": "WORK", "label": "Warmup", "start_index": 0, "end_index": 6, "start_time": 0,
         "end_time": 10, "elapsed_time": 10, "moving_time": 6, "group_id": "g1",
         "ElapsedTime": 10.0, "average_watts": 125},
        {"type": "WORK", "label": "Rep 1", "start_index": 6, "end_index": 12, "start_time": 10,
         "end_time": 16, "elapsed_time": 6, "moving_time": 6, "group_id": "g1",
         "ElapsedTime": 6.0, "average_watts": 225},
    ],
    "icu_groups": [
        {"id": "g1", "count": 2, "start_index": 0, "elapsed_time": 16, "moving_time": 12,
         "average_watts": 175},
    ],
}
