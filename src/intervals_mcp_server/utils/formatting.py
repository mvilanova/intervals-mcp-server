"""
Formatting utilities for Intervals.icu MCP Server

This module contains formatting functions for handling data from the Intervals.icu API.
"""

import re
from datetime import datetime
from typing import Any


def _is_camelcase(field_name: str) -> bool:
    """Check if a field name is camelCase (starts with lowercase, contains uppercase).

    Args:
        field_name: The field name to check

    Returns:
        True if the field is camelCase, False otherwise
    """
    if not field_name:
        return False
    # Must start with lowercase letter and contain at least one uppercase letter
    return field_name[0].islower() and any(c.isupper() for c in field_name)


def _detect_custom_fields(data: dict[str, Any], known_fields: set[str]) -> dict[str, Any]:
    """Detect custom camelCase fields in API response that are not already handled.

    Args:
        data: Dictionary containing API response data
        known_fields: Set of field names that are already handled by formatting functions

    Returns:
        Dictionary containing only custom field key-value pairs
    """
    custom_fields: dict[str, Any] = {}
    for key, value in data.items():
        # Skip if field is already known/displayed
        if key in known_fields:
            continue
        # Only include camelCase fields (custom fields convention)
        if _is_camelcase(key):
            custom_fields[key] = value
    return custom_fields


def _format_custom_fields(custom_fields: dict[str, Any]) -> list[str]:
    """Format custom fields into a readable list of strings.

    Args:
        custom_fields: Dictionary of custom field key-value pairs

    Returns:
        List of formatted strings, or empty list if no custom fields
    """
    if not custom_fields:
        return []

    formatted_lines: list[str] = []
    for key, value in sorted(custom_fields.items()):
        # Format the field name (convert camelCase to more readable format)
        # e.g., "customFieldName" -> "Custom Field Name"
        formatted_key = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
        # Capitalize first letter, ensuring we have at least one character before indexing
        if formatted_key and len(formatted_key) > 0:
            formatted_key = formatted_key[0].upper() + formatted_key[1:]
        elif key and len(key) > 0:
            # Fallback to original key if formatted_key is empty
            formatted_key = key[0].upper() + key[1:]
        else:
            # Both are empty (shouldn't happen due to _is_camelcase check, but be defensive)
            formatted_key = key if key else "Unknown"

        # Format the value based on type
        if value is None:
            formatted_value = "N/A"
        elif isinstance(value, bool):
            formatted_value = str(value)
        elif isinstance(value, (int, float)):
            formatted_value = str(value)
        elif isinstance(value, str):
            formatted_value = value
        elif isinstance(value, (list, dict)):
            formatted_value = str(value)
        else:
            formatted_value = str(value)

        formatted_lines.append(f"- {formatted_key}: {formatted_value}")

    return formatted_lines


# Known activity fields that are already displayed in format_activity_summary
_KNOWN_ACTIVITY_FIELDS = {
    "name",
    "id",
    "type",
    "startTime",
    "start_date",
    "description",
    "distance",
    "duration",
    "elapsed_time",
    "moving_time",
    "elevationGain",
    "total_elevation_gain",
    "total_elevation_loss",
    "perceived_exertion",
    "icu_rpe",
    "feel",
    "avgPower",
    "icu_average_watts",
    "average_watts",
    "icu_weighted_avg_watts",
    "trainingLoad",
    "icu_training_load",
    "icu_ftp",
    "icu_joules",
    "icu_intensity",
    "icu_power_hr",
    "icu_variability_index",
    "avgHr",
    "average_heartrate",
    "max_heartrate",
    "lthr",
    "icu_resting_hr",
    "decoupling",
    "average_cadence",
    "calories",
    "average_speed",
    "max_speed",
    "average_stride",
    "avg_lr_balance",
    "icu_weight",
    "session_rpe",
    "trainer",
    "average_temp",
    "min_temp",
    "max_temp",
    "average_wind_speed",
    "headwind_percent",
    "tailwind_percent",
    "icu_ctl",
    "icu_atl",
    "trimp",
    "polarization_index",
    "power_load",
    "hr_load",
    "pace_load",
    "icu_efficiency_factor",
    "device_name",
    "power_meter",
    "file_type",
}


# Known wellness fields that are already displayed in format_wellness_entry
_KNOWN_WELLNESS_FIELDS = {
    "id",
    "date",
    "ctl",
    "atl",
    "rampRate",
    "ctlLoad",
    "atlLoad",
    "sportInfo",
    "updated",
    "weight",
    "restingHR",
    "hrv",
    "hrvSDNN",
    "avgSleepingHR",
    "spO2",
    "systolic",
    "diastolic",
    "respiration",
    "bloodGlucose",
    "lactate",
    "vo2max",
    "bodyFat",
    "abdomen",
    "baevskySI",
    "sleepSecs",
    "sleepHours",
    "sleepQuality",
    "sleepScore",
    "readiness",
    "menstrualPhase",
    "menstrualPhasePredicted",
    "soreness",
    "fatigue",
    "stress",
    "mood",
    "motivation",
    "injury",
    "kcalConsumed",
    "hydrationVolume",
    "hydration",
    "steps",
    "comments",
    "locked",
}


