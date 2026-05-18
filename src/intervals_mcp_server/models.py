"""
Typed response models for Intervals.icu API responses.

Design note — dataclasses vs Pydantic v2:
  Pydantic v2 is not in the existing dependency set. The project already ships a
  set of generic dataclass helpers (_from_dict, _to_dict, _coerce) in utils/types.py
  that handle all the coercion required here: optional fields, numeric widening,
  nested dataclass deserialization, and enum parsing. Adding Pydantic purely for
  model validation would add a heavyweight dependency with no incremental benefit.
  stdlib dataclasses + the existing helpers are the right choice.

Public surface:
  - IntervalsError  — typed representation of API error dicts
  - SportInfo       — single sport entry inside a WellnessEntry
  - WellnessEntry   — typed /wellness response item
  - EventWorkout    — workout sub-document inside an Event
  - EventCalendar   — calendar sub-document inside an Event
  - Event           — typed /events response item
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from intervals_mcp_server.utils.types import _from_dict, _to_dict  # noqa: PLC2701


__all__ = [
    "Event",
    "EventCalendar",
    "EventWorkout",
    "IntervalsError",
    "SportInfo",
    "WellnessEntry",
]


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


@dataclass
class IntervalsError:
    """Typed representation of an error dict returned by make_intervals_request.

    All error paths in the API client produce dicts with at least ``error``
    and ``message`` keys; ``status_code`` is present only for HTTP-level errors.
    """

    message: str = "Unknown error"
    error: bool = True
    status_code: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntervalsError:
        return _from_dict(cls, data)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


# ---------------------------------------------------------------------------
# Wellness models
# ---------------------------------------------------------------------------


@dataclass
class SportInfo:
    """A single sport entry inside a WellnessEntry.sportInfo list."""

    type: str | None = None
    eftp: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SportInfo:
        return _from_dict(cls, data)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class WellnessEntry:
    """Typed representation of one item from the /athlete/{id}/wellness endpoint.

    Field names match the Intervals.icu API's camelCase JSON keys so that
    _from_dict / _to_dict work without a rename table. All fields are optional
    (None default) because the API emits explicit null for unset measurements.

    Unknown keys (e.g. custom user fields) are silently ignored by _from_dict.
    If you need custom fields to survive a round-trip through to_dict(), pass
    the raw dict directly to format_wellness_entry instead.
    """

    # Identifier / metadata
    id: str | None = None
    date: str | None = None
    updated: str | None = None

    # Training load
    ctl: float | None = None
    atl: float | None = None
    rampRate: float | None = None
    ctlLoad: float | None = None
    atlLoad: float | None = None

    # Sport-specific
    sportInfo: list[SportInfo] | None = None

    # Vital signs
    weight: float | None = None
    tempWeight: float | None = None
    restingHR: float | None = None
    tempRestingHR: float | None = None
    hrv: float | None = None
    hrvSDNN: float | None = None
    avgSleepingHR: float | None = None
    spO2: float | None = None
    systolic: float | None = None
    diastolic: float | None = None
    respiration: float | None = None
    bloodGlucose: float | None = None
    lactate: float | None = None
    vo2max: float | None = None
    bodyFat: float | None = None
    abdomen: float | None = None
    baevskySI: float | None = None

    # Sleep & recovery
    sleepSecs: float | None = None
    sleepHours: float | None = None
    sleepQuality: int | None = None
    sleepScore: float | None = None
    readiness: float | None = None

    # Menstrual tracking
    menstrualPhase: str | None = None
    menstrualPhasePredicted: str | None = None

    # Subjective feelings (1–10 scale)
    soreness: int | None = None
    fatigue: int | None = None
    stress: int | None = None
    mood: int | None = None
    motivation: int | None = None
    injury: int | None = None

    # Nutrition & hydration
    kcalConsumed: float | None = None
    carbohydrates: float | None = None
    protein: float | None = None
    fatTotal: float | None = None
    hydrationVolume: float | None = None
    hydration: float | None = None

    # Activity
    steps: int | None = None

    # Misc
    comments: str | None = None
    locked: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WellnessEntry:
        return _from_dict(cls, data)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


# ---------------------------------------------------------------------------
# Event models
# ---------------------------------------------------------------------------


@dataclass
class EventWorkout:
    """Workout sub-document embedded inside an Event."""

    id: str | None = None
    sport: str | None = None
    duration: int | None = None
    tss: float | None = None
    intervals: list[Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventWorkout:
        return _from_dict(cls, data)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class EventCalendar:
    """Calendar reference embedded inside an Event."""

    name: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EventCalendar:
        return _from_dict(cls, data)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)


@dataclass
class Event:
    """Typed representation of one item from the /events endpoint.

    Field names use the snake_case the Events API actually returns
    (e.g. ``start_date_local``). The nested ``workout`` and ``calendar``
    sub-documents are deserialized into their own typed classes via
    _coerce so you get full type-safe access to their fields.
    """

    id: str | None = None
    date: str | None = None
    start_date_local: str | None = None
    name: str | None = None
    description: str | None = None
    category: str | None = None
    workout: EventWorkout | None = None
    race: bool | None = None
    priority: str | None = None
    result: str | None = None
    calendar: EventCalendar | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        return _from_dict(cls, data)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)
