"""
Type definitions for Intervals.icu MCP Server.

This module contains dataclasses and enums for representing workout data
structures used in the Intervals.icu API, including workout steps, values,
and documentation. Also includes enums for server configuration.

The per-class ``to_dict`` / ``from_dict`` methods are thin wrappers around
the module-level :func:`_to_dict` / :func:`_from_dict` helpers, which iterate
``dataclasses.fields()`` and use :func:`typing.get_type_hints` to coerce
JSON values back into the right enum / dataclass / list types. Adding a new
field to one of the dataclasses below requires no serializer changes.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum, StrEnum
from types import UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints


__all__ = [
    "Step",
    "TransportAliases",
    "Value",
    "ValueUnits",
    "WorkoutDoc",
]


# --- Enums ------------------------------------------------------------------


class WorkoutTarget(Enum):
    """Enumeration of workout target types."""

    AUTO = "AUTO"
    POWER = "POWER"
    HR = "HR"
    PACE = "PACE"


class HrTarget(Enum):
    """Enumeration of heart rate target averaging methods."""

    LAP = "lap"
    INSTANT = "1s"
    THREE_SECOND = "3s"
    TEN_SECOND = "10s"
    THIRTY_SECOND = "30s"


class Intensity(Enum):
    """Enumeration of workout step intensity types."""

    ACTIVE = "active"
    REST = "rest"
    WARMUP = "warmup"
    COOLDOWN = "cooldown"
    RECOVERY = "recovery"
    INTERVAL = "interval"
    OTHER = "other"


class PaceUnits(Enum):
    """Enumeration of pace unit types for swimming and running."""

    SECS_100M = "SECS_100M"
    SECS_100Y = "SECS_100Y"
    MINS_KM = "MINS_KM"
    MINS_MILE = "MINS_MILE"
    SECS_500M = "SECS_500M"


class ValueUnits(Enum):
    """Enumeration of value unit types for workout steps (power, heart rate, pace, cadence)."""

    PERCENT_MMP = "%mmp"
    PERCENT_HR = "%hr"
    PERCENT_LTHR = "%lthr"
    PERCENT_PACE = "%pace"
    POWER_ZONE = "power_zone"
    HR_ZONE = "hr_zone"
    PACE_ZONE = "pace_zone"
    WATTS = "w"
    PERCENT_FTP = "%ftp"
    CADENCE = "cadence"


class TransportAliases(StrEnum):
    """Enumeration of supported MCP transport types."""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    STREAMABLE_HTTP = "streamable-http"


# --- Generic dataclass <-> dict helpers -------------------------------------


def _serialize(val: Any) -> Any:
    """Serialize a single field value into a JSON-compatible form."""
    if isinstance(val, Enum):
        return val.value
    if is_dataclass(val) and not isinstance(val, type):
        return val.to_dict()  # type: ignore[attr-defined]
    if isinstance(val, list):
        return [_serialize(v) for v in val]
    if isinstance(val, dict):
        # Recurse so nested enums / dataclasses inside dict values (e.g.
        # WorkoutDoc.sport_settings) survive json.dumps.
        return {k: _serialize(v) for k, v in val.items()}
    return val


def _to_dict(obj: Any, rename: dict[str, str] | None = None) -> dict[str, Any]:
    """Convert a dataclass instance to a dict, skipping ``None`` fields.

    ``rename`` maps Python field names to JSON keys (e.g. snake → camel case
    for the few fields the Intervals.icu API requires camelCase for).
    """
    rename = rename or {}
    out: dict[str, Any] = {}
    for f in fields(obj):
        val = getattr(obj, f.name)
        if val is None:
            continue
        out[rename.get(f.name, f.name)] = _serialize(val)
    return out


def _coerce(val: Any, hint: Any) -> Any:
    """Coerce a JSON value back into the type indicated by ``hint``."""
    # Null in JSON → None in Python, regardless of declared type. Without this
    # guard, an explicit `null` for a `list[X] | None` field would crash the
    # list comprehension below.
    if val is None:
        return None
    origin = get_origin(hint)
    # Both `typing.Union[X, None]` and PEP 604 `X | None` need to be matched:
    # `get_origin(int | None)` returns `types.UnionType`, not `typing.Union`,
    # so the legacy check alone silently misses every `X | None` field.
    if origin is Union or origin is UnionType:
        non_none = [a for a in get_args(hint) if a is not type(None)]
        # Single non-None arm (Optional[X]) → recurse. Anything broader passes through.
        if len(non_none) == 1:
            return _coerce(val, non_none[0])
        return val
    if origin is list:
        elem_hint = get_args(hint)[0] if get_args(hint) else Any
        return [_coerce(v, elem_hint) for v in val]
    if isinstance(hint, type):
        if issubclass(hint, Enum):
            return hint(val)
        if is_dataclass(hint):
            return hint.from_dict(val)  # type: ignore[attr-defined]
    return val


def _from_dict(
    cls: type, data: dict[str, Any], rename: dict[str, str] | None = None
) -> Any:
    """Build a dataclass instance from a dict using its type hints for coercion."""
    inv_rename = {v: k for k, v in (rename or {}).items()}
    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for json_key, val in data.items():
        py_key = inv_rename.get(json_key, json_key)
        if py_key in hints:
            kwargs[py_key] = _coerce(val, hints[py_key])
    return cls(**kwargs)


def float_to_str(value: float) -> str:
    """Format the value without decimals if it's a whole number."""
    return str(int(value)) if value.is_integer() else str(value)