def _format_activity_start_time(activity: dict[str, Any]) -> str:
    """Format activity start time from activity data."""
    start_time = activity.get("startTime", activity.get("start_date", "Unknown"))
    if isinstance(start_time, str) and len(start_time) > 10:
        try:
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            start_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return start_time


def _format_activity_rpe(activity: dict[str, Any]) -> str:
    """Format RPE (Rate of Perceived Exertion) from activity data."""
    rpe = activity.get("perceived_exertion", None)
    if rpe is None:
        rpe = activity.get("icu_rpe", "N/A")
    if isinstance(rpe, (int, float)):
        rpe = f"{rpe}/10"
    return rpe


def _format_activity_feel(activity: dict[str, Any]) -> str:
    """Format feel value from activity data."""
    feel = activity.get("feel", "N/A")
    if isinstance(feel, int):
        feel = f"{feel}/5"
    return feel


def format_activity_summary(activity: dict[str, Any]) -> str:
    """Format an activity into a readable string."""
    start_time = _format_activity_start_time(activity)
    rpe = _format_activity_rpe(activity)
    feel = _format_activity_feel(activity)

    # Detect and format custom fields
    custom_fields = _detect_custom_fields(activity, _KNOWN_ACTIVITY_FIELDS)
    custom_fields_lines = _format_custom_fields(custom_fields)

    result = f"""
Activity: {activity.get("name", "Unnamed")}
ID: {activity.get("id", "N/A")}
Type: {activity.get("type", "Unknown")}
Date: {start_time}
Description: {activity.get("description", "N/A")}
Distance: {activity.get("distance", 0)} meters
Duration: {activity.get("duration", activity.get("elapsed_time", 0))} seconds
Moving Time: {activity.get("moving_time", "N/A")} seconds
Elevation Gain: {activity.get("elevationGain", activity.get("total_elevation_gain", 0))} meters
Elevation Loss: {activity.get("total_elevation_loss", "N/A")} meters

Power Data:
Average Power: {activity.get("avgPower", activity.get("icu_average_watts", activity.get("average_watts", "N/A")))} watts
Weighted Avg Power: {activity.get("icu_weighted_avg_watts", "N/A")} watts
Training Load: {activity.get("trainingLoad", activity.get("icu_training_load", "N/A"))}
FTP: {activity.get("icu_ftp", "N/A")} watts
Kilojoules: {activity.get("icu_joules", "N/A")}
Intensity: {activity.get("icu_intensity", "N/A")}
Power:HR Ratio: {activity.get("icu_power_hr", "N/A")}
Variability Index: {activity.get("icu_variability_index", "N/A")}

Heart Rate Data:
Average Heart Rate: {activity.get("avgHr", activity.get("average_heartrate", "N/A"))} bpm
Max Heart Rate: {activity.get("max_heartrate", "N/A")} bpm
LTHR: {activity.get("lthr", "N/A")} bpm
Resting HR: {activity.get("icu_resting_hr", "N/A")} bpm
Decoupling: {activity.get("decoupling", "N/A")}

Other Metrics:
Cadence: {activity.get("average_cadence", "N/A")} rpm
Calories: {activity.get("calories", "N/A")}
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
File Type: {activity.get("file_type", "N/A")}"""

    # Append custom fields section if any custom fields were found
    if custom_fields_lines:
        result += "\n\nCustom Fields:"
        result += "\n" + "\n".join(custom_fields_lines)

    return result


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


def _format_training_metrics(entries: dict[str, Any]) -> list[str]:
    """Format training metrics section."""
    training_metrics = []
    for k, label in [
        ("ctl", "Fitness (CTL)"),
        ("atl", "Fatigue (ATL)"),
        ("rampRate", "Ramp Rate"),
        ("ctlLoad", "CTL Load"),
        ("atlLoad", "ATL Load"),
    ]:
        if entries.get(k) is not None:
            training_metrics.append(f"- {label}: {entries[k]}")
    return training_metrics


def _format_sport_info(entries: dict[str, Any]) -> list[str]:
    """Format sport-specific info section."""
    sport_info_list = []
    if entries.get("sportInfo"):
        for sport in entries.get("sportInfo", []):
            if isinstance(sport, dict) and sport.get("eftp") is not None:
                sport_info_list.append(f"- {sport.get('type')}: eFTP = {sport['eftp']}")
    return sport_info_list


