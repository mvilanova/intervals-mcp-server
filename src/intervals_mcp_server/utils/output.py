"""
Structured (JSON) output helpers for list tools.

JSON records use stable snake_case keys and unconverted numeric values
(seconds, meters, m/s, watts, ...). Keys whose value is missing are omitted.
"""

import json
import re
from typing import Any, Literal

OutputFormat = Literal["text", "json"]
VALID_FORMATS = ("text", "json")

_ACTIVITY_KEYS: dict[str, tuple[str, ...]] = {
    "id": ("id",),
    "name": ("name",),
    "type": ("type",),
    "date": ("startTime", "start_date_local", "start_date"),
    "description": ("description",),
    "distance_m": ("distance",),
    "duration_s": ("duration", "elapsed_time"),
    "moving_time_s": ("moving_time",),
    "elevation_gain_m": ("elevationGain", "total_elevation_gain"),
    "elevation_loss_m": ("total_elevation_loss",),
    "average_power_w": ("avgPower", "icu_average_watts", "average_watts"),
    "weighted_avg_power_w": ("icu_weighted_avg_watts",),
    "training_load": ("trainingLoad", "icu_training_load"),
    "ftp_w": ("icu_ftp",),
    "intensity": ("icu_intensity",),
    "average_hr_bpm": ("avgHr", "average_heartrate"),
    "max_hr_bpm": ("max_heartrate",),
    "average_cadence_rpm": ("average_cadence",),
    "calories_kcal": ("calories",),
    "average_speed_mps": ("average_speed",),
    "max_speed_mps": ("max_speed",),
    "rpe": ("perceived_exertion", "icu_rpe"),
    "feel": ("feel",),
    "ctl": ("icu_ctl",),
    "atl": ("icu_atl",),
    "trainer": ("trainer",),
    "device_name": ("device_name",),
}

_EVENT_KEYS: dict[str, tuple[str, ...]] = {
    "id": ("id",),
    "date": ("start_date_local", "date"),
    "name": ("name",),
    "description": ("description",),
    "category": ("category",),
    "type": ("type",),
}

_WELLNESS_KEYS = (
    "id ctl atl rampRate ctlLoad atlLoad weight restingHR hrv hrvSDNN avgSleepingHR spO2 "
    "systolic diastolic respiration bloodGlucose lactate vo2max bodyFat abdomen baevskySI "
    "sleepSecs sleepQuality sleepScore readiness menstrualPhase menstrualPhasePredicted "
    "soreness fatigue stress mood motivation injury kcalConsumed carbohydrates protein "
    "fatTotal hydrationVolume hydration steps comments locked"
).split()
# Metadata keys never reported under "other_fields".
_WELLNESS_INTERNAL = {"date", "updated", "tempWeight", "tempRestingHR"}


def _snake(name: str) -> str:
    """Convert camelCase to snake_case (e.g. restingHR -> resting_hr)."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()


def validate_format(output_format: str) -> str | None:
    """Return an error message if output_format is not supported, else None."""
    if output_format not in VALID_FORMATS:
        return (
            f"Error: invalid format '{output_format}'. "
            f"Supported values: {', '.join(VALID_FORMATS)}."
        )
    return None


def _first(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-None value among keys, else None."""
    for key in keys:
        if record.get(key) is not None:
            return record[key]
    return None


def _project(record: dict[str, Any], mapping: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    """Project a raw record onto the curated keys, dropping missing values."""
    out = {name: _first(record, keys) for name, keys in mapping.items()}
    return {k: v for k, v in out.items() if v is not None}


def activity_to_dict(activity: dict[str, Any]) -> dict[str, Any]:
    """Curated JSON record for an activity (same fields as the text summary)."""
    out = _project(activity, _ACTIVITY_KEYS)
    gear_raw = activity.get("gear")
    gear_name = activity.get("_resolved_gear_name") or activity.get("gear_name")
    gear_id = activity.get("gear_id")
    if isinstance(gear_raw, dict):
        gear_name = gear_name or gear_raw.get("name") or gear_raw.get("display_name")
        gear_id = gear_raw.get("id", gear_id)
    gear = {k: v for k, v in (("id", gear_id), ("name", gear_name)) if v is not None}
    if gear:
        out["gear"] = gear
    return out


def event_to_dict(event: dict[str, Any]) -> dict[str, Any]:
    """Curated JSON record for a calendar event."""
    out = _project(event, _EVENT_KEYS)
    category = str(event.get("category") or "")
    if category == "WORKOUT":
        out["kind"] = "workout"
    elif category.startswith("RACE_"):
        out["kind"] = "race"
    elif category == "NOTE":
        out["kind"] = "note"
    else:
        out["kind"] = "other"
    return out


def wellness_to_dict(entry: dict[str, Any], include_all_fields: bool = False) -> dict[str, Any]:
    """Curated JSON record for a wellness entry (keys converted to snake_case)."""
    out = {_snake(k): entry[k] for k in _WELLNESS_KEYS if entry.get(k) is not None}
    if "id" in out:
        out = {"date": out.pop("id"), **out}
    if include_all_fields:
        known = set(_WELLNESS_KEYS) | _WELLNESS_INTERNAL
        other = {k: v for k, v in entry.items() if k not in known and v is not None}
        if other:
            out["other_fields"] = other
    return out


def to_json(records: list[dict[str, Any]]) -> str:
    """Serialize records as indented JSON (UTF-8 preserved)."""
    return json.dumps(records, indent=2, ensure_ascii=False, default=str)