# --- Domain types -----------------------------------------------------------


_VALUE_FORMATS: dict[ValueUnits, str] = {
    ValueUnits.PERCENT_MMP: "{v}%",
    ValueUnits.PERCENT_HR: "{v}%",
    ValueUnits.PERCENT_LTHR: "{v}%",
    ValueUnits.PERCENT_PACE: "{v}%",
    ValueUnits.PERCENT_FTP: "{v}%",
    ValueUnits.POWER_ZONE: "Z{v}",
    ValueUnits.HR_ZONE: "Z{v}",
    ValueUnits.PACE_ZONE: "Z{v}",
    ValueUnits.WATTS: "{v}W",
    ValueUnits.CADENCE: "{v}rpm",
}

_VALUE_UNIT_LABELS: dict[ValueUnits, str] = {
    ValueUnits.PERCENT_HR: "HR",
    ValueUnits.HR_ZONE: "HR",
    ValueUnits.PERCENT_MMP: "MMP",
    ValueUnits.PERCENT_LTHR: "LTHR",
    ValueUnits.PERCENT_PACE: "Pace",
    ValueUnits.PACE_ZONE: "Pace",
    ValueUnits.PERCENT_FTP: "ftp",
    ValueUnits.POWER_ZONE: "W",
    ValueUnits.CADENCE: "Cadence",
}


@dataclass
class Value:
    """Represents a value with units for workout step intensity.

    Can represent a single value, a range (start-end), or a ramp. Supports
    various unit types including percentages, zones, and absolute values.
    """

    value: float | None = None
    start: float | None = None
    end: float | None = None
    units: ValueUnits | None = None
    target: HrTarget | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Value:
        return _from_dict(cls, data)

    def _format_value(self, value: float) -> str:
        template = _VALUE_FORMATS.get(self.units, "{v}") if self.units else "{v}"
        return template.format(v=float_to_str(value))

    def _format_units(self) -> str:
        if self.units is None:
            return ""
        return _VALUE_UNIT_LABELS.get(self.units, "")

    def __str__(self) -> str:
        parts: list[str] = []
        if self.start is not None and self.end is not None:
            parts.append(f"{self._format_value(self.start)}-{self._format_value(self.end)}")
        if self.value is not None:
            parts.append(self._format_value(self.value))
        if self.units is not None:
            parts.append(self._format_units())
        if self.target is not None:
            parts.append(f"hr={self.target.value}")
        return " ".join(parts)


