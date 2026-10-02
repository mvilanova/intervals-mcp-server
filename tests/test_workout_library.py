"""
Unit tests for the workout library tools:
- get_workout_library
- create_library_workout
- add_event_from_library
"""

import asyncio
import os
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.server import (  # pylint: disable=wrong-import-position
    add_event_from_library,
    create_library_workout,
    delete_library_workout,
    get_workout_library,
)

TARGET = "intervals_mcp_server.tools.workout_library.make_intervals_request"

FOLDERS = [
    {
        "id": 10,
        "type": "FOLDER",
        "name": "Cycling",
        "children": [
            {
                "id": 101,
                "name": "Sweet Spot 3x10",
                "type": "Ride",
                "moving_time": 5400,
                "icu_training_load": 80,
                "description": "- 10m 55%\n3x\n- 10m 90%\n- 5m 55%",
                "folder_id": 10,
            }
        ],
    },
    {"id": 11, "type": "PLAN", "name": "Strength", "children": []},
]


def _patch(monkeypatch, responder) -> list[dict[str, Any]]:
    """Patch make_intervals_request with a responder; returns the list of recorded calls."""
    calls: list[dict[str, Any]] = []

    async def fake(url, api_key=None, params=None, method="GET", data=None):
        calls.append({"url": url, "method": method, "data": data})
        return responder(url, method)

    monkeypatch.setattr(TARGET, fake)
    return calls


def test_get_workout_library(monkeypatch):
    """All folders and their workouts are listed."""
    _patch(monkeypatch, lambda url, method: FOLDERS)
    result = asyncio.run(get_workout_library(athlete_id="i1"))
    assert "FOLDER: Cycling (id: 10) - 1 workouts" in result
    assert "id: 101" in result and "Sweet Spot 3x10" in result
    assert "duration: 1h30m" in result and "load: 80" in result
    assert "description: - 10m 55%..." in result
    assert "PLAN: Strength" in result


def test_get_workout_library_folder_filter(monkeypatch):
    """Folder filter works by case-insensitive name and by id."""
    _patch(monkeypatch, lambda url, method: FOLDERS)
    by_name = asyncio.run(get_workout_library(folder="cycling", athlete_id="i1"))
    assert "Cycling" in by_name and "Strength" not in by_name
    by_id = asyncio.run(get_workout_library(folder="11", athlete_id="i1"))
    assert "Strength" in by_id and "Cycling" not in by_id
    missing = asyncio.run(get_workout_library(folder="nope", athlete_id="i1"))
    assert "No folder matching 'nope'" in missing


def test_get_workout_library_empty_and_error(monkeypatch):
    """Empty library and API errors give readable messages."""
    _patch(monkeypatch, lambda url, method: [])
    assert "No workout library found" in asyncio.run(get_workout_library(athlete_id="i1"))
    _patch(monkeypatch, lambda url, method: {"error": True, "message": "boom"})
    result = asyncio.run(get_workout_library(athlete_id="i1"))
    assert "Error fetching workout library: boom" in result


def test_create_library_workout_only_passed_fields(monkeypatch):
    """Only passed fields are sent; folder name is resolved to its id."""

    def responder(url, method):
        return FOLDERS if method == "GET" else {"id": 555}

    calls = _patch(monkeypatch, responder)
    result = asyncio.run(
        create_library_workout(
            name="Sweet Spot 3x10",
            sport_type="Ride",
            folder="CYCLING",
            description="- 10m 55%",
            athlete_id="i1",
        )
    )
    assert "Successfully created library workout id: 555" in result
    post = calls[-1]
    assert post["method"] == "POST" and post["url"] == "/athlete/i1/workouts"
    assert post["data"] == {
        "name": "Sweet Spot 3x10",
        "type": "Ride",
        "folder_id": 10,
        "description": "- 10m 55%",
    }


def test_create_library_workout_with_workout_doc(monkeypatch):
    """workout_doc is rendered into the description like in add_or_update_event."""
    from intervals_mcp_server.utils.types import WorkoutDoc  # pylint: disable=import-outside-toplevel

    doc = WorkoutDoc.from_dict(
        {"steps": [{"power": {"value": 80, "units": "%ftp"}, "duration": 600}]}
    )

    def responder(url, method):
        return [FOLDERS[0]] if method == "GET" else {"id": 1}

    calls = _patch(monkeypatch, responder)
    result = asyncio.run(
        create_library_workout(
            name="Z2", sport_type="Ride", workout_doc=doc, moving_time=600, athlete_id="i1"
        )
    )
    assert "Successfully created" in result
    data = calls[-1]["data"]
    assert data["folder_id"] == 10  # single folder is used implicitly
    assert data["description"] == str(doc) and data["description"]
    assert data["moving_time"] == 600
    assert "distance" not in data


