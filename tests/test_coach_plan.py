"""
Unit tests for the plan section and projection mode of the coach report (no network).
"""

# pylint: disable=missing-function-docstring

import pathlib
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from intervals_mcp_server import coach_metrics as cm  # pylint: disable=wrong-import-position  # noqa: E402
from tests.coach_fixtures import END, TODAY, activity, event, projection_scenario, realistic_scenario, wellness  # pylint: disable=wrong-import-position  # noqa: E402
from tests.test_coach_metrics import REPORT_KEYS  # pylint: disable=wrong-import-position  # noqa: E402

WEEK_END = TODAY + timedelta(days=6)  # Sunday of 2026-W40
PROJECTION_KEYS = REPORT_KEYS[:6] + ["plan"] + REPORT_KEYS[6:]


def _plan(events, records=None, acts=None, start=TODAY, end=WEEK_END, race_until=None):
    return cm.plan_summary(events, cm.wellness_by_day(records or []), acts or [], start, end, race_until or end)


def test_plan_summary_week_sports_and_missing_load():
    _, records, _, events = projection_scenario()
    plan = _plan(events, records, race_until=TODAY + timedelta(days=84))
    assert (plan["from"], plan["to"]) == ("2026-09-28", "2026-10-04")
    week = plan["weeks"][0]
    assert {key: week[key] for key in ("week", "days", "load", "h", "n", "rest_days", "missing_load")} == {
        "week": "2026-W40", "days": 7, "load": 79 + 56 + 3 * 211 + 49, "h": 20.7, "n": 8, "rest_days": 1, "missing_load": 2,
    }
    assert week["by_sport"] == {
        cm.KRAFT: {"load": None, "h": 1.2, "n": 2},
        cm.LAUF: {"load": 56, "h": 1.0, "n": 1},
        cm.RAD: {"load": 79 + 3 * 211 + 49, "h": 18.5, "n": 5},
    }
    by_day = cm.wellness_by_day(records)
    week_days = [TODAY + timedelta(days=offset) for offset in range(7)]
    assert week["ctl"] == round(by_day[WEEK_END]["ctl"], 1)
    assert week["ramp"] == round(by_day[WEEK_END]["rampRate"], 1)
    assert week["tsb_min"] == round(min(by_day[day]["ctl"] - by_day[day]["atl"] for day in week_days), 1)
    assert "done_load" not in week  # the week starts in the plan
    assert [(race["date"], race["category"]) for race in plan["races"]] == [
        ("2026-10-04", "RACE_C"), ("2026-10-25", "RACE_B"),
    ]


def test_plan_summary_rest_days_race_days_and_loads():
    events = [
        event(TODAY + timedelta(days=1), "Run", load=0),  # a computed 0 stays 0
        event(TODAY + timedelta(days=3), category="RACE_A", load=None, moving=None),
        event(TODAY + timedelta(days=9), "Ride", load=None),
    ]
    weeks = _plan(events, end=TODAY + timedelta(days=9))["weeks"]
    assert len(weeks) == 2
    first, second = weeks[0], weeks[1]
    assert first["rest_days"] == 5  # neither the run nor the race day is a rest day
    assert (first["load"], first["missing_load"]) == (0, 0)
    assert second == {
        "week": "2026-W41", "days": 3, "load": None, "h": 1.0, "n": 1,
        "by_sport": {cm.RAD: {"load": None, "h": 1.0, "n": 1}},
        "rest_days": 2, "missing_load": 1, "ctl": None, "ramp": None, "tsb_min": None,
    }


def test_plan_races_window_and_other_categories_ignored():
    events = [
        event(END, category="RACE_A", name="before plan start"),
        event(TODAY, None, category="NOTE", load=None),
        event(TODAY + timedelta(days=20), category="RACE_B", name="within look-ahead"),
        event(TODAY + timedelta(days=90), category="RACE_A", name="too far"),
    ]
    plan = _plan(events, race_until=TODAY + timedelta(days=84))
    assert plan["races"] == [{"date": "2026-10-18", "name": "within look-ahead", "category": "RACE_B"}]
    assert {key: plan["weeks"][0][key] for key in ("load", "n", "rest_days")} == {"load": 0, "n": 0, "rest_days": 7}


def test_plan_week_with_completed_days_keeps_done_load_separate():
    acts = [
        activity(TODAY, load=100, moving=3600),
        activity(TODAY + timedelta(days=1), load=50, moving=1800),
        activity(END, load=300),  # previous week
    ]
    plan = _plan([event(TODAY + timedelta(days=2), load=70)], acts=acts, start=TODAY + timedelta(days=2))
    week = plan["weeks"][0]
    assert (week["days"], week["load"]) == (5, 70)
    assert (week["done_load"], week["done_h"]) == (150, 1.5)