@dataclass
class Step:
    """Represents a single step in a workout.

    A step can be a warmup, cooldown, interval, or repeat block. It can
    specify duration, distance, intensity targets, and contain nested steps
    for repeats.
    """

    text: str | None = None
    text_locale: dict[str, str] | None = None
    duration: int | None = None
    distance: float | None = None
    until_lap_press: bool | None = None
    reps: int | None = None
    warmup: bool | None = None
    cooldown: bool | None = None
    intensity: Intensity | None = None
    steps: list[Step] | None = None
    ramp: bool | None = None
    freeride: bool | None = None
    maxeffort: bool | None = None
    power: Value | None = None
    hr: Value | None = None
    pace: Value | None = None
    cadence: Value | None = None
    hidepower: bool | None = None
    # Resolved actual watts / bpm etc. when resolve=true is supplied to the endpoint.
    _power: Value | None = None
    _hr: Value | None = None
    _pace: Value | None = None
    _distance: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Step:
        return _from_dict(cls, data)

    def _format_duration(self) -> str:
        if self.duration is None:
            return ""
        remaining = self.duration
        parts: list[str] = []
        if remaining > 3600:
            parts.append(f"{remaining // 3600}h")
            remaining %= 3600
        if remaining > 100 or remaining == 60:
            parts.append(f"{remaining // 60}m")
            remaining %= 60
        if remaining > 0:
            parts.append(f"{remaining}s")
        return "".join(parts)

    def _format_distance(self) -> str:
        if self.distance is None:
            return ""
        if self.distance < 1000:
            return f"{float_to_str(self.distance)}mtr"
        return f"{float_to_str(self.distance / 1000)}km"

    def __str__(self) -> str:
        return self._to_str()

    def _to_str(self, nested: bool = False) -> str:
        val = ""
        if self.reps is not None:
            if nested:
                raise ValueError("Nested steps not supported")
            val += f"\n{self.reps}x "
        else:
            if not nested and self.warmup:
                val += "\nWarmup\n"
            if not nested and self.cooldown:
                val += "\nCooldown\n"

            if self.duration is not None:
                val += f"- {self._format_duration()} "
            elif self.distance is not None:
                val += f"- {self._format_distance()} "

            for flag, label in (
                (self.freeride, "freeride"),
                (self.maxeffort, "maxeffort"),
                (self.ramp, "ramp"),
                (self.hidepower, "hidepower"),
            ):
                if flag:
                    val += f"{label} "
            if self.intensity is not None:
                val += f"intensity={self.intensity.value} "

            for target in (self.power, self.hr, self.pace, self.cadence):
                if target is not None:
                    val += f"{target} "
        if self.text is not None:
            val += f"{self.text} "
        if self.reps is not None and self.steps is not None:
            for step in self.steps:
                # nested=True requires the private helper; __str__ can't take args.
                val += "\n" + step._to_str(nested=True)  # noqa: SLF001
            val += "\n"
        elif not nested and (self.warmup or self.cooldown):
            val += "\n"
        return val


# WorkoutDoc.sport_settings is a free-form dict (the Intervals.icu API
# documents no fixed fields). It used to be a dedicated empty dataclass
# that always serialized to {}; inlining as a dict is observationally
# identical and removes a 25-line placeholder class.


@dataclass
class WorkoutDoc:
    """Represents a complete workout document for the Intervals.icu API.

    Contains workout metadata, step definitions, and sport-specific settings.
    """

    description: str | None = None
    description_locale: dict[str, str] | None = None
    duration: int | None = None
    distance: float | None = None
    ftp: int | None = None
    lthr: int | None = None
    threshold_pace: float | None = None  # meters/sec
    pace_units: PaceUnits | None = None
    sport_settings: dict[str, Any] | None = None
    category: str | None = None
    target: WorkoutTarget | None = None
    steps: list[Step] | None = None
    # `zone_times` is sometimes an array of ints, sometimes of objects.
    zone_times: list[int | dict[str, Any]] | None = None
    options: dict[str, str] | None = None
    locales: list[str] | None = None

    # Snake-case fields that the API spells in camelCase.
    _RENAME = {"sport_settings": "sportSettings", "zone_times": "zoneTimes"}

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self, rename=self._RENAME)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkoutDoc:
        return _from_dict(cls, data, rename=cls._RENAME)

    def __str__(self) -> str:
        parts: list[str] = []
        if self.description is not None:
            parts.append(f"{self.description}\n")
        if self.steps is not None:
            parts.extend(f"{step}\n" for step in self.steps)
        return "".join(parts)