def test_create_library_workout_folder_errors(monkeypatch):
    """No folders, unknown folder and ambiguous folder return explanations and do not POST."""
    calls = _patch(monkeypatch, lambda url, method: [])
    result = asyncio.run(create_library_workout(name="A", sport_type="Run", athlete_id="i1"))
    assert "no folders" in result
    assert all(c["method"] == "GET" for c in calls)

    calls = _patch(monkeypatch, lambda url, method: FOLDERS)
    unknown = asyncio.run(
        create_library_workout(name="A", sport_type="Run", folder="x", athlete_id="i1")
    )
    assert "no folder matching 'x'" in unknown and "Cycling (id 10)" in unknown
    assert all(c["method"] == "GET" for c in calls)


def test_create_library_workout_plan_and_ambiguity(monkeypatch):
    """Plans are rejected, implicit choice ignores plans, ambiguous names list matches."""
    two_folders = [
        {"id": 1, "type": "FOLDER", "name": "Bike", "children": []},
        {"id": 2, "type": "FOLDER", "name": "bike", "children": []},
        {"id": 3, "type": "PLAN", "name": "Plan", "children": []},
    ]
    calls = _patch(monkeypatch, lambda url, method: two_folders)
    plan = asyncio.run(
        create_library_workout(name="A", sport_type="Run", folder="Plan", athlete_id="i1")
    )
    assert "plans are not supported" in plan
    dup = asyncio.run(
        create_library_workout(name="A", sport_type="Run", folder="BIKE", athlete_id="i1")
    )
    assert "ambiguous" in dup and "(id 1)" in dup and "(id 2)" in dup
    multi = asyncio.run(create_library_workout(name="A", sport_type="Run", athlete_id="i1"))
    assert "multiple folders" in multi and "Plan" not in multi
    assert all(c["method"] == "GET" for c in calls)

    # Implicit choice: exactly one FOLDER next to a PLAN is used.
    def responder(url, method):
        return FOLDERS if method == "GET" else {"id": 7}

    calls = _patch(monkeypatch, responder)
    result = asyncio.run(create_library_workout(name="A", sport_type="Run", athlete_id="i1"))
    assert "Successfully" in result and calls[-1]["data"]["folder_id"] == 10

    # Only plans: no implicit target.
    _patch(monkeypatch, lambda url, method: [FOLDERS[1]])
    only_plans = asyncio.run(create_library_workout(name="A", sport_type="Run", athlete_id="i1"))
    assert "no regular folders" in only_plans


def test_get_workout_library_large_shows_counts_only(monkeypatch):
    """Unfiltered listing with more than 50 workouts shows counts; a filter shows details."""
    big = [
        {
            "id": 1,
            "type": "FOLDER",
            "name": "Big",
            "children": [{"id": i, "name": f"W{i}", "type": "Ride"} for i in range(51)],
        }
    ]
    _patch(monkeypatch, lambda url, method: big)
    result = asyncio.run(get_workout_library(athlete_id="i1"))
    assert "Big (id: 1) - 51 workouts" in result and "pass `folder`" in result.lower()
    assert "W5" not in result
    detailed = asyncio.run(get_workout_library(folder="Big", athlete_id="i1"))
    assert "name: W5 " in detailed


def test_add_event_from_library_extra_fields_and_id_validation(monkeypatch):
    """target, sub_type and carbs_per_hour are copied; non-numeric ids are rejected."""
    workout = {
        "name": "W",
        "type": "Ride",
        "target": "POWER",
        "sub_type": "COMMUTE",
        "carbs_per_hour": 60,
        "color": None,
    }

    def responder(url, method):
        return workout if method == "GET" else {"id": 1}

    calls = _patch(monkeypatch, responder)
    asyncio.run(add_event_from_library(workout_id="5", date="2026-10-05", athlete_id="i1"))
    data = calls[-1]["data"]
    assert data["target"] == "POWER" and data["sub_type"] == "COMMUTE"
    assert data["carbs_per_hour"] == 60 and "color" not in data

    calls.clear()
    for bad in ["", "../events/1", "12a", "1/2"]:
        result = asyncio.run(
            add_event_from_library(workout_id=bad, date="2026-10-05", athlete_id="i1")
        )
        assert "must be a numeric" in result
    assert not calls