def test_plan_week_ramp_falls_back_to_ctl_difference():
    records = [wellness(WEEK_END - timedelta(days=7), ctl=100.0), wellness(WEEK_END, ctl=107.5, atl=120.0, ramp=None)]
    week = _plan([], records)["weeks"][0]
    assert (week["ctl"], week["ramp"], week["tsb_min"]) == (107.5, 7.5, -12.5)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, []),
        ({"ramp": 6.0}, []),
        ({"ramp": 6.1}, [("ramp_planned_high", "warning", 6.1, 6.0)]),
        ({"tsb_min": -20.0}, []),
        ({"tsb_min": -20.1}, [("tsb_planned_low", "warning", -20.1, -20.0)]),
        ({"tsb_min": -30.0}, [("tsb_planned_low", "warning", -30.0, -20.0)]),
        ({"tsb_min": -30.1}, [("tsb_planned_low", "alarm", -30.1, -30.0)]),
        ({"rest_days": 0}, [("planned_rest_days_low", "info", 0, 1)]),
        ({"rest_days": 0, "days": 6}, []),  # week only partly in the plan
        ({"ramp": None, "tsb_min": None}, []),
    ],
)
def test_plan_flags(overrides, expected):
    week = {"week": "2026-W40", "days": 7, "rest_days": 1, "ramp": 3.0, "tsb_min": -10.0, **overrides}
    flags = cm.plan_flags({"weeks": [week]})
    assert [(flag["code"], flag["sev"], flag["val"], flag["thr"]) for flag in flags] == expected
    assert all(flag["basis"] == "projection" and flag["week"] == "2026-W40" for flag in flags)


def _projection_report():
    acts, records, athlete_record, events = projection_scenario()
    report = cm.build_coach_report(acts, records, athlete_record, WEEK_END, 14, load_end=END, today=TODAY, events=events)
    return report, cm.wellness_by_day(records)


def test_projection_report_structure_without_false_alarms():
    report, _ = _projection_report()
    assert list(report) == PROJECTION_KEYS
    assert report["schema_version"] == "1.1"
    period = report["period"]
    assert (period["mode"], period["start"], period["load_end"], period["end"]) == (
        "projection", "2026-09-14", END.isoformat(), WEEK_END.isoformat(),
    )
    codes = {flag["code"] for flag in report["flags"]}
    assert not codes & {"acwr_low", "acwr_high", "monotony_high", "hrv_insufficient", "hrv_below"}
    assert all(flag["basis"] in ("actual", "projection") for flag in report["flags"])
    assert report["load"]["deload"] is False
    assert report["load"]["load_7d"] > 0  # completed week, not the empty future
    assert report["recovery"]["as_of"] == TODAY.isoformat()
    assert report["recovery"]["hrv"]["status"] == "within"
    assert [week["week"] for week in report["volume"]] == ["2026-W38", "2026-W39"]
    assert report["plan"]["from"] == TODAY.isoformat()
    assert {
        "code": "tsb_planned_low", "sev": "warning", "val": report["plan"]["weeks"][0]["tsb_min"],
        "thr": -20.0, "basis": "projection", "week": "2026-W40",
    } in report["flags"]


def test_projection_load_src_matches_values():
    report, by_day = _projection_report()
    load = report["load"]
    assert load["src"] == "api_incl_planned"
    assert load["ctl"] == round(by_day[WEEK_END]["ctl"], 1)
    assert load["ctl"] > load["actual"]["ctl"]  # CTL only rises through planned load
    assert (load["actual"]["date"], load["actual"]["src"]) == (TODAY.isoformat(), "api")
    assert load["actual"]["ctl"] == round(by_day[TODAY]["ctl"], 1)
    expected = {"date": WEEK_END.isoformat(), **{key: load[key] for key in ("ctl", "atl", "tsb", "ramp", "src")}}
    assert load["projected"] == report["plan"]["projection"] == expected


def test_projection_caps_load_end_at_today():
    acts, records, athlete_record, _ = projection_scenario()
    report = cm.build_coach_report(acts, records, athlete_record, WEEK_END, 14, today=TODAY)
    assert report["period"]["load_end"] == TODAY.isoformat()
    assert report["plan"]["from"] == (TODAY + timedelta(days=1)).isoformat()
    assert report["plan"]["weeks"][0]["n"] == 0  # no events passed


def test_actual_report_has_no_projection_keys():
    acts, records, athlete_record = realistic_scenario()
    for today in (None, END, END + timedelta(days=5)):
        report = cm.build_coach_report(acts, records, athlete_record, END, 28, today=today, events=[event(END)])
        assert list(report) == REPORT_KEYS
        assert report["period"]["mode"] == "actual"
        assert "actual" not in report["load"] and "as_of" not in report["recovery"]
        assert all("basis" not in flag for flag in report["flags"])
