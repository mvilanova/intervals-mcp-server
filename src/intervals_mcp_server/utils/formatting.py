"""
Formatting utilities for Intervals.icu MCP Server

This module contains formatting functions for handling data from the Intervals.icu API.
"""

from datetime import datetime
from typing import Any


def format_activity_summary(activity: dict[str, Any]) -> str:
    """Format an activity into a readable string."""
    start_time = activity.get("startTime", activity.get("start_date", "Unknown"))

    if isinstance(start_time, str) and len(start_time) > 10:
        # Format datetime if it's a full ISO string
        try:
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            start_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    return f"""
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
Perceived Exertion: {activity.get("perceived_exertion", activity.get("icu_rpe", "N/A"))}/10
Session RPE: {activity.get("session_rpe", "N/A")}
Feel: {activity.get("feel", "N/A")}/10

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


def format_wellness_entry(entry: dict[str, Any]) -> str:
    """Format a wellness data entry into a readable string with all available fields."""

    # Convert sleep seconds to hours if available
    sleep_hours = "N/A"
    if entry.get("sleepSecs") is not None:
        sleep_seconds = entry.get("sleepSecs")
        if sleep_seconds is not None:  # Extra check to avoid None division
            sleep_hours = f"{sleep_seconds / 3600:.2f}"
    elif entry.get("sleepHours") is not None:
        # Some responses might use sleepHours directly
        sleep_hours = f"{entry.get('sleepHours')}"

    # Format menstrual phase with proper capitalization if present
    menstrual_phase = entry.get("menstrualPhase", "N/A")
    if menstrual_phase != "N/A" and menstrual_phase is not None:
        menstrual_phase = menstrual_phase.capitalize()
    else:
        menstrual_phase = "N/A"

    menstrual_phase_predicted = entry.get("menstrualPhasePredicted", "N/A")
    if menstrual_phase_predicted != "N/A" and menstrual_phase_predicted is not None:
        menstrual_phase_predicted = menstrual_phase_predicted.capitalize()
    else:
        menstrual_phase_predicted = "N/A"

    # Format sport information if available
    sport_info_list = []
    if entry.get("sportInfo"):
        for sport in entry.get("sportInfo", []):
            if isinstance(sport, dict):
                sport_info_list.append(
                    f"  * {sport.get('type', 'Unknown')}: eFTP = {sport.get('eftp', 'N/A')}"
                )

    # Create sport info string
    if sport_info_list:
        sport_info = "\n".join(sport_info_list)
    else:
        sport_info = "  None available"

    return f"""Date: {entry.get("date", "Unknown date")}
ID: {entry.get("id", "N/A")}

Training Metrics:
  Fitness (CTL): {entry.get("ctl", "N/A")}
  Fatigue (ATL): {entry.get("atl", "N/A")}
  Ramp Rate: {entry.get("rampRate", "N/A")}
  CTL Load: {entry.get("ctlLoad", "N/A")}
  ATL Load: {entry.get("atlLoad", "N/A")}

Sport-Specific Info:
{sport_info}

Vital Signs:
  Weight: {entry.get("weight", "N/A")} kg
  Resting HR: {entry.get("restingHR", "N/A")} bpm
  HRV: {entry.get("hrv", "N/A")}
  HRV SDNN: {entry.get("hrvSDNN", "N/A")}
  Average Sleeping HR: {entry.get("avgSleepingHR", "N/A")} bpm
  SpO2: {entry.get("spO2", "N/A")}%
  Blood Pressure: {entry.get("systolic", "N/A")}/{entry.get("diastolic", "N/A")} mmHg
  Respiration: {entry.get("respiration", "N/A")} breaths/min
  Blood Glucose: {entry.get("bloodGlucose", "N/A")} mmol/L
  Lactate: {entry.get("lactate", "N/A")} mmol/L
  VO2 Max: {entry.get("vo2max", "N/A")} ml/kg/min
  Body Fat: {entry.get("bodyFat", "N/A")}%
  Abdomen: {entry.get("abdomen", "N/A")} cm
  Baevsky Stress Index: {entry.get("baevskySI", "N/A")}

Sleep & Recovery:
  Sleep: {sleep_hours} hours
  Sleep Score: {entry.get("sleepScore", "N/A")}/100
  Sleep Quality: {entry.get("sleepQuality", "N/A")}/10
  Readiness: {entry.get("readiness", "N/A")}/10

Menstrual Tracking:
  Menstrual Phase: {menstrual_phase}
  Predicted Phase: {menstrual_phase_predicted}

Subjective Feelings:
  Soreness: {entry.get("soreness", "N/A")}/10
  Fatigue: {entry.get("fatigue", "N/A")}/10
  Stress: {entry.get("stress", "N/A")}/10
  Mood: {entry.get("mood", "N/A")}/10
  Motivation: {entry.get("motivation", "N/A")}/10
  Injury Level: {entry.get("injury", "N/A")}/10

Nutrition & Hydration:
  Calories Consumed: {entry.get("kcalConsumed", "N/A")} kcal
  Hydration Score: {entry.get("hydration", "N/A")}/10
  Hydration Volume: {entry.get("hydrationVolume", "N/A")} ml