def test_create_library_workout_api_error(monkeypatch):
    """API error on POST is reported."""

    def responder(url, method):
        return FOLDERS if method == "GET" else {"error": True, "message": "bad request"}

    _patch(monkeypatch, responder)
    result = asyncio.run(
        create_library_workout(name="A", sport_type="Run", folder="Cycling", athlete_id="i1")
    )
    assert "Error creating library workout: bad request" in result


def test_add_event_from_library(monkeypatch):
    """Event is created from the library workout's fields on the given date."""
    workout = {
        "id": 101,
        "name": "Sweet Spot 3x10",
        "type": "Ride",
        "description": "- 10m 55%",
        "moving_time": 5400,
        "icu_training_load": 80,
        "folder_id": 10,
        "color": None,
    }

    def responder(url, method):
        return workout if method == "GET" else {"id": 999}

    calls = _patch(monkeypatch, responder)
    result = asyncio.run(
        add_event_from_library(workout_id="101", date="2026-10-05", athlete_id="i1")
    )
    assert "Successfully created event id: 999 on 2026-10-05" in result
    assert calls[0]["url"] == "/athlete/i1/workouts/101"
    assert calls[1]["method"] == "POST" and calls[1]["url"] == "/athlete/i1/events"
    assert calls[1]["data"] == {
        "name": "Sweet Spot 3x10",
        "type": "Ride",
        "description": "- 10m 55%",
        "moving_time": 5400,
        "category": "WORKOUT",
        "start_date_local": "2026-10-05T00:00:00",
    }


def test_add_event_from_library_errors(monkeypatch):
    """Invalid date, missing workout and API errors are reported without creating an event."""
    calls = _patch(monkeypatch, lambda url, method: {})
    assert "Error" in asyncio.run(
        add_event_from_library(workout_id="1", date="not-a-date", athlete_id="i1")
    )
    assert not calls
    result = asyncio.run(add_event_from_library(workout_id="1", date="2026-10-05", athlete_id="i1"))
    assert "No library workout found with id 1" in result

    _patch(monkeypatch, lambda url, method: {"error": True, "message": "nope"})
    result = asyncio.run(add_event_from_library(workout_id="1", date="2026-10-05", athlete_id="i1"))
    assert "Error fetching library workout: nope" in result

    def responder(url, method):
        return {"name": "W", "type": "Run"} if method == "GET" else {"error": True, "message": "x"}

    _patch(monkeypatch, responder)
    result = asyncio.run(add_event_from_library(workout_id="1", date="2026-10-05", athlete_id="i1"))
    assert "Error creating event from library workout: x" in result


def test_delete_library_workout(monkeypatch):
    """The workout is looked up first, then deleted with a DELETE on its own URL."""

    def responder(url, method):
        return [101] if method == "DELETE" else {"id": 101, "name": "Sweet Spot 3x10"}

    calls = _patch(monkeypatch, responder)
    result = asyncio.run(delete_library_workout(workout_id="101", athlete_id="i1"))
    assert result == "Deleted library workout 101 'Sweet Spot 3x10'."
    assert [(c["url"], c["method"]) for c in calls] == [
        ("/athlete/i1/workouts/101", "GET"),
        ("/athlete/i1/workouts/101", "DELETE"),
    ]


def test_delete_library_workout_errors(monkeypatch):
    """Invalid ids, missing workouts and API errors never send a DELETE for the wrong target."""
    calls = _patch(monkeypatch, lambda url, method: {})
    for bad in ("", "12a", "../events/1", "1/2"):
        result = asyncio.run(delete_library_workout(workout_id=bad, athlete_id="i1"))
        assert result == "Error: workout_id must be a numeric library workout ID."
    assert not calls

    result = asyncio.run(delete_library_workout(workout_id="7", athlete_id="i1"))
    assert result == "No library workout found with id 7."
    assert [c["method"] for c in calls] == ["GET"]

    _patch(monkeypatch, lambda url, method: {"error": True, "message": "nope"})
    result = asyncio.run(delete_library_workout(workout_id="7", athlete_id="i1"))
    assert result == "Error fetching library workout: nope"

    def responder(url, method):
        return (
            {"error": True, "message": "denied"} if method == "DELETE" else {"id": 7, "name": "W"}
        )

    _patch(monkeypatch, responder)
    result = asyncio.run(delete_library_workout(workout_id="7", athlete_id="i1"))
    assert result == "Error deleting library workout: denied"
