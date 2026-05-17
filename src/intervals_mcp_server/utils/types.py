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
    """
    Convert a Python value into a JSON-compatible representation.

    Converts Enum members to their `.value`, dataclass instances to their `to_dict()` output, and recursively serializes lists and dicts so nested enums/dataclasses are converted. Values that are already JSON-compatible are returned unchanged.

    Returns:
        Any: A JSON-serializable representation of `val` (primitive, dict, list, or converted enum/dataclass form).
    """
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
    """
    Convert a dataclass instance to a JSON-serializable dict, omitting fields whose value is None.

    Parameters:
        obj (Any): A dataclass instance to serialize.
        rename (dict[str, str] | None): Optional mapping from Python field names to output keys (e.g., snake_case -> camelCase). Keys not present in this mapping are emitted using the original field name.

    Returns:
        dict[str, Any]: A dict mapping output keys to serialized values (enums, nested dataclasses, lists, and dict values are converted via the module's serialization rules).
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
    """
    Coerce a JSON-derived value into the Python type described by `hint`.

    Parameters:
        val (Any): The JSON-derived value to coerce (may be None).
        hint (Any): A type hint or annotation indicating the desired target type
            (may be a concrete type, dataclass, Enum, `list[...]`, `typing.Union`, or
            PEP 604 union).

    Returns:
        Any: The value converted to the hinted type when conversion is applicable:
            - `None` if `val` is `None`.
            - For `Optional[T]`/`T | None` with a single non-None arm, the result of
              coercing to `T`.
            - For `list[T]`, a list with each element coerced to `T`.
            - For `Enum` subclasses, an enum instance constructed from `val`.
            - For dataclass types, an instance built via `from_dict`.
            - Numeric inputs coerced to `float` or `int` when the hint is `float` or
              `int`, respectively.
            If no applicable conversion is available, returns `val` unchanged.
    """
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
        # `Value.value` / `Step.distance` are annotated `float`, but the API
        # sends bare integers for round numbers. Without this cast, callers see
        # an `int` where a `float` is declared — sloppy enough on py312 (where
        # `int.is_integer()` happens to exist) and a real AttributeError on
        # older runtimes if this code is ever back-ported. Branch explicitly
        # so mypy can narrow the constructor call.
        if isinstance(val, (int, float)):
            if hint is float:
                return float(val)
            if hint is int:
                return int(val)
    return val


def _from_dict(cls: type, data: dict[str, Any], rename: dict[str, str] | None = None) -> Any:
    """
    Create an instance of the given dataclass-like type from a JSON-compatible dictionary by coercing values to the annotated field types.

    Parameters:
        cls (type): The target dataclass/type to instantiate.
        data (dict[str, Any]): Mapping of JSON keys to values to populate the instance.
        rename (dict[str, str] | None): Optional mapping from Python field names to JSON keys; when provided, JSON keys will be mapped back to Python field names before coercion.

    Returns:
        An instance of `cls` constructed with values from `data` coerced to the corresponding type hints. Keys in `data` that do not correspond to `cls` type hints are ignored.
    """
    inv_rename = {v: k for k, v in (rename or {}).items()}
    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for json_key, val in data.items():
        py_key = inv_rename.get(json_key, json_key)
        if py_key in hints:
            kwargs[py_key] = _coerce(val, hints[py_key])
    return cls(**kwargs)


def float_to_str(value: float) -> str:
    """
    Format a float as a string, omitting the decimal point when the value is a whole number.

    Returns:
        The string representation of the value; if the float is a whole number the decimal part is removed (e.g. 2.0 -> "2"), otherwise the standard float string is returned.
    """
    value = float(value)
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
        """
        Convert the dataclass instance to a JSON-compatible dictionary for API serialization.

        Returns:
            dict[str, Any]: A dictionary containing all fields that are not `None`. Enum values are converted to their raw values, dataclass fields are converted to dictionaries, and lists/dicts are recursively serialized to JSON-compatible types.
        """
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Value:
        """
        Create a Value instance from a JSON-compatible dictionary.

        Parameters:
            data (dict[str, Any]): Dictionary containing keys that match Value's fields; values will be coerced to the annotated types.

        Returns:
            Value: A new Value instance populated from `data`.
        """
        return _from_dict(cls, data)

    def _format_value(self, value: float) -> str:
        """
        Format a numeric value according to this Value's units for display.

        Parameters:
                value (float): The numeric value to format.

        Returns:
                formatted (str): The value formatted as a string using the unit-specific template (or plain numeric string if units are not set).
        """
        template = _VALUE_FORMATS.get(self.units, "{v}") if self.units else "{v}"
        return template.format(v=float_to_str(value))

    def _format_units(self) -> str:
        """
        Get the short label for this Value's units.

        Returns:
            The unit label string, or an empty string if `units` is `None` or no label is available.
        """
        if self.units is None:
            return ""
        return _VALUE_UNIT_LABELS.get(self.units, "")

    def __str__(self) -> str:
        """
        Produce a compact human-readable representation of the Value.

        The string includes, in order:
        - a range formatted as `start-end` if both `start` and `end` are present,
        - the primary value if present,
        - the unit label if present,
        - the heart-rate target as `hr=<target>` if present.
        All present components are joined with single spaces.

        Returns:
            A formatted string describing the value and any available range, units, and HR target.
        """
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
        """
        Convert the dataclass instance to a JSON-compatible dictionary for API serialization.

        Underscore-prefixed fields (``_power``, ``_hr``, ``_pace``, ``_distance``)
        are *response-only*: the Intervals.icu API populates them on
        ``resolve=true`` GETs but rejects them on writes. They must be stripped
        from any payload that round-trips a resolved step back to the API.

        Returns:
            dict[str, Any]: A dictionary containing all non-`None`,
            non-underscore-prefixed fields. Enum values are converted to their
            raw values, dataclass fields are converted to dictionaries, and
            lists/dicts are recursively serialized to JSON-compatible types.
        """
        return {k: v for k, v in _to_dict(self).items() if not k.startswith("_")}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Step:
        """
        Create a Step instance from a dictionary containing serialized Step fields.

        Parameters:
            data (dict[str, Any]): Mapping of field names to values representing a Step.

        Returns:
            Step: The deserialized Step instance.
        """
        return _from_dict(cls, data)

    def _format_duration(self) -> str:
        """
        Format self.duration (seconds) into a compact human-readable string.

        If `self.duration` is None an empty string is returned. Hours are emitted as
        "{h}h" when duration >= 3600, minutes as "{m}m" when the remaining seconds
        are greater than 100 or exactly 60, and seconds as "{s}s" for any remaining
        seconds > 0. Components are concatenated without separators.

        Returns:
            str: The formatted duration string, or an empty string if `duration` is None.
        """
        if self.duration is None:
            return ""
        remaining = self.duration
        parts: list[str] = []
        # `>=` rather than `>` so exact-hour and exact-minute boundaries
        # render with their natural unit (3600s → "1h", not "60m"; 90s →
        # "1m30s", not "90s").
        if remaining >= 3600:
            parts.append(f"{remaining // 3600}h")
            remaining %= 3600
        if remaining >= 60:
            parts.append(f"{remaining // 60}m")
            remaining %= 60
        if remaining > 0:
            parts.append(f"{remaining}s")
        return "".join(parts)

    def _format_distance(self) -> str:
        """
        Format the instance's distance into a compact human-readable string.

        Returns:
            A short string representing `distance`: `''` if `distance` is None; otherwise
            `'<n>mtr'` when `distance` is less than 1000 (meters) or `'<n>km'` for
            kilometer values. The numeric portion omits a decimal point for whole numbers.
        """
        if self.distance is None:
            return ""
        if self.distance < 1000:
            return f"{float_to_str(self.distance)}mtr"
        return f"{float_to_str(self.distance / 1000)}km"

    def __str__(self) -> str:
        """
        Provide a human-readable, formatted string representation of the Step.

        Returns:
            A formatted, human-readable string describing the step (may include multiple lines and nested step text).
        """
        return self._to_str()

    def _to_str(self, nested: bool = False) -> str:
        """
        Render this Step as a formatted multi-line string describing its duration/distance, flags, intensity, targets, text, and any nested steps.

        If `reps` is set the string is prefixed with "{reps}x " and, when `steps` are present, each nested step is appended on its own line. When not repeated, warmup/cooldown headers are included (unless `nested` is True), and duration or distance is shown with any enabled flags (`freeride`, `maxeffort`, `ramp`, `hidepower`), intensity, and target values appended. Trailing newlines are added for repeated groups and for top-level warmup/cooldown sections.

        Parameters:
                nested (bool): If True, render this step in a nested context (suppresses warmup/cooldown headers and disallows top-level repeats).

        Returns:
                str: The composed, human-readable representation of the step.

        Raises:
                ValueError: If `nested` is True while `reps` is set (nested repeated groups are not supported).
        """
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
        """
        Serialize the workout document into a JSON-compatible dictionary suitable for the API.

        Returns:
            dict[str, Any]: A dictionary using the API's field names (camelCase where applicable); any fields with value `None` are omitted.
        """
        return _to_dict(self, rename=self._RENAME)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkoutDoc:
        """
        Create a WorkoutDoc from a JSON-style dictionary.

        Parameters:
            data (dict[str, Any]): Dictionary of workout fields (typically API/camelCase keys) to be coerced into the typed WorkoutDoc structure, including nested steps and enum values.

        Returns:
            WorkoutDoc: An instance populated from the provided dictionary.
        """
        return _from_dict(cls, data, rename=cls._RENAME)

    def __str__(self) -> str:
        """
        Return a human-readable workout document consisting of the optional description followed by each step on its own line.

        If `description` is present it appears first followed by a newline. Each step in `steps`, if present, is rendered using the step's string representation with a trailing newline. Returns an empty string when neither `description` nor `steps` are set.

        Returns:
            str: The concatenated description and step lines.
        """
        parts: list[str] = []
        if self.description is not None:
            parts.append(f"{self.description}\n")
        if self.steps is not None:
            parts.extend(f"{step}\n" for step in self.steps)
        return "".join(parts)
