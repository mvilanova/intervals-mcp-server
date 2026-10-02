"""
Unit tests for the get_hr_curves and get_pace_curves MCP tools.

The API is mocked with synthetic data; no network access is performed.
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.server import (  # pylint: disable=wrong-import-position
    get_hr_curves,
    get_pace_curves,
)

HR_CURVES_DATA = {
    "list": [
        {
            "id": "90d",
            "label": "90 days",
            "start_date_local": "2026-07-04T00:00:00",
            "end_date_local": "2026-10-02T00:00:00",
            "secs": [1, 5, 15, 30, 60, 300, 600, 1200, 1800, 3600],
            "values": [180, 178, 176, 174, 172, 168, 165, 160, 156, 150],
            "activity_id": ["i1"] * 10,
        }
    ],
    "activities": {},
}

PACE_CURVES_DATA = {
    "list": [
        {
            "id": "1y",
            "label": "1 year",
            "start_date_local": "2025-10-03T00:00:00",
            "end_date_local": "2026-10-03T00:00:00",
            "distance": [100.0, 400.0, 1000.0, 5000.0, 10000.0],
            "values": [20, 100, 270, 1500, 3200],
            "activity_id": ["i1", "i2", "i3", "i4", "i5"],
            "type": "PACE",
        }
    ],
    "activities": {},
}

SWIM_CURVES_DATA = {
    "list": [
        {
            "id": "1y",
            "label": "1 year",
            "distance": [50.0, 100.0, 200.0],
            "values": [45, 100, 215],
            "activity_id": ["i1", "i2", "i3"],
        }
    ]
}


def _patch(monkeypatch, response, captured=None):
    async def fake_request(*_args, **kwargs):
        if captured is not None:
            captured.update(kwargs)
        return response

    monkeypatch.setattr(
        "intervals_mcp_server.tools.hr_pace_curves.make_intervals_request", fake_request
    )


def test_get_hr_curves(monkeypatch):
    """Default durations are extracted and rendered as bpm."""
    captured: dict = {}
    _patch(monkeypatch, HR_CURVES_DATA, captured)
    result = asyncio.run(get_hr_curves(athlete_id="i1"))
    assert captured["url"] == "/athlete/i1/hr-curves"
    assert captured["params"] == {"curves": ["90d"], "type": "Run"}
    assert "Heart Rate Curves (Run):" in result
    assert "90 days (2026-07-04 to 2026-10-02):" in result
    assert "5s: 178bpm" in result
    assert "1h: 150bpm" in result
    assert "15m:" not in result


def test_get_hr_curves_custom_range_and_durations(monkeypatch):
    """Curve ids and a date range are combined; only requested durations are shown."""
    captured: dict = {}
    _patch(monkeypatch, HR_CURVES_DATA, captured)
    result = asyncio.run(
        get_hr_curves(
            durations=[60, 90],
            curves=["1y"],
            start_date="2026-01-01",
            end_date="2026-03-01",
            athlete_id="i1",
        )
    )
    assert captured["params"]["curves"] == ["1y", "r.2026-01-01.2026-03-01"]
    assert "1m: 172bpm" in result
    assert "5s:" not in result
    assert "Not available: 1m30s" in result


def test_get_hr_curves_validation_and_errors(monkeypatch):
    """Date validation, empty results and API errors are reported."""
    _patch(monkeypatch, HR_CURVES_DATA)
    assert "Both start_date and end_date" in asyncio.run(
        get_hr_curves(start_date="2026-01-01", athlete_id="i1")
    )
    _patch(monkeypatch, {"list": []})
    assert "No HR curve data found" in asyncio.run(get_hr_curves(athlete_id="i1"))
    _patch(monkeypatch, {"error": True, "message": "Boom"})
    assert "Error fetching HR curves: Boom" in asyncio.run(get_hr_curves(athlete_id="i1"))


def test_get_pace_curves(monkeypatch):
    """Times and min/km pace are rendered for the default run distances."""
    captured: dict = {}
    _patch(monkeypatch, PACE_CURVES_DATA, captured)
    result = asyncio.run(get_pace_curves(athlete_id="i1", curves=["1y"]))
    assert captured["url"] == "/athlete/i1/pace-curves"
    assert captured["params"] == {"curves": ["1y"], "type": "Run"}
    assert "Pace Curves (Run):" in result
    assert "400m: 1:40 (4:10/km) [i2]" in result
    assert "1km: 4:30 (4:30/km) [i3]" in result
    assert "5km: 25:00 (5:00/km) [i4]" in result
    assert "10km: 53:20 (5:20/km) [i5]" in result
    assert "800m:" not in result
    assert "Not available: 800m, 3km, 21.1km, 42.2km" in result


def test_get_pace_curves_gap_and_custom_distances(monkeypatch):
    """The gap flag is forwarded and labels the output."""
    captured: dict = {}
    _patch(monkeypatch, PACE_CURVES_DATA, captured)
    result = asyncio.run(get_pace_curves(distances=[5000], gap=True, athlete_id="i1"))
    assert captured["params"]["gap"] is True
    assert "GAP Curves (Run):" in result
    assert "5km:" in result
    assert "1km:" not in result


def test_get_pace_curves_swim(monkeypatch):
    """Swims use min/100m and swim default distances."""
    _patch(monkeypatch, SWIM_CURVES_DATA)
    result = asyncio.run(get_pace_curves(activity_type="Swim", athlete_id="i1"))
    assert "100m: 1:40 (1:40/100m) [i2]" in result
    assert "200m: 3:35 (1:48/100m) [i3]" in result


def test_get_pace_curves_validation_and_errors(monkeypatch):
    """Date validation, empty results and API errors are reported."""
    _patch(monkeypatch, PACE_CURVES_DATA)
    assert "start_date must be before end_date" in asyncio.run(
        get_pace_curves(start_date="2026-03-01", end_date="2026-01-01", athlete_id="i1")
    )
    _patch(monkeypatch, {"list": []})
    assert "No pace curve data found" in asyncio.run(get_pace_curves(athlete_id="i1"))
    _patch(monkeypatch, {"error": True, "message": "Boom"})
    assert "Error fetching pace curves: Boom" in asyncio.run(get_pace_curves(athlete_id="i1"))


def test_curves_skip_none_and_zero_values(monkeypatch):
    """None/0 values are reported as not available, never rendered (no 0:00 pace)."""
    data = {
        "list": [
            {
                "id": "1y",
                "distance": [400.0, 1000.0, 5000.0],
                "values": [0, None, 1500],
                "activity_id": ["i1", "i2", "i3"],
            }
        ]
    }
    _patch(monkeypatch, data)
    result = asyncio.run(get_pace_curves(distances=[400, 1000, 5000], athlete_id="i1"))
    assert "5km: 25:00" in result
    assert "0:00" not in result
    assert "Not available: 400m, 1km" in result

    hr = {
        "list": [{"id": "90d", "secs": [5, 60], "values": [None, 150], "activity_id": ["a", "b"]}]
    }
    _patch(monkeypatch, hr)
    result = asyncio.run(get_hr_curves(durations=[5, 60], athlete_id="i1"))
    assert "1m: 150bpm" in result
    assert "Not available: 5s" in result
