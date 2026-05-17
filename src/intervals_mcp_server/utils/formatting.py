"""
Formatting utilities for Intervals.icu MCP Server

This module contains formatting functions for handling data from the Intervals.icu API.
"""

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any


def _format_iso_datetime(value: Any) -> Any:
    """Reformat an ISO-8601 datetime string as 'YYYY-MM-DD HH:MM:SS'.

    Passes the value through unchanged when it isn't a parseable ISO datetime
    longer than 10 characters (10-char date-only strings are left as-is).
    """
    if isinstance(value, str) and len(value) > 10:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            return value
    return value


def _first_present(d: dict[str, Any], *keys: str, default: Any = "N/A") -> Any:
    """Return the value of the first key present in ``d``, else ``default``.

    Mirrors `d.get(k1, d.get(k2, ...))` chained calls exactly: a key whose
    value is explicitly ``None`` still counts as present and stops the chain.
    For None-aware fallbacks (e.g. RPE) the caller handles them inline.
    """
    for k in keys:
        if k in d:
            return d[k]
    return default


def format_activity_summary(activity: dict[str, Any]) -> str:
    """Format an activity into a readable string."""
    start_time = _format_iso_datetime(
        _first_present(activity, "startTime", "start_date", default="Unknown")
    )

    rpe = activity.get("perceived_exertion", None)
    if rpe is None:
        rpe = activity.get("icu_rpe", "N/A")
    if isinstance(rpe, (int, float)):
        rpe = f"{rpe}/10"

    feel = activity.get("feel", "N/A")
    if isinstance(feel, int):
        feel = f"{feel}/5"

    return f"""
Activity: {activity.get("name", "Unnamed")}
ID: {activity.get("id", "N/A")}
Type: {activity.get("type", "Unknown")}
Date: {start_time}
Description: {activity.get("description", "N/A")}
Distance: {activity.get("distance", 0)} meters
Duration: {_first_present(activity, "duration", "elapsed_time", default=0)} seconds
Moving Time: {activity.get("moving_time", "N/A")} seconds
Elevation Gain: {_first_present(activity, "elevationGain", "total_elevation_gain", default=0)} meters
Elevation Loss: {activity.get("total_elevation_loss", "N/A")} meters

Power Data:
Average Power: {_first_present(activity, "avgPower", "icu_average_watts", "average_watts")} watts
Weighted Avg Power: {activity.get("icu_weighted_avg_watts", "N/A")} watts
Training Load: {_first_present(activity, "trainingLoad", "icu_training_load")}
FTP: {activity.get("icu_ftp", "N/A")} watts
Kilojoules: {activity.get("icu_joules", "N/A")}
Intensity: {activity.get("icu_intensity", "N/A")}
Power:HR Ratio: {activity.get("icu_power_hr", "N/A")}
Variability Index: {activity.get("icu_variability_index", "N/A")}

Heart Rate Data:
Average Heart Rate: {_first_present(activity, "avgHr", "average_heartrate")} bpm
Max Heart Rate: {activity.get("max_heartrate", "N/A")} bpm
LTHR: {activity.get("lthr", "N/A")} bpm
Resting HR: {activity.get("icu_resting_hr", "N/A")} bpm
Decoupling: {activity.get("decoupling", "N/A")}

Other Metrics:
Cadence: {activity.get("average_cadence", "N/A")} rpm
Calories burned: {activity.get("calories", "N/A")} kcal
Average Speed: {activity.get("average_speed", "N/A")} m/s
Max Speed: {activity.get("max_speed", "N/A")} m/s
Average Stride: {activity.get("average_stride", "N/A")}
L/R Balance: {activity.get("avg_lr_balance", "N/A")}
Weight: {activity.get("icu_weight", "N/A")} kg
RPE: {rpe}
Session RPE: {activity.get("session_rpe", "N/A")}
Feel: {feel}

Environment:
Trainer: {activity.get("trainer", "N/A")}
Average Temp: {activity.get("average_temp", "N/A")}°C
Min Temp: {activity.get("min_temp", "N/A")}°C
Max Temp: {activity.get("max_temp", "N/A")}°C
Avg Wind Speed: {activity.get("average_wind_speed", "N/A")} km/h
Headwind %: {activity.get("headwind_percent", "N/A")}%
Tailwind %: {activity.get("tailwind_percent", "N/A")}%

Training Metrics:
Fitness (CTL): {activity.get("icu_ctl", "N/A")}
Fatigue (ATL): {activity.get("icu_atl", "N/A")}
TRIMP: {activity.get("trimp", "N/A")}
Polarization Index: {activity.get("polarization_index", "N/A")}
Power Load: {activity.get("power_load", "N/A")}
HR Load: {activity.get("hr_load", "N/A")}
Pace Load: {activity.get("pace_load", "N/A")}
Efficiency Factor: {activity.get("icu_efficiency_factor", "N/A")}

Device Info:
Device: {activity.get("device_name", "N/A")}
Power Meter: {activity.get("power_meter", "N/A")}
File Type: {activity.get("file_type", "N/A")}
"""