def _format_vital_signs(entries: dict[str, Any]) -> list[str]:
    """Format vital signs section."""
    vital_signs = []
    for k, label, unit in [
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
    ]:
        if entries.get(k) is not None:
            value = entries[k]
            if k == "systolic" and entries.get("diastolic") is not None:
                vital_signs.append(
                    f"- Blood Pressure: {entries['systolic']}/{entries['diastolic']} mmHg"
                )
            elif k not in ("systolic", "diastolic"):
                vital_signs.append(f"- {label}: {value}{(' ' + unit) if unit else ''}")
    return vital_signs


def _format_sleep_recovery(entries: dict[str, Any]) -> list[str]:
    """Format sleep and recovery section."""
    sleep_lines = []
    sleep_hours = None
    if entries.get("sleepSecs") is not None:
        sleep_hours = f"{entries['sleepSecs'] / 3600:.2f}"
    elif entries.get("sleepHours") is not None:
        sleep_hours = f"{entries['sleepHours']}"
    if sleep_hours is not None:
        sleep_lines.append(f"  Sleep: {sleep_hours} hours")

    if entries.get("sleepQuality") is not None:
        quality_value = entries["sleepQuality"]
        quality_labels = {1: "Great", 2: "Good", 3: "Average", 4: "Poor"}
        quality_text = quality_labels.get(quality_value, str(quality_value))
        sleep_lines.append(f"  Sleep Quality: {quality_value} ({quality_text})")

    if entries.get("sleepScore") is not None:
        sleep_lines.append(f"  Device Sleep Score: {entries['sleepScore']}/100")

    if entries.get("readiness") is not None:
        sleep_lines.append(f"  Readiness: {entries['readiness']}/10")

    return sleep_lines


def _format_menstrual_tracking(entries: dict[str, Any]) -> list[str]:
    """Format menstrual tracking section."""
    menstrual_lines = []
    if entries.get("menstrualPhase") is not None:
        menstrual_lines.append(f"  Menstrual Phase: {str(entries['menstrualPhase']).capitalize()}")
    if entries.get("menstrualPhasePredicted") is not None:
        menstrual_lines.append(
            f"  Predicted Phase: {str(entries['menstrualPhasePredicted']).capitalize()}"
        )
    return menstrual_lines


def _format_subjective_feelings(entries: dict[str, Any]) -> list[str]:
    """Format subjective feelings section."""
    subjective_lines = []
    for k, label in [
        ("soreness", "Soreness"),
        ("fatigue", "Fatigue"),
        ("stress", "Stress"),
        ("mood", "Mood"),
        ("motivation", "Motivation"),
        ("injury", "Injury Level"),
    ]:
        if entries.get(k) is not None:
            subjective_lines.append(f"  {label}: {entries[k]}/10")
    return subjective_lines


def _format_nutrition_hydration(entries: dict[str, Any]) -> list[str]:
    """Format nutrition and hydration section."""
    nutrition_lines = []
    for k, label in [
        ("kcalConsumed", "Calories Consumed"),
        ("hydrationVolume", "Hydration Volume"),
    ]:
        if entries.get(k) is not None:
            nutrition_lines.append(f"- {label}: {entries[k]}")

    if entries.get("hydration") is not None:
        nutrition_lines.append(f"  Hydration Score: {entries['hydration']}/10")

    return nutrition_lines


def _add_wellness_section(lines: list[str], section_lines: list[str], section_title: str) -> None:
    """Add a wellness section to the lines list if it has content.

    Args:
        lines: The list of lines being built
        section_lines: The formatted lines for this section
        section_title: The title of the section
    """
    if section_lines:
        lines.append(section_title)
        lines.extend(section_lines)
        lines.append("")


