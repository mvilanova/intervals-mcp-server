"""
Tests for typed Intervals API response models (models.py).

Covers:
  - IntervalsError: valid, minimal, extra-fields-ignored
  - WellnessEntry: full payload, minimal payload, nulls, unknown custom fields
  - SportInfo: nested parse inside WellnessEntry
  - Event / EventWorkout / EventCalendar: nested parse, full payload
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intervals_mcp_server.models import (
    Event,
    EventCalendar,
    EventWorkout,
    IntervalsError,
    SportInfo,
    WellnessEntry,
)

_RESOURCES = Path(__file__).parent / "ressources"


# ---------------------------------------------------------------------------
# IntervalsError
# ---------------------------------------------------------------------------


class TestIntervalsError:
    def test_full_payload(self):
        data = {"error": True, "status_code": 401, "message": "Unauthorized"}
        err = IntervalsError.from_dict(data)
        assert err.error is True
        assert err.status_code == 401
        assert err.message == "Unauthorized"

    def test_minimal_payload_uses_defaults(self):
        err = IntervalsError.from_dict({"error": True})
        assert err.message == "Unknown error"
        assert err.status_code is None

    def test_extra_keys_are_ignored(self):
        err = IntervalsError.from_dict({"error": True, "message": "oops", "unexpected": "field"})
        assert err.message == "oops"
        assert not hasattr(err, "unexpected")

    def test_to_dict_round_trip(self):
        err = IntervalsError(message="Bad request", status_code=400)
        d = err.to_dict()
        assert d["message"] == "Bad request"
        assert d["status_code"] == 400
        assert d["error"] is True

    def test_to_dict_omits_none(self):
        err = IntervalsError(message="oops")
        d = err.to_dict()
        assert "status_code" not in d


# ---------------------------------------------------------------------------
# SportInfo
# ---------------------------------------------------------------------------


class TestSportInfo:
    def test_valid(self):
        s = SportInfo.from_dict({"type": "Ride", "eftp": 282.86})
        assert s.type == "Ride"
        assert s.eftp == pytest.approx(282.86)

    def test_null_eftp(self):
        s = SportInfo.from_dict({"type": "Run", "eftp": None})
        assert s.eftp is None

    def test_to_dict_omits_none(self):
        s = SportInfo(type="Ride")
        d = s.to_dict()
        assert "eftp" not in d
        assert d["type"] == "Ride"


# ---------------------------------------------------------------------------
# WellnessEntry — full resource fixture
# ---------------------------------------------------------------------------


class TestWellnessEntryFromFixture:
    @pytest.fixture(autouse=True)
    def load_fixture(self):
        with open(_RESOURCES / "wellness_entry.json", encoding="utf-8") as f:
            self.raw = json.load(f)
        self.entry = WellnessEntry.from_dict(self.raw)

    def test_id_is_date_string(self):
        assert self.entry.id == "2025-05-24"

    def test_training_load_fields(self):
        assert self.entry.ctl == pytest.approx(70.87253)
        assert self.entry.atl == pytest.approx(91.97159)
        assert self.entry.rampRate == pytest.approx(6.997368)

    def test_vital_signs(self):
        assert self.entry.weight == 78
        assert self.entry.restingHR == 50

    def test_null_fields_are_none(self):
        assert self.entry.hrv is None
        assert self.entry.sleepSecs is None
        assert self.entry.comments is None

    def test_steps(self):
        assert self.entry.steps == 2303

    def test_nested_sport_info_parsed(self):
        assert self.entry.sportInfo is not None
        assert len(self.entry.sportInfo) == 2
        ride = self.entry.sportInfo[0]
        assert isinstance(ride, SportInfo)
        assert ride.type == "Ride"
        assert ride.eftp == pytest.approx(282.85992)
        run = self.entry.sportInfo[1]
        assert run.type == "Run"
        assert run.eftp is None

    def test_to_dict_round_trip_known_fields(self):
        d = self.entry.to_dict()
        assert d["id"] == "2025-05-24"
        assert d["weight"] == 78
        assert d["steps"] == 2303
        # Null fields should be omitted
        assert "hrv" not in d
        assert "sleepSecs" not in d

    def test_custom_fields_ignored(self):
        raw_with_custom = {**self.raw, "myCustomMetric": 42}
        entry = WellnessEntry.from_dict(raw_with_custom)
        assert not hasattr(entry, "myCustomMetric")
        assert "myCustomMetric" not in entry.to_dict()


# ---------------------------------------------------------------------------
# WellnessEntry — edge cases
# ---------------------------------------------------------------------------


class TestWellnessEntryEdgeCases:
    def test_empty_dict_gives_all_none(self):
        entry = WellnessEntry.from_dict({})
        assert entry.id is None
        assert entry.ctl is None

    def test_minimal_dict(self):
        entry = WellnessEntry.from_dict({"id": "2024-01-01", "ctl": 75})
        assert entry.id == "2024-01-01"
        assert entry.ctl == 75.0

    def test_integer_coerced_to_float_for_ctl(self):
        entry = WellnessEntry.from_dict({"ctl": 80})
        assert isinstance(entry.ctl, float)
        assert entry.ctl == 80.0

    def test_nutrition_macros(self):
        entry = WellnessEntry.from_dict({"carbohydrates": 310, "protein": 145, "fatTotal": 72})
        assert entry.carbohydrates == pytest.approx(310.0)
        assert entry.protein == pytest.approx(145.0)
        assert entry.fatTotal == pytest.approx(72.0)

    def test_sleep_quality_int(self):
        entry = WellnessEntry.from_dict({"sleepQuality": 2})
        assert entry.sleepQuality == 2
        assert isinstance(entry.sleepQuality, int)

    def test_locked_bool(self):
        entry = WellnessEntry.from_dict({"locked": True})
        assert entry.locked is True


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


class TestEventFromFixture:
    @pytest.fixture(autouse=True)
    def load_fixture(self):
        with open(_RESOURCES / "event_details_workout_race.json", encoding="utf-8") as f:
            self.raw = json.load(f)
        self.event = Event.from_dict(self.raw)

    def test_top_level_fields(self):
        assert self.event.id == "e123"
        assert self.event.name == "Stage 1: Pyrenees Climb"
        assert self.event.description == "Cat 1 climb to summit, 18km @ 7.5%"
        assert self.event.race is True
        assert self.event.priority == "A"
        assert self.event.result == "12th"

    def test_nested_workout_parsed(self):
        w = self.event.workout
        assert isinstance(w, EventWorkout)
        assert w.id == "w42"
        assert w.sport == "Ride"
        assert w.duration == 3600
        assert w.tss == pytest.approx(95.0)
        assert isinstance(w.intervals, list)
        assert len(w.intervals) == 5

    def test_nested_calendar_parsed(self):
        cal = self.event.calendar
        assert isinstance(cal, EventCalendar)
        assert cal.name == "TdF Etape Tour 2024"

    def test_to_dict_round_trip(self):
        d = self.event.to_dict()
        assert d["id"] == "e123"
        assert d["race"] is True
        assert d["workout"]["sport"] == "Ride"
        assert d["calendar"]["name"] == "TdF Etape Tour 2024"


class TestEventEdgeCases:
    def test_empty_event(self):
        event = Event.from_dict({})
        assert event.id is None
        assert event.workout is None

    def test_event_no_workout(self):
        event = Event.from_dict({"id": "e1", "name": "Rest Day", "race": False})
        assert event.name == "Rest Day"
        assert event.workout is None
        assert event.race is False

    def test_event_workout_without_intervals(self):
        event = Event.from_dict({"workout": {"id": "w1", "sport": "Run", "duration": 1800}})
        assert event.workout is not None
        assert event.workout.intervals is None

    def test_extra_keys_ignored(self):
        event = Event.from_dict({"id": "e1", "unknownProp": "value"})
        assert event.id == "e1"
        assert not hasattr(event, "unknownProp")
