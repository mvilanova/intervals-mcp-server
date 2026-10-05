"""
Tests for the get_coach_report MCP tool with a mocked Intervals.icu API (no network).
"""

# pylint: disable=missing-function-docstring

import asyncio
import json
import os
import pathlib
import sys
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.server import get_coach_report  # pylint: disable=wrong-import-position  # noqa: E402
from intervals_mcp_server.tools import coach_report as tool_module  # pylint: disable=wrong-import-position  # noqa: E402
from tests.coach_fixtures import END, TODAY, projection_scenario, realistic_scenario  # pylint: disable=wrong-import-position  # noqa: E402

SNAPSHOT = pathlib.Path(__file__).resolve().parent / "ressources" / "coach_report_v1_0.json"
WEEK_END = TODAY + timedelta(days=6)


def _filter_events(events, params):
    """Emulate the date window and category filter of GET /athlete/{id}/events."""
    selected = [e for e in events if params["oldest"] <= e["start_date_local"][:10] <= params["newest"]]
    if "category" in params:
        selected = [e for e in selected if e["category"] in params["category"].split(",")]
    return selected


def _projection_data():
    """API responses for the morning of TODAY with 2026-W40 planned."""
    activities, wellness, athlete, events = projection_scenario()
    return {"athlete": athlete, "activities": activities, "wellness": wellness, "events": events}


def _fake_api(monkeypatch, overrides=None, today=TODAY):
    """Route requests by URL suffix to fixture data and record them.

    ``today`` is the athlete's current day (default: the Monday after END).
    """
    activities, wellness, athlete = realistic_scenario()
    responses = {"athlete": athlete, "activities": activities, "wellness": wellness, "events": []}
    responses.update(overrides or {})
    calls = []

    async def fake_request(url, api_key=None, params=None, method="GET", data=None):  # pylint: disable=unused-argument
        calls.append((url, params))
        if url.endswith("/activities"):
            return responses["activities"]
        if url.endswith("/wellness"):
            return responses["wellness"]
        if url.endswith("/events"):
            result = responses["events"]
            return _filter_events(result, params) if isinstance(result, list) else result
        return responses["athlete"]

    monkeypatch.setattr(tool_module, "make_intervals_request", fake_request)
    monkeypatch.setattr(tool_module, "_athlete_today", lambda athlete: today)
    return calls


def test_get_coach_report_returns_compact_json(monkeypatch):
    calls = _fake_api(monkeypatch)
    result = asyncio.run(get_coach_report(days=28, end_date=END.isoformat()))
    report = json.loads(result)
    assert report["schema_version"] == "1.1"
    assert report["period"]["mode"] == "actual"
    assert report["period"]["end"] == END.isoformat()
    assert len(result.encode("utf-8")) < 4096
    assert " " not in result.split('"code"')[0]  # compact separators
    params = {url.rsplit("/", 1)[-1]: p for url, p in calls}
    assert params["activities"] == {"oldest": "2026-08-30", "newest": "2026-09-28"}
    assert params["wellness"] == {"oldest": "2026-07-30", "newest": "2026-09-27"}
    assert all(url == "/athlete/i1" or url.startswith("/athlete/i1/") for url, _ in calls)


def test_get_coach_report_short_window_still_fetches_fixed_windows(monkeypatch):
    calls = _fake_api(monkeypatch)
    report = json.loads(asyncio.run(get_coach_report(days=7, end_date=END.isoformat())))
    assert report["period"]["days"] == 7
    assert len(report["volume"]) == 1
    params = {url.rsplit("/", 1)[-1]: p for url, p in calls}
    assert params["activities"]["oldest"] == "2026-08-30"


def test_get_coach_report_default_end_uses_athlete_timezone(monkeypatch):
    _fake_api(monkeypatch)
    monkeypatch.setattr(tool_module, "_athlete_today", lambda athlete: END)
    report = json.loads(asyncio.run(get_coach_report()))
    assert report["period"]["end"] == END.isoformat()
    assert report["period"]["load_end"] == END.isoformat()  # END already has an activity
    assert report["period"]["days"] == 28