def format_wellness_entry(entries: dict[str, Any]) -> str:
    """Format wellness entry data into a readable string.

    Formats various wellness metrics including training metrics, vital signs,
    sleep data, menstrual tracking, subjective feelings, nutrition, and activity.

    Args:
        entries: Dictionary containing wellness data fields such as:
            - Training metrics: ctl, atl, rampRate, ctlLoad, atlLoad
            - Vital signs: weight, restingHR, hrv, hrvSDNN, avgSleepingHR, spO2,
              systolic, diastolic, respiration, bloodGlucose, lactate, vo2max,
              bodyFat, abdomen, baevskySI
            - Sleep: sleepSecs, sleepHours, sleepQuality, sleepScore, readiness
            - Menstrual: menstrualPhase, menstrualPhasePredicted
            - Subjective: soreness, fatigue, stress, mood, motivation, injury
            - Nutrition: kcalConsumed, hydrationVolume, hydration
            - Activity: steps
            - Other: comments, locked, date

    Returns:
        A formatted string representation of the wellness entry.
    """
    lines = ["Wellness Data:", f"Date: {entries.get('id', 'N/A')}", ""]

    _add_wellness_section(lines, _format_training_metrics(entries), "Training Metrics:")
    _add_wellness_section(lines, _format_sport_info(entries), "Sport-Specific Info:")
    _add_wellness_section(lines, _format_vital_signs(entries), "Vital Signs:")
    _add_wellness_section(lines, _format_sleep_recovery(entries), "Sleep & Recovery:")
    _add_wellness_section(lines, _format_menstrual_tracking(entries), "Menstrual Tracking:")
    _add_wellness_section(lines, _format_subjective_feelings(entries), "Subjective Feelings:")
    _add_wellness_section(lines, _format_nutrition_hydration(entries), "Nutrition & Hydration:")

    if entries.get("steps") is not None:
        lines.extend(["Activity:", f"- Steps: {entries['steps']}", ""])

    if entries.get("comments"):
        lines.append(f"Comments: {entries['comments']}")
    if "locked" in entries:
        lines.append(f"Status: {'Locked' if entries.get('locked') else 'Unlocked'}")

    # Detect and format custom fields
    custom_fields = _detect_custom_fields(entries, _KNOWN_WELLNESS_FIELDS)
    custom_fields_lines = _format_custom_fields(custom_fields)

    # Append custom fields section if any custom fields were found
    if custom_fields_lines:
        lines.extend(["", "Custom Fields:"])
        lines.extend(custom_fields_lines)

    return "\n".join(lines)


def format_event_summary(event: dict[str, Any]) -> str:
    """Format a basic event summary into a readable string."""

    # Update to check for "date" if "start_date_local" is not provided
    event_date = event.get("start_date_local", event.get("date", "Unknown"))
    event_type = "Workout" if event.get("workout") else "Race" if event.get("race") else "Other"
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

    event_details = f"""Event Details:

ID: {event.get("id", "N/A")}
Date: {event.get("date", "Unknown")}
Name: {event.get("name", "Unnamed")}
Description: {event.get("description", "No description")}"""

    # Check if it's a workout-based event
    if "workout" in event and event["workout"]:
        workout = event["workout"]
        event_details += f"""

Workout Information:
Workout ID: {workout.get("id", "N/A")}
Sport: {workout.get("sport", "Unknown")}
Duration: {workout.get("duration", 0)} seconds
TSS: {workout.get("tss", "N/A")}"""

        # Include interval count if available
        if "intervals" in workout and isinstance(workout["intervals"], list):
            event_details += f"""
Intervals: {len(workout["intervals"])}"""

    # Check if it's a race
    if event.get("race"):
        event_details += f"""

Race Information:
Priority: {event.get("priority", "N/A")}
Result: {event.get("result", "N/A")}"""

    # Include calendar information
    if "calendar" in event:
        cal = event["calendar"]
        event_details += f"""

Calendar: {cal.get("name", "N/A")}"""

    return event_details


def format_intervals(intervals_data: dict[str, Any]) -> str:
    """Format intervals data into a readable string with all available fields.

    Args:
        intervals_data: The intervals data from the Intervals.icu API

    Returns:
        A formatted string representation of the intervals data
    """
    # Format basic intervals information
    result = f"""Intervals Analysis:

ID: {intervals_data.get("id", "N/A")}
Analyzed: {intervals_data.get("analyzed", "N/A")}

"""

    # Format individual intervals
    if "icu_intervals" in intervals_data and intervals_data["icu_intervals"]:
        result += "Individual Intervals:\n\n"

        for i, interval in enumerate(intervals_data["icu_intervals"], 1):
            result += f"""[{i}] {interval.get("label", f"Interval {i}")} ({interval.get("type", "Unknown")})
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

    # Format interval groups
    if "icu_groups" in intervals_data and intervals_data["icu_groups"]:
        result += "Interval Groups:\n\n"

        for i, group in enumerate(intervals_data["icu_groups"], 1):
            result += f"""Group: {group.get("id", f"Group {i}")} (Contains {group.get("count", 0)} intervals)
Duration: {group.get("elapsed_time", 0)} seconds (moving: {group.get("moving_time", 0)} seconds)
Distance: {group.get("distance", 0)} meters
Start-End Indices: {group.get("start_index", 0)}-N/A

Power: Avg {group.get("average_watts", 0)} watts ({group.get("average_watts_kg", 0)} W/kg), Max {group.get("max_watts", 0)} watts
W. Avg Power: {group.get("weighted_average_watts", 0)} watts, Intensity: {group.get("intensity", 0)}
Heart Rate: Avg {group.get("average_heartrate", 0)}, Max {group.get("max_heartrate", 0)} bpm
Speed: Avg {group.get("average_speed", 0)}, Max {group.get("max_speed", 0)} m/s
Cadence: Avg {group.get("average_cadence", 0)}, Max {group.get("max_cadence", 0)} rpm

"""

    return result