def format_workout(workout: dict[str, Any]) -> str:
    """Format a workout into a readable string."""
    return f"""
Workout: {workout.get("name", "Unnamed")}
Description: {workout.get("description", "No description")}
Sport: {workout.get("sport", "Unknown")}
Duration: {workout.get("duration", 0)} seconds
TSS: {workout.get("tss", "N/A")}
Intervals: {len(workout.get("intervals", []))}
"""


# Field tables for the wellness formatters. Each tuple is (key, label[, unit]).
# These tables are the single source of truth for both the rendered output and
# the `_KNOWN_WELLNESS_KEYS` set below — adding a field updates both at once.

_TRAINING_METRICS_FIELDS: list[tuple[str, str]] = [
    ("ctl", "Fitness (CTL)"),
    ("atl", "Fatigue (ATL)"),
    ("rampRate", "Ramp Rate"),
    ("ctlLoad", "CTL Load"),
    ("atlLoad", "ATL Load"),
]

_VITAL_SIGNS_FIELDS: list[tuple[str, str, str]] = [
    ("weight", "Weight", "kg"),
    ("restingHR", "Resting HR", "bpm"),
    ("hrv", "HRV", ""),
    ("hrvSDNN", "HRV SDNN", ""),
    ("avgSleepingHR", "Average Sleeping HR", "bpm"),
    ("spO2", "SpO2", "%"),
    ("systolic", "Systolic BP", ""),
    ("diastolic", "Diastolic BP", ""),
    ("respiration", "Respiration", "breaths/min"),
    ("bloodGlucose", "Blood Glucose", "mmol/L"),
    ("lactate", "Lactate", "mmol/L"),
    ("vo2max", "VO2 Max", "ml/kg/min"),
    ("bodyFat", "Body Fat", "%"),
    ("abdomen", "Abdomen", "cm"),
    ("baevskySI", "Baevsky Stress Index", ""),
]

_SUBJECTIVE_FEELINGS_FIELDS: list[tuple[str, str]] = [
    ("soreness", "Soreness"),
    ("fatigue", "Fatigue"),
    ("stress", "Stress"),
    ("mood", "Mood"),
    ("motivation", "Motivation"),
    ("injury", "Injury Level"),
]

_NUTRITION_FIELDS: list[tuple[str, str, str]] = [
    ("kcalConsumed", "Calories Consumed", ""),
    ("carbohydrates", "Carbohydrates", "g"),
    ("protein", "Protein", "g"),
    ("fatTotal", "Fat", "g"),
    ("hydrationVolume", "Hydration Volume", ""),
]

_SLEEP_QUALITY_LABELS: dict[int, str] = {1: "Great", 2: "Good", 3: "Average", 4: "Poor"}


def _format_training_metrics(entries: dict[str, Any]) -> list[str]:
    return [
        f"- {label}: {entries[k]}"
        for k, label in _TRAINING_METRICS_FIELDS
        if entries.get(k) is not None
    ]


def _format_sport_info(entries: dict[str, Any]) -> list[str]:
    return [
        f"- {sport.get('type')}: eFTP = {sport['eftp']}"
        for sport in entries.get("sportInfo") or []
        if isinstance(sport, dict) and sport.get("eftp") is not None
    ]