def test_get_coach_report_morning_without_activity_ends_load_yesterday(monkeypatch):
    _fake_api(monkeypatch)
    today = END + timedelta(days=1)  # Monday, no activity recorded yet
    monkeypatch.setattr(tool_module, "_athlete_today", lambda athlete: today)
    report = json.loads(asyncio.run(get_coach_report()))
    assert report["period"]["end"] == today.isoformat()
    assert report["period"]["load_end"] == END.isoformat()
    assert report["period"]["start"] == "2026-08-31"
    assert [week["week"] for week in report["volume"]][-1] == "2026-W39"


def test_get_coach_report_explicit_end_date_is_not_shifted(monkeypatch):
    _fake_api(monkeypatch)
    today = END + timedelta(days=1)
    report = json.loads(asyncio.run(get_coach_report(end_date=today.isoformat())))
    assert report["period"]["load_end"] == today.isoformat()


def test_athlete_today_timezone_handling():
    assert isinstance(tool_module._athlete_today({"timezone": "Europe/Berlin"}), date)  # pylint: disable=protected-access
    assert tool_module._athlete_today({"timezone": "Not/AZone"}) == date.today()  # pylint: disable=protected-access
    assert tool_module._athlete_today(None) == date.today()  # pylint: disable=protected-access


def test_get_coach_report_validates_input(monkeypatch):
    calls = _fake_api(monkeypatch)
    assert asyncio.run(get_coach_report(days=3)).startswith("Error: days must be between 7 and 90")
    assert asyncio.run(get_coach_report(days=91)).startswith("Error: days must be between 7 and 90")
    for bad_date in ("27.09.2026", "2026-9-7", "2026-02-30", "2026-W39-1", "9999-12-31", "0001-01-01", "2026-09-27/../x"):
        result = asyncio.run(get_coach_report(end_date=bad_date))
        assert result.startswith("Error: end_date must be a valid date in YYYY-MM-DD format"), bad_date
    assert not calls


def test_get_coach_report_passes_api_errors_through(monkeypatch):
    _fake_api(monkeypatch, {"activities": {"error": True, "message": "401 Unauthorized"}})
    result = asyncio.run(get_coach_report(end_date=END.isoformat()))
    assert result == "Error fetching activities: 401 Unauthorized"

    _fake_api(monkeypatch, {"wellness": {"error": True, "message": "boom"}})
    assert asyncio.run(get_coach_report(end_date=END.isoformat())) == "Error fetching wellness data: boom"

    _fake_api(monkeypatch, {"athlete": {"error": True, "message": "403 Forbidden"}})
    assert asyncio.run(get_coach_report()) == "Error fetching athlete: 403 Forbidden"


def test_get_coach_report_with_empty_data(monkeypatch):
    _fake_api(monkeypatch, {"activities": [], "wellness": [], "athlete": {}})
    report = json.loads(asyncio.run(get_coach_report(end_date=END.isoformat())))
    assert report["load"]["acwr"] is None
    assert report["recovery"]["hrv"]["status"] == "insufficient_data"


def test_actual_mode_matches_schema_1_0_snapshot(monkeypatch):
    """Without a future end date only schema_version and period.mode change."""
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    _fake_api(monkeypatch)
    for key, kwargs in (("default", {}), ("explicit_end", {"end_date": END.isoformat()})):
        report = json.loads(asyncio.run(get_coach_report(**kwargs)))
        assert report["schema_version"] == "1.1"
        assert report["period"].pop("mode") == "actual"
        report["schema_version"] = "1.0"
        assert report == snapshot[key], key