Activity:
  Steps: {entry.get("steps", "N/A")}

Comments: {entry.get("comments", "No comments")}
Status: {"Locked" if entry.get("locked") else "Unlocked"}
Last Updated: {entry.get("updated", "Unknown")}"""


def format_event_summary(event: dict[str, Any]) -> str:
    """Format a basic event summary into a readable string."""

    event_date = event.get("start_date_local", "Unknown")
    event_type = (
        "Workout" if event.get("workout") else "Race" if event.get("race") else "Other"
    )
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
            interval_type = interval.get("type", "Unknown")
            label = interval.get("label", f"Interval {i}")

            # Format duration, distance, and time information
            moving_time = interval.get("moving_time", 0)
            elapsed_time = interval.get("elapsed_time", 0)
            distance = interval.get("distance", 0)

            # Format power metrics
            avg_watts = interval.get("average_watts", 0)
            max_watts = interval.get("max_watts", 0)
            avg_watts_kg = interval.get("average_watts_kg", 0)
            max_watts_kg = interval.get("max_watts_kg", 0)
            w_avg = interval.get("weighted_average_watts", 0)
            intensity = interval.get("intensity", 0)
            training_load = interval.get("training_load", 0)

            # Format heart rate metrics
            avg_hr = interval.get("average_heartrate", 0)
            max_hr = interval.get("max_heartrate", 0)

            # Format cadence metrics
            avg_cadence = interval.get("average_cadence", 0)
            max_cadence = interval.get("max_cadence", 0)

            # Format speed metrics
            avg_speed = interval.get("average_speed", 0)
            max_speed = interval.get("max_speed", 0)

            result += f"""[{i}] {label} ({interval_type})
Duration: {elapsed_time} seconds (moving: {moving_time} seconds)
Distance: {distance} meters
Start-End Indices: {interval.get("start_index", 0)}-{interval.get("end_index", 0)}

Power Metrics:
  Average Power: {avg_watts} watts ({avg_watts_kg} W/kg)
  Max Power: {max_watts} watts ({max_watts_kg} W/kg)
  Weighted Avg Power: {w_avg} watts
  Intensity: {intensity}
  Training Load: {training_load}
  Joules: {interval.get("joules", 0)}
  Joules > FTP: {interval.get("joules_above_ftp", 0)}
  Power Zone: {interval.get("zone", "N/A")} ({interval.get("zone_min_watts", 0)}-{interval.get("zone_max_watts", 0)} watts)
  W' Balance: Start {interval.get("wbal_start", 0)}, End {interval.get("wbal_end", 0)}
  L/R Balance: {interval.get("avg_lr_balance", 0)}
  Variability: {interval.get("w5s_variability", 0)}
  Torque: Avg {interval.get("average_torque", 0)}, Min {interval.get("min_torque", 0)}, Max {interval.get("max_torque", 0)}

Heart Rate & Metabolic:
  Heart Rate: Avg {avg_hr}, Min {interval.get("min_heartrate", 0)}, Max {max_hr} bpm
  Decoupling: {interval.get("decoupling", 0)}
  DFA α1: {interval.get("average_dfa_a1", 0)}
  Respiration: {interval.get("average_respiration", 0)} breaths/min
  EPOC: {interval.get("average_epoc", 0)}
  SmO2: {interval.get("average_smo2", 0)}% / {interval.get("average_smo2_2", 0)}%
  THb: {interval.get("average_thb", 0)} / {interval.get("average_thb_2", 0)}

Speed & Cadence:
  Speed: Avg {avg_speed}, Min {interval.get("min_speed", 0)}, Max {max_speed} m/s
  GAP: {interval.get("gap", 0)} m/s
  Cadence: Avg {avg_cadence}, Min {interval.get("min_cadence", 0)}, Max {max_cadence} rpm
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
            group_id = group.get("id", f"Group {i}")

            # Format basic group information
            moving_time = group.get("moving_time", 0)
            elapsed_time = group.get("elapsed_time", 0)
            distance = group.get("distance", 0)
            count = group.get("count", 0)

            # Format power metrics
            avg_watts = group.get("average_watts", 0)
            max_watts = group.get("max_watts", 0)
            avg_watts_kg = group.get("average_watts_kg", 0)
            max_watts_kg = group.get("max_watts_kg", 0)
            w_avg = group.get("weighted_average_watts", 0)
            intensity = group.get("intensity", 0)

            result += f"""Group: {group_id} (Contains {count} intervals)
Duration: {elapsed_time} seconds (moving: {moving_time} seconds)
Distance: {distance} meters
Start-End Indices: {group.get("start_index", 0)}-N/A

Power: Avg {avg_watts} watts ({avg_watts_kg} W/kg), Max {max_watts} watts
W. Avg Power: {w_avg} watts, Intensity: {intensity}
Heart Rate: Avg {group.get("average_heartrate", 0)}, Max {group.get("max_heartrate", 0)} bpm
Speed: Avg {group.get("average_speed", 0)}, Max {group.get("max_speed", 0)} m/s
Cadence: Avg {group.get("average_cadence", 0)}, Max {group.get("max_cadence", 0)} rpm

"""

    return result