def _format_vital_signs(entries: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for k, label, unit in _VITAL_SIGNS_FIELDS:
        val = entries.get(k)
        if val is None:
            continue
        if k == "systolic":
            dia = entries.get("diastolic")
            if dia is not None:
                lines.append(f"- Blood Pressure: {val}/{dia} mmHg")
            else:
                # Partial reading: render systolic on its own rather than dropping it.
                suffix = f" {unit}" if unit else ""
                lines.append(f"- {label}: {val}{suffix}")
        elif k == "diastolic":
            # When both are present the combined "Blood Pressure" line was already
            # emitted at systolic above. Only render solo if systolic is absent.
            if entries.get("systolic") is None:
                suffix = f" {unit}" if unit else ""
                lines.append(f"- {label}: {val}{suffix}")
        else:
            suffix = f" {unit}" if unit else ""
            lines.append(f"- {label}: {val}{suffix}")
    return lines


def _format_sleep_recovery(entries: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if entries.get("sleepSecs") is not None:
        lines.append(f"  Sleep: {entries['sleepSecs'] / 3600:.2f} hours")
    elif entries.get("sleepHours") is not None:
        lines.append(f"  Sleep: {entries['sleepHours']} hours")

    quality = entries.get("sleepQuality")
    if quality is not None:
        quality_text = _SLEEP_QUALITY_LABELS.get(quality, str(quality))
        lines.append(f"  Sleep Quality: {quality} ({quality_text})")

    if entries.get("sleepScore") is not None:
        lines.append(f"  Device Sleep Score: {entries['sleepScore']}/100")
    if entries.get("readiness") is not None:
        lines.append(f"  Readiness: {entries['readiness']}/10")
    return lines


def _format_menstrual_tracking(entries: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for k, label in (
        ("menstrualPhase", "Menstrual Phase"),
        ("menstrualPhasePredicted", "Predicted Phase"),
    ):
        if entries.get(k) is not None:
            lines.append(f"  {label}: {str(entries[k]).capitalize()}")
    return lines


def _format_subjective_feelings(entries: dict[str, Any]) -> list[str]:
    return [
        f"  {label}: {entries[k]}/10"
        for k, label in _SUBJECTIVE_FEELINGS_FIELDS
        if entries.get(k) is not None
    ]


def _format_nutrition_hydration(entries: dict[str, Any]) -> list[str]:
    """Render nutrition / hydration lines, skipping any null/missing field."""
    lines: list[str] = []
    for k, label, unit in _NUTRITION_FIELDS:
        if entries.get(k) is not None:
            suffix = f" {unit}" if unit else ""
            lines.append(f"- {label}: {entries[k]}{suffix}")
    if entries.get("hydration") is not None:
        lines.append(f"  Hydration Score: {entries['hydration']}/10")
    return lines


def _format_other_fields(entries: dict[str, Any], known_keys: frozenset[str]) -> list[str]:
    """Render every entry not already handled by the standard sections."""
    other_lines: list[str] = []
    for key, value in entries.items():
        if key in known_keys or value is None:
            continue
        rendered = json.dumps(value) if isinstance(value, (dict, list)) else value
        other_lines.append(f"- {key}: {rendered}")
    return other_lines


_WELLNESS_SECTIONS: list[tuple[str, Callable[[dict[str, Any]], list[str]]]] = [
    ("Training Metrics:", _format_training_metrics),
    ("Sport-Specific Info:", _format_sport_info),
    ("Vital Signs:", _format_vital_signs),
    ("Sleep & Recovery:", _format_sleep_recovery),
    ("Menstrual Tracking:", _format_menstrual_tracking),
    ("Subjective Feelings:", _format_subjective_feelings),
    ("Nutrition & Hydration:", _format_nutrition_hydration),
]


# Every wellness key the standard formatters look at. Anything outside this set
# falls through to "Other Fields" when ``include_all_fields=True``. Keep in
# sync with the section helpers: missing a key here would double-render it as
# both a section line and an "Other Fields" line.
_KNOWN_WELLNESS_KEYS: frozenset[str] = frozenset(
    {k for k, _ in _TRAINING_METRICS_FIELDS}
    | {k for k, _, _ in _VITAL_SIGNS_FIELDS}
    | {k for k, _ in _SUBJECTIVE_FEELINGS_FIELDS}
    | {k for k, _, _ in _NUTRITION_FIELDS}
    | {
        "sportInfo",
        "sleepSecs",
        "sleepHours",
        "sleepQuality",
        "sleepScore",
        "readiness",
        "menstrualPhase",
        "menstrualPhasePredicted",
        "hydration",
        # Top-level fields rendered inline by format_wellness_entry.
        "id",
        "steps",
        "comments",
        "locked",
        # Metadata fields that should never surface under "Other Fields".
        "date",
        "updated",
        "tempWeight",
        "tempRestingHR",
    }
)


def format_wellness_entry(entries: dict[str, Any], include_all_fields: bool = False) -> str:
    """Format wellness entry data into a readable string.

    See :data:`_KNOWN_WELLNESS_KEYS` for the set of fields handled by the
    standard sections; everything else is appended under "Other Fields" when
    ``include_all_fields=True``.
    """
    lines: list[str] = ["Wellness Data:", f"Date: {entries.get('id', 'N/A')}", ""]

    for header, formatter in _WELLNESS_SECTIONS:
        section_lines = formatter(entries)
        if section_lines:
            lines.append(header)
            lines.extend(section_lines)
            lines.append("")

    if entries.get("steps") is not None:
        lines.extend(["Activity:", f"- Steps: {entries['steps']}", ""])

    if entries.get("comments"):
        lines.append(f"Comments: {entries['comments']}")
    if "locked" in entries:
        lines.append(f"Status: {'Locked' if entries.get('locked') else 'Unlocked'}")

    if include_all_fields:
        other_lines = _format_other_fields(entries, _KNOWN_WELLNESS_KEYS)
        if other_lines:
            lines.extend(["", "Other Fields:", *other_lines])

    return "\n".join(lines)


def format_event_summary(event: dict[str, Any]) -> str:
    """Format a basic event summary into a readable string."""

    # Update to check for "date" if "start_date_local" is not provided
    event_date = event.get("start_date_local", event.get("date", "Unknown"))
    if event.get("workout"):
        event_type = "Workout"
    elif event.get("race"):
        event_type = "Race"
    else:
        event_type = "Other"
    event_name = event.get("name", "Unnamed")
    event_id = event.get("id", "N/A")
    event_desc = event.get("description", "No description")

    return f"""Date: {event_date}
ID: {event_id}
Type: {event_type}
Name: {event_name}
Description: {event_desc}"""


def format_event_details(event: dict[str, Any]) -> str:
    """Format detailed event information into a readable string."""
    parts: list[str] = [
        f"""Event Details:

ID: {event.get("id", "N/A")}
Date: {event.get("date", "Unknown")}
Name: {event.get("name", "Unnamed")}
Description: {event.get("description", "No description")}"""
    ]

    workout = event.get("workout")
    if workout:
        workout_lines = [
            "Workout Information:",
            f"Workout ID: {workout.get('id', 'N/A')}",
            f"Sport: {workout.get('sport', 'Unknown')}",
            f"Duration: {workout.get('duration', 0)} seconds",
            f"TSS: {workout.get('tss', 'N/A')}",
        ]
        if isinstance(workout.get("intervals"), list):
            workout_lines.append(f"Intervals: {len(workout['intervals'])}")
        parts.append("\n".join(workout_lines))

    if event.get("race"):
        parts.append(
            "Race Information:\n"
            f"Priority: {event.get('priority', 'N/A')}\n"
            f"Result: {event.get('result', 'N/A')}"
        )

    if "calendar" in event:
        parts.append(f"Calendar: {event['calendar'].get('name', 'N/A')}")

    return "\n\n".join(parts)


def format_activity_message(message: dict[str, Any]) -> str:
    """Format an activity message/note into a readable string."""
    created = _format_iso_datetime(message.get("created", "Unknown"))

    return f"""Author: {message.get("name", "Unknown")}
Date: {created}
Type: {message.get("type", "TEXT")}
Content: {message.get("content", "")}"""


def format_custom_item_details(item: dict[str, Any]) -> str:
    """Format detailed custom item information into a readable string."""
    lines = ["Custom Item Details:", ""]
    lines.append(f"ID: {item.get('id', 'N/A')}")
    lines.append(f"Name: {item.get('name', 'N/A')}")
    lines.append(f"Type: {item.get('type', 'N/A')}")

    if item.get("description"):
        lines.append(f"Description: {item['description']}")
    if item.get("visibility"):
        lines.append(f"Visibility: {item['visibility']}")
    if item.get("index") is not None:
        lines.append(f"Index: {item['index']}")
    if item.get("hide_script") is not None:
        lines.append(f"Hide Script: {item['hide_script']}")
    if item.get("content"):
        lines.append(f"Content: {json.dumps(item['content'], indent=2)}")

    return "\n".join(lines)


def _format_one_interval(i: int, interval: dict[str, Any]) -> str:
    """Render a single icu_intervals entry. Trailing blank line included."""
    return f"""[{i}] {interval.get("label", f"Interval {i}")} ({interval.get("type", "Unknown")})
Duration: {interval.get("elapsed_time", 0)} seconds (moving: {interval.get("moving_time", 0)} seconds)
Distance: {interval.get("distance", 0)} meters
Start-End Indices: {interval.get("start_index", 0)}-{interval.get("end_index", 0)}

Power Metrics:
  Average Power: {interval.get("average_watts", 0)} watts ({interval.get("average_watts_kg", 0)} W/kg)
  Max Power: {interval.get("max_watts", 0)} watts ({interval.get("max_watts_kg", 0)} W/kg)
  Weighted Avg Power: {interval.get("weighted_average_watts", 0)} watts
  Intensity: {interval.get("intensity", 0)}
  Training Load: {interval.get("training_load", 0)}
  Joules: {interval.get("joules", 0)}
  Joules > FTP: {interval.get("joules_above_ftp", 0)}
  Power Zone: {interval.get("zone", "N/A")} ({interval.get("zone_min_watts", 0)}-{interval.get("zone_max_watts", 0)} watts)
  W' Balance: Start {interval.get("wbal_start", 0)}, End {interval.get("wbal_end", 0)}
  L/R Balance: {interval.get("avg_lr_balance", 0)}
  Variability: {interval.get("w5s_variability", 0)}
  Torque: Avg {interval.get("average_torque", 0)}, Min {interval.get("min_torque", 0)}, Max {interval.get("max_torque", 0)}

Heart Rate & Metabolic:
  Heart Rate: Avg {interval.get("average_heartrate", 0)}, Min {interval.get("min_heartrate", 0)}, Max {interval.get("max_heartrate", 0)} bpm
  Decoupling: {interval.get("decoupling", 0)}
  DFA α1: {interval.get("average_dfa_a1", 0)}
  Respiration: {interval.get("average_respiration", 0)} breaths/min
  EPOC: {interval.get("average_epoc", 0)}
  SmO2: {interval.get("average_smo2", 0)}% / {interval.get("average_smo2_2", 0)}%
  THb: {interval.get("average_thb", 0)} / {interval.get("average_thb_2", 0)}

Speed & Cadence:
  Speed: Avg {interval.get("average_speed", 0)}, Min {interval.get("min_speed", 0)}, Max {interval.get("max_speed", 0)} m/s
  GAP: {interval.get("gap", 0)} m/s
  Cadence: Avg {interval.get("average_cadence", 0)}, Min {interval.get("min_cadence", 0)}, Max {interval.get("max_cadence", 0)} rpm
  Stride: {interval.get("average_stride", 0)}

Elevation & Environment:
  Elevation Gain: {interval.get("total_elevation_gain", 0)} meters
  Altitude: Min {interval.get("min_altitude", 0)}, Max {interval.get("max_altitude", 0)} meters
  Gradient: {interval.get("average_gradient", 0)}%
  Temperature: {interval.get("average_temp", 0)}°C (Weather: {interval.get("average_weather_temp", 0)}°C, Feels like: {interval.get("average_feels_like", 0)}°C)
  Wind: Speed {interval.get("average_wind_speed", 0)} km/h, Gust {interval.get("average_wind_gust", 0)} km/h, Direction {interval.get("prevailing_wind_deg", 0)}°
  Headwind: {interval.get("headwind_percent", 0)}%, Tailwind: {interval.get("tailwind_percent", 0)}%

"""


def _format_one_group(i: int, group: dict[str, Any]) -> str:
    """Render a single icu_groups entry. Trailing blank line included."""
    return f"""Group: {group.get("id", f"Group {i}")} (Contains {group.get("count", 0)} intervals)
Duration: {group.get("elapsed_time", 0)} seconds (moving: {group.get("moving_time", 0)} seconds)
Distance: {group.get("distance", 0)} meters
Start-End Indices: {group.get("start_index", 0)}-N/A

Power: Avg {group.get("average_watts", 0)} watts ({group.get("average_watts_kg", 0)} W/kg), Max {group.get("max_watts", 0)} watts
W. Avg Power: {group.get("weighted_average_watts", 0)} watts, Intensity: {group.get("intensity", 0)}
Heart Rate: Avg {group.get("average_heartrate", 0)}, Max {group.get("max_heartrate", 0)} bpm
Speed: Avg {group.get("average_speed", 0)}, Max {group.get("max_speed", 0)} m/s
Cadence: Avg {group.get("average_cadence", 0)}, Max {group.get("max_cadence", 0)} rpm

"""


def format_intervals(intervals_data: dict[str, Any]) -> str:
    """Render Intervals.icu intervals + groups payload as a single readable string."""
    result = f"""Intervals Analysis:

ID: {intervals_data.get("id", "N/A")}
Analyzed: {intervals_data.get("analyzed", "N/A")}

"""

    if intervals_data.get("icu_intervals"):
        result += "Individual Intervals:\n\n"
        for i, interval in enumerate(intervals_data["icu_intervals"], 1):
            result += _format_one_interval(i, interval)

    if intervals_data.get("icu_groups"):
        result += "Interval Groups:\n\n"
        for i, group in enumerate(intervals_data["icu_groups"], 1):
            result += _format_one_group(i, group)

    return result