def test_future_end_date_gives_projection_with_plan(monkeypatch):
    calls = _fake_api(monkeypatch, _projection_data())
    report = json.loads(asyncio.run(get_coach_report(days=14, end_date=WEEK_END.isoformat())))
    assert report["period"]["mode"] == "projection"
    assert report["period"]["load_end"] == END.isoformat()  # nothing recorded today yet
    codes = {flag["code"] for flag in report["flags"]}
    assert "acwr_low" not in codes and "hrv_insufficient" not in codes
    assert report["load"]["deload"] is False
    assert report["recovery"]["as_of"] == TODAY.isoformat()

    week = report["plan"]["weeks"][0]
    assert report["plan"]["from"] == TODAY.isoformat()
    assert week["week"] == "2026-W40"
    assert week["load"] == 79 + 56 + 211 + 211 + 211 + 49  # planned loads of the mocked events
    assert week["missing_load"] == 2
    assert [race["name"] for race in report["plan"]["races"]] == ["Club TT", "Gravel race"]  # deduplicated

    wellness_by_id = {record["id"]: record for record in _projection_data()["wellness"]}
    assert report["load"]["src"] == "api_incl_planned"
    assert report["load"]["projected"]["ctl"] == round(wellness_by_id[WEEK_END.isoformat()]["ctl"], 1)
    assert report["load"]["projected"]["ctl"] > report["load"]["actual"]["ctl"]

    params = {(url.rsplit("/", 1)[-1], "category" in (p or {})): p for url, p in calls}
    assert params[("events", False)] == {"oldest": "2026-09-28", "newest": "2026-10-04"}
    assert params[("events", True)] == {
        "oldest": "2026-09-28", "newest": "2026-12-21", "category": "RACE_A,RACE_B,RACE_C",
    }
    assert params[("activities", False)] == {"oldest": "2026-08-31", "newest": "2026-09-29"}
    assert params[("wellness", False)] == {"oldest": "2026-07-31", "newest": "2026-10-04"}


def test_projection_after_first_activity_plans_from_tomorrow(monkeypatch):
    data = _projection_data()
    data["activities"] = data["activities"] + [
        {"type": "Ride", "start_date_local": f"{TODAY.isoformat()}T07:00:00", "icu_training_load": 40, "moving_time": 3600}
    ]
    _fake_api(monkeypatch, data)
    report = json.loads(asyncio.run(get_coach_report(days=14, end_date=WEEK_END.isoformat())))
    assert report["period"]["load_end"] == TODAY.isoformat()
    week = report["plan"]["weeks"][0]
    assert report["plan"]["from"] == (TODAY + timedelta(days=1)).isoformat()
    assert (week["days"], week["done_load"]) == (6, 40)


def test_end_date_too_far_ahead_is_rejected(monkeypatch):
    calls = _fake_api(monkeypatch)
    result = asyncio.run(get_coach_report(end_date=(TODAY + timedelta(days=91)).isoformat()))
    assert result == "Error: end_date may be at most 90 days after today (2026-09-28)."
    assert len(calls) == 1  # only the athlete
    assert asyncio.run(get_coach_report(end_date=(TODAY + timedelta(days=90)).isoformat())).startswith("{")


def test_projection_passes_event_errors_through(monkeypatch):
    _fake_api(monkeypatch, {"events": {"error": True, "message": "boom"}})
    result = asyncio.run(get_coach_report(end_date=WEEK_END.isoformat()))
    assert result == "Error fetching events: boom"


def _athlete_ids(calls):
    return {url.split("/")[2] for url, _ in calls}


def test_get_coach_report_uses_given_athlete_id(monkeypatch):
    monkeypatch.setattr(tool_module.config, "athlete_id", "i1")
    calls = _fake_api(monkeypatch, _projection_data())
    report = json.loads(asyncio.run(get_coach_report(end_date=WEEK_END.isoformat(), athlete_id="i2")))
    assert report["period"]["mode"] == "projection"
    assert {url.rsplit("/", 1)[-1] for url, _ in calls} == {"i2", "activities", "wellness", "events"}
    assert _athlete_ids(calls) == {"i2"}


def test_get_coach_report_defaults_to_configured_athlete(monkeypatch):
    monkeypatch.setattr(tool_module.config, "athlete_id", "i1")
    for athlete_id in (None, "", "  "):
        calls = _fake_api(monkeypatch)
        assert asyncio.run(get_coach_report(end_date=END.isoformat(), athlete_id=athlete_id)).startswith("{")
        assert _athlete_ids(calls) == {"i1"}, athlete_id


def test_get_coach_report_rejects_invalid_athlete_id(monkeypatch):
    calls = _fake_api(monkeypatch)
    for athlete_id in ("i2/events", "../i1", "abc"):
        result = asyncio.run(get_coach_report(athlete_id=athlete_id))
        assert result.startswith("Error: athlete_id must be all digits"), athlete_id
    assert not calls
