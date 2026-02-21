"""
Formatting utilities for Intervals.icu MCP Server

This module contains formatting functions for handling data from the Intervals.icu API.
"""

from datetime import datetime
from typing import Any


def format_date_with_day_of_week(date_value: str) -> str:
    """Format a date string to include day of week for better readability.

    Args:
        date_value: Date string in ISO-8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)

    Returns:
        Formatted date string with day of week prefix (e.g., "Saturday, 2026-02-21")
        or original value if parsing fails
    """
    if not date_value or date_value in ("Unknown", "N/A"):
        return date_value

    try:
        # Handle both date-only and datetime formats
        date_str = date_value.split("T")[0]  # Extract YYYY-MM-DD part
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_week = date_obj.strftime("%A")
        return f"{day_of_week}, {date_value}"
    except (ValueError, AttributeError):
        return date_value


def _add_field(lines: list[str], label: str, value: Any, unit: str = "") -> None:
    """Add a field to lines only if value is not None/empty."""
    if value is not None and value != "" and value != "N/A":
        lines.append(f"{label}: {value}{unit}")


def format_activity_summary(activity: dict[str, Any]) -> str:
    """Format an activity into a readable string, showing only non-empty fields."""
    lines = []

    # Basic info (always show)
    start_time = activity.get("startTime", activity.get("start_date", "Unknown"))
    if isinstance(start_time, str) and len(start_time) > 10:
        try:
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            start_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    lines.append(f"Activity: {activity.get('name', 'Unnamed')}")
    _add_field(lines, "ID", activity.get("id"))
    _add_field(lines, "Type", activity.get("type"))
    _add_field(lines, "Date", start_time)
    _add_field(lines, "Description", activity.get("description"))
    _add_field(lines, "Distance", activity.get("distance"), " meters")
    _add_field(lines, "Duration", activity.get("duration") or activity.get("elapsed_time"), " seconds")
    _add_field(lines, "Moving Time", activity.get("moving_time"), " seconds")

    elevation_gain = activity.get("elevationGain") or activity.get("total_elevation_gain")
    _add_field(lines, "Elevation Gain", elevation_gain, " meters")
    _add_field(lines, "Elevation Loss", activity.get("total_elevation_loss"), " meters")

    # Power Data
    power_lines: list[str] = []
    avg_power = activity.get("avgPower") or activity.get("icu_average_watts") or activity.get("average_watts")
    _add_field(power_lines, "Average Power", avg_power, " watts")
    _add_field(power_lines, "Weighted Avg Power", activity.get("icu_weighted_avg_watts"), " watts")
    _add_field(power_lines, "Training Load", activity.get("trainingLoad") or activity.get("icu_training_load"))
    _add_field(power_lines, "FTP", activity.get("icu_ftp"), " watts")
    _add_field(power_lines, "Kilojoules", activity.get("icu_joules"))
    _add_field(power_lines, "Intensity", activity.get("icu_intensity"))
    _add_field(power_lines, "Power:HR Ratio", activity.get("icu_power_hr"))
    _add_field(power_lines, "Variability Index", activity.get("icu_variability_index"))

    if power_lines:
        lines.append("\nPower Data:")
        lines.extend(power_lines)

    # Heart Rate Data
    hr_lines: list[str] = []
    avg_hr = activity.get("avgHr") or activity.get("average_heartrate")
    _add_field(hr_lines, "Average Heart Rate", avg_hr, " bpm")
    _add_field(hr_lines, "Max Heart Rate", activity.get("max_heartrate"), " bpm")
    _add_field(hr_lines, "LTHR", activity.get("lthr"), " bpm")
    _add_field(hr_lines, "Resting HR", activity.get("icu_resting_hr"), " bpm")
    _add_field(hr_lines, "Decoupling", activity.get("decoupling"))

    if hr_lines:
        lines.append("\nHeart Rate Data:")
        lines.extend(hr_lines)

    # Other Metrics
    other_lines: list[str] = []
    _add_field(other_lines, "Cadence", activity.get("average_cadence"), " rpm")
    _add_field(other_lines, "Calories", activity.get("calories"))
    _add_field(other_lines, "Average Speed", activity.get("average_speed"), " m/s")
    _add_field(other_lines, "Max Speed", activity.get("max_speed"), " m/s")
    _add_field(other_lines, "Average Stride", activity.get("average_stride"))
    _add_field(other_lines, "L/R Balance", activity.get("avg_lr_balance"))
    _add_field(other_lines, "Weight", activity.get("icu_weight"), " kg")

    rpe = activity.get("perceived_exertion") or activity.get("icu_rpe")
    if rpe is not None:
        rpe_str = f"{rpe}/10" if isinstance(rpe, (int, float)) else str(rpe)
        _add_field(other_lines, "RPE", rpe_str)
    _add_field(other_lines, "Session RPE", activity.get("session_rpe"))

    feel = activity.get("feel")
    if feel is not None:
        feel_str = f"{feel}/5" if isinstance(feel, int) else str(feel)
        _add_field(other_lines, "Feel", feel_str)

    if other_lines:
        lines.append("\nOther Metrics:")
        lines.extend(other_lines)

    # Environment
    env_lines: list[str] = []
    if activity.get("trainer") is not None:
        _add_field(env_lines, "Trainer", activity.get("trainer"))
    _add_field(env_lines, "Average Temp", activity.get("average_temp"), "°C")
    _add_field(env_lines, "Min Temp", activity.get("min_temp"), "°C")
    _add_field(env_lines, "Max Temp", activity.get("max_temp"), "°C")
    _add_field(env_lines, "Avg Wind Speed", activity.get("average_wind_speed"), " km/h")
    _add_field(env_lines, "Headwind %", activity.get("headwind_percent"), "%")
    _add_field(env_lines, "Tailwind %", activity.get("tailwind_percent"), "%")

    if env_lines:
        lines.append("\nEnvironment:")
        lines.extend(env_lines)

    # Training Metrics
    training_lines: list[str] = []
    _add_field(training_lines, "Fitness (CTL)", activity.get("icu_ctl"))
    _add_field(training_lines, "Fatigue (ATL)", activity.get("icu_atl"))
    _add_field(training_lines, "TRIMP", activity.get("trimp"))
    if activity.get("polarization_index") is not None:
        _add_field(training_lines, "Polarization Index", activity.get("polarization_index"))
    _add_field(training_lines, "Power Load", activity.get("power_load"))
    _add_field(training_lines, "HR Load", activity.get("hr_load"))
    _add_field(training_lines, "Pace Load", activity.get("pace_load"))
    _add_field(training_lines, "Efficiency Factor", activity.get("icu_efficiency_factor"))

    if training_lines:
        lines.append("\nTraining Metrics:")
        lines.extend(training_lines)

    # Device Info
    device_lines: list[str] = []
    _add_field(device_lines, "Device", activity.get("device_name"))
    _add_field(device_lines, "Power Meter", activity.get("power_meter"))
    _add_field(device_lines, "File Type", activity.get("file_type"))

    if device_lines:
        lines.append("\nDevice Info:")
        lines.extend(device_lines)

    return "\n".join(lines) + "\n"


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
    lines = ["Wellness Data:"]
    date_value = entries.get('id', 'N/A')
    formatted_date = format_date_with_day_of_week(date_value)
    lines.append(f"Date: {formatted_date}")
    lines.append("")

    training_metrics = _format_training_metrics(entries)
    if training_metrics:
        lines.append("Training Metrics:")
        lines.extend(training_metrics)
        lines.append("")

    sport_info_list = _format_sport_info(entries)
    if sport_info_list:
        lines.append("Sport-Specific Info:")
        lines.extend(sport_info_list)
        lines.append("")

    vital_signs = _format_vital_signs(entries)
    if vital_signs:
        lines.append("Vital Signs:")
        lines.extend(vital_signs)
        lines.append("")

    sleep_lines = _format_sleep_recovery(entries)
    if sleep_lines:
        lines.append("Sleep & Recovery:")
        lines.extend(sleep_lines)
        lines.append("")

    menstrual_lines = _format_menstrual_tracking(entries)
    if menstrual_lines:
        lines.append("Menstrual Tracking:")
        lines.extend(menstrual_lines)
        lines.append("")

    subjective_lines = _format_subjective_feelings(entries)
    if subjective_lines:
        lines.append("Subjective Feelings:")
        lines.extend(subjective_lines)
        lines.append("")

    nutrition_lines = _format_nutrition_hydration(entries)
    if nutrition_lines:
        lines.append("Nutrition & Hydration:")
        lines.extend(nutrition_lines)
        lines.append("")

    if entries.get("steps") is not None:
        lines.append("Activity:")
        lines.append(f"- Steps: {entries['steps']}")
        lines.append("")

    if entries.get("comments"):
        lines.append(f"Comments: {entries['comments']}")
    if "locked" in entries:
        lines.append(f"Status: {'Locked' if entries.get('locked') else 'Unlocked'}")

    return "\n".join(lines)


def format_event_summary(event: dict[str, Any]) -> str:
    """Format a basic event summary into a readable string."""

    # Update to check for "date" if "start_date_local" is not provided
    event_date = event.get("start_date_local", event.get("date", "Unknown"))
    formatted_date = format_date_with_day_of_week(event_date)

    event_type = "Workout" if event.get("workout") else "Race" if event.get("race") else "Other"
    event_name = event.get("name", "Unnamed")
    event_id = event.get("id", "N/A")
    event_desc = event.get("description", "No description")

    return f"""Date: {formatted_date}
ID: {event_id}
Type: {event_type}
Name: {event_name}
Description: {event_desc}"""


def format_event_details(event: dict[str, Any]) -> str:
    """Format detailed event information into a readable string."""

    event_date = event.get("date", "Unknown")
    formatted_date = format_date_with_day_of_week(event_date)

    event_details = f"""Event Details:

ID: {event.get("id", "N/A")}
Date: {formatted_date}
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
