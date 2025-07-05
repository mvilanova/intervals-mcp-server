"""
Formatting utilities for Intervals.icu MCP Server

This module contains formatting functions for handling data from the Intervals.icu API.
"""

from datetime import datetime
from typing import Any, List


class Section:
    """Context manager for conditionally adding sections to output.
    
    Only adds the heading if any lines are actually written.
    Lines are only written if the value is not None.
    """
    
    def __init__(self, 
                 lines: List[str] | None = None,
                 parent: Any | None=None,
                 heading: str = None,
                 indent: int | str = "",
                 data: dict[str, Any]=None):
        self.heading_lines = []
        self.lines = lines
        self.data = self.process_data(data)
        self.parent = parent

        parent_indent = self.parent.indent if self.parent is not None else ""

        self.indent = indent
        if isinstance(indent, int):
            self.indent = " " * indent
        self.indent = parent_indent + self.indent

        if lines is None:
            self.lines = []
        
        if len(self.lines) > 0:
            self.heading_lines.append("")
        if heading is not None:
            self.heading_lines.append(parent_indent + heading)

    def process_data(self, data: dict[str, Any] | None):
        """Process data, make a copy without None values."""
        if data is None:
            return {}
        return {k: v for k, v in data.items() if v is not None}

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.parent is not None:
            if len(self.parent.lines) > 0:
                self.parent.append("")
            self.parent.append_lines(self.lines)

    def append_lines(self, lines: List[str]):
        if len(lines) > 0:
            if len(self.heading_lines) > 0:
                self.lines.extend(self.heading_lines)
                self.heading_lines = []
            self.lines.extend(lines)
            
    def append(self, fmt_str: str, value_key: List[str] | str = None, value: Any=None, data: dict[str, Any]=None, none_val: Any=None, defaults: dict[str, Any] | None=None, **kwargs):
        """Append a formatted line if value is not None."""

        if defaults is None:
            defaults = {}
        data = {**self.data, **self.process_data(data), **kwargs}
        if isinstance(value_key, str):
            value_key = [value_key]
        if value_key is not None:
            for key in value_key:
                v = data.get(key)
                if v is not None:
                    kwargs["value"] = v
                    break

        if value is not None:
            kwargs["value"] = value

        if none_val is not None and kwargs.get("value") is None:
            kwargs["value"] = none_val

        line = None
        args = []
        if kwargs.get("value") is not None:
            args.append(kwargs["value"])

        while True:
            try:
                line = fmt_str.format(*args, **{**defaults, **data})
            except KeyError as e:
                if none_val is not None and e.args[0] not in data:
                    data[e.args[0]] = none_val
                    continue
                else:
                    return
            except IndexError as e:
                if none_val is not None and len(args) == 0:
                    args.append(none_val)
                    continue
                else:
                    return
            break

        if line is not None:
            if len(self.heading_lines) > 0:
                self.lines.extend(self.heading_lines)
                self.heading_lines = []
            self.lines.append(self.indent + line)


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

    lines = []
    main_section = Section(lines, data=activity)
    main_section.append("Activity: {name}")
    main_section.append("ID: {id}")
    main_section.append("Type: {type}")
    main_section.append("Date: {}", value=start_time)
    main_section.append("Description: {description}")
    main_section.append("Distance: {distance} meters")
    main_section.append("Duration: {duration} seconds")
    main_section.append("Moving Time: {moving_time} seconds")
    main_section.append("Elevation Gain: {elevation_gain} meters")
    main_section.append("Elevation Loss: {elevation_loss} meters")

    with Section(lines, data=activity, heading="Power Data:", indent='- ') as power_section:
        power_section.append("Average Power: {avg_power} W")
        power_section.append("Weighted Avg Power: {weighted_avg_power} W")
        power_section.append("Training Load: {training_load}")
        power_section.append("FTP: {ftp} W")
        power_section.append("Kilojoules: {kilojoules}")
        power_section.append("Intensity: {intensity}")
        power_section.append("Power:HR Ratio: {power_hr_ratio}")
        power_section.append("Variability Index: {variability_index}")

    with Section(lines, data=activity, heading="Heart Rate Data:", indent='- ') as hr_section:
        hr_section.append("Average Heart Rate: {avg_hr} bpm")
        hr_section.append("Max Heart Rate: {max_hr} bpm")
        hr_section.append("LTHR: {lthr} bpm")
        hr_section.append("Resting HR: {resting_hr} bpm")
        hr_section.append("Decoupling: {decoupling}")

    with Section(lines, data=activity, heading="Other Metrics:", indent='- ') as other_section:
        other_section.append("Cadence: {cadence} rpm")
        other_section.append("Calories: {calories}")
        other_section.append("Average Speed: {average_speed} m/s")
        other_section.append("Max Speed: {max_speed} m/s")
        other_section.append("Average Stride: {average_stride} m")
        other_section.append("L/R Balance: {avg_lr_balance}")
        other_section.append("Weight: {weight} kg")
        other_section.append("RPE: {value}/10", value_key=["perceived_exertion", "icu_rpe"])
        other_section.append("Session RPE: {session_rpe}")
        other_section.append("Feel: {feel}/5")

    with Section(lines, data=activity, heading="Environment:", indent='- ') as environment_section:
        environment_section.append("Trainer: {trainer}")
        environment_section.append("Average Temp: {average_temp}°C")
        environment_section.append("Min Temp: {min_temp}°C")
        environment_section.append("Max Temp: {max_temp}°C")
        environment_section.append("Avg Wind Speed: {average_wind_speed} km/h")
        environment_section.append("Headwind %: {headwind_percent}%")
        environment_section.append("Tailwind %: {tailwind_percent}%")

    with Section(lines, data=activity, heading="Training Metrics:", indent='- ') as training_metrics_section:
        training_metrics_section.append("Fitness (CTL): {ctl}")
        training_metrics_section.append("Fatigue (ATL): {atl}")
        training_metrics_section.append("TRIMP: {trimp}")
        training_metrics_section.append("Polarization Index: {polarization_index}")
        training_metrics_section.append("Power Load: {power_load}")
        training_metrics_section.append("HR Load: {hr_load}")
        training_metrics_section.append("Pace Load: {pace_load}")
        training_metrics_section.append("Efficiency Factor: {efficiency_factor}")

    with Section(lines, data=activity, heading="Device Info:", indent='- ') as device_section:
        device_section.append("Device: {device_name}")
        device_section.append("Power Meter: {power_meter}")
        device_section.append("File Type: {file_type}")
    return "\n".join(lines)


def format_workout(workout: dict[str, Any]) -> str:
    """Format a workout into a readable string."""
    lines = []
    main_section = Section(lines, data=workout)
    main_section.append("Workout: {name}")
    main_section.append("Description: {description}")
    main_section.append("Sport: {sport}")
    main_section.append("Duration: {duration} seconds", none_val=0)
    main_section.append("TSS: {tss}")
    main_section.append("Intervals: {}", value=len(workout.get("intervals", [])))
    return "\n".join(lines)

def format_wellness_entry(entries: dict[str, Any]) -> str:
    lines = []
    main_section = Section(lines, data=entries, heading="Wellness Data:")
    main_section.append("Date: {id}")

    with Section(lines, data=entries, heading="Training Metrics:", indent='- ') as metrics_section:
        metrics_section.append("Fitness (CTL): {ctl}")
        metrics_section.append("Fatigue (ATL): {atl}")
        metrics_section.append("Ramp Rate: {rampRate}")
        metrics_section.append("CTL Load: {ctlLoad}")
        metrics_section.append("ATL Load: {atlLoad}")

    with Section(lines, data=entries, heading="Sport-Specific Info:", indent='- ') as sport_section:
        if entries.get("sportInfo"):
            for sport in entries.get("sportInfo", []):
                if isinstance(sport, dict):
                    sport_section.append("{type}: eFTP = {eftp:.0f} W", data=sport)

    with Section(lines, data=entries, heading="Vital Signs:", indent='- ') as vital_section:
        vital_section.append("Weight: {weight} kg")
        vital_section.append("Resting HR: {restingHR} bpm")
        vital_section.append("HRV: {hrv}")
        vital_section.append("HRV SDNN: {hrvSDNN}")
        vital_section.append("Average Sleeping HR: {avgSleepingHR} bpm")
        vital_section.append("SpO2: {spO2}%")
        vital_section.append("Blood Pressure: {systolic}/{diastolic} mmHg")
        vital_section.append("Respiration: {respiration} breaths/min")
        vital_section.append("Blood Glucose: {bloodGlucose} mmol/L")
        vital_section.append("Lactate: {lactate} mmol/L")
        vital_section.append("VO2 Max: {vo2max} ml/kg/min")
        vital_section.append("Body Fat: {bodyFat}%")
        vital_section.append("Abdomen: {abdomen} cm")
        vital_section.append("Baevsky Stress Index: {baevskySI}")

    with Section(lines, data=entries, heading="Sleep & Recovery:", indent='- ') as sleep_section:
        if entries.get("sleepSecs") is not None:
            entries['sleepHours'] = entries['sleepSecs'] / 3600
        sleep_section.append("Sleep: {sleepHours} hours")
        sleep_section.append("Sleep Score: {sleepScore}")
        sleep_section.append("Sleep Quality: {sleepQuality}/4")
        sleep_section.append("Readiness: {readiness}")

    # Menstrual Tracking
    with Section(lines, data=entries, heading="Menstrual Tracking:", indent='- ') as menstrual_section:
        menstrual_section.append("Menstrual Phase: {menstrualPhase}")
        menstrual_section.append("Predicted Phase: {menstrualPhasePredicted}")

    # Subjective Feelings
    with Section(lines, data=entries, heading="Subjective Feelings:", indent='- ') as subjective_section:
        subjective_section.append("Soreness: {soreness}/14")
        subjective_section.append("Fatigue: {fatigue}/4")
        subjective_section.append("Stress: {stress}/4")
        subjective_section.append("Mood: {mood}/4")
        subjective_section.append("Motivation: {motivation}/4")
        subjective_section.append("Injury: {injury}/4")

    # Nutrition & Hydration
    with Section(lines, data=entries, heading="Nutrition & Hydration:", indent='- ') as nutrition_section:
        nutrition_section.append("Calories Consumed: {kcalConsumed} kcal")
        nutrition_section.append("Hydration Volume: {hydrationVolume} ml")
        nutrition_section.append("Hydration Score: {hydration}/4")

    # Activity
    with Section(lines, data=entries, heading="Activity:", indent='- ') as activity_section:
        activity_section.append("Steps: {steps}")

    # Comments, Status, Updated
    with Section(lines, data=entries) as comments_section:
        comments_section.append("Comments: {comments}")
        comments_section.append("Status: {}", value='Locked' if entries.get('locked', False) else 'Unlocked')

    return "\n".join(lines)


def format_event_summary(event: dict[str, Any]) -> str:
    """Format a basic event summary into a readable string."""

    lines = []
    with Section(lines, data=event) as main_section:
        main_section.append("Date: {}", value_key=["start_date_local", "date"])
        main_section.append("ID: {id}")
        main_section.append("Type: {type}", type="Workout" if event.get("workout") else "Race" if event.get("race") else "Other")
        main_section.append("Name: {name}")
        main_section.append("Description: \n{description}")
        main_section.lines[-1] = main_section.lines[-1].strip()
    return "\n".join(lines)


def format_event_details(event: dict[str, Any]) -> str:
    """Format detailed event information into a readable string."""

    lines = []
    with Section(lines, data=event, heading="Event Details:") as main_section:
        main_section.append("")
        main_section.append("ID: {id}")
        main_section.append("Date: {date}")
        main_section.append("Name: {name}")
        main_section.append("Description: \n{description}")
        main_section.lines[-1] = main_section.lines[-1].strip()

    if workout := event.get("workout"):
        with Section(lines, data=workout, heading="Workout Information:") as workout_section:
            workout_section.append("Workout ID: {id}")
            workout_section.append("Sport: {sport}")
            workout_section.append("Duration: {duration} seconds")
            workout_section.append("TSS: {tss}")
            if intervals := workout.get("intervals"):
                workout_section.append("Intervals: {}", value=len(intervals))

    if event.get("race"):
        with Section(lines, data=event, heading="Race Information:") as race_section:
            race_section.append("Priority: {priority}")
            race_section.append("Result: {result}")

    if calendar := event.get("calendar"):
        with Section(lines, data=calendar, heading="Calendar Information:") as calendar_section:
            calendar_section.append("Calendar: {name}")

    return "\n".join(lines)


def format_intervals(intervals_data: dict[str, Any]) -> str:
    """Format intervals data into a readable string with all available fields.

    Args:
        intervals_data: The intervals data from the Intervals.icu API

    Returns:
        A formatted string representation of the intervals data
    """
    lines = []

    # Format basic intervals information
    main_section = Section(lines, data=intervals_data, heading="Intervals Analysis:")
    main_section.append("ID: {id}")
    main_section.append("Analyzed: {analyzed}")

    # Format individual intervals
    if intervals := intervals_data.get("icu_intervals"):
        with Section(parent=main_section, heading="Individual Intervals:") as intervals_section:
            for i, interval in enumerate(intervals, 1):
                with Section(parent=intervals_section, data=interval, heading=f"[{i}] {interval.get("label", f"Interval {i}")} ({interval.get("type", "Unknown")})") as interval_section:
                    interval_section.append("Duration: {elapsed_time} seconds (moving: {moving_time} seconds)", none_val=0)
                    interval_section.append("Distance: {distance} meters")
                    interval_section.append("Start-End Indices: {start_index}-{end_index}")

                    with Section(parent=interval_section, data=interval, heading="Power Metrics:") as power_section:
                        power_section.append("Average Power: {average_watts} watts ({average_watts_kg} W/kg)", defaults={"average_watts_kg": 0})
                        power_section.append("Max Power: {max_watts} watts ({max_watts_kg} W/kg)", defaults={"max_watts_kg": 0})
                        power_section.append("Weighted Avg Power: {weighted_average_watts} watts")
                        power_section.append("Intensity: {intensity}")
                        power_section.append("Training Load: {training_load}")
                        power_section.append("Joules: {joules}")
                        power_section.append("Joules > FTP: {joules_above_ftp}")
                        power_section.append("Power Zone: {zone} ({zone_min_watts}-{zone_max_watts} watts)")
                        power_section.append("W' Balance: Start {wbal_start}, End {wbal_end}")
                        power_section.append("L/R Balance: {avg_lr_balance}")
                        power_section.append("Variability: {w5s_variability}")
                        power_section.append("Torque: Avg {average_torque}, Min {min_torque}, Max {max_torque}")

                    with Section(parent=interval_section, data=interval, heading="Heart Rate & Metabolic:") as heart_rate_section:
                        heart_rate_section.append("Heart Rate: Avg {average_heartrate}, Min {min_heartrate}, Max {max_heartrate} bpm")
                        heart_rate_section.append("Decoupling: {decoupling}")
                        heart_rate_section.append("DFA α1: {average_dfa_a1}")
                        heart_rate_section.append("Respiration: {average_respiration} breaths/min")
                        heart_rate_section.append("EPOC: {average_epoc}")
                        heart_rate_section.append("SmO2: {average_smo2}% / {average_smo2_2}%")
                        heart_rate_section.append("THb: {average_thb}% / {average_thb_2}%")

                    with Section(parent=interval_section, data=interval, heading="Speed & Cadence:") as speed_section:
                        speed_section.append("Speed: Avg {average_speed}, Min {min_speed}, Max {max_speed} m/s")
                        speed_section.append("GAP: {gap} m/s")
                        speed_section.append("Cadence: Avg {average_cadence}, Min {min_cadence}, Max {max_cadence} rpm")
                        speed_section.append("Stride: {average_stride}")

                    with Section(parent=interval_section, data=interval, heading="Elevation & Environment:") as elevation_section:
                        elevation_section.append("Elevation Gain: {total_elevation_gain} meters")
                        elevation_section.append("Altitude: Min {min_altitude}, Max {max_altitude} meters")
                        elevation_section.append("Gradient: {average_gradient}%")
                        elevation_section.append("Temperature: {average_temp}°C (Weather: {average_weather_temp}°C, Feels like: {average_feels_like}°C)")
                        elevation_section.append("Wind: Speed {average_wind_speed} km/h, Gust {average_wind_gust} km/h, Direction {prevailing_wind_deg}°")
                        elevation_section.append("Headwind: {headwind_percent}%, Tailwind: {tailwind_percent}%")

    if icu_groups := intervals_data.get("icu_groups"):
        with Section(parent=main_section, heading="Interval Groups:") as groups_section:
            for i, group in enumerate(icu_groups, 1):
                with Section(parent=groups_section, data=group, heading=f"Group {i}") as group_section:
                    group_section.append("[{i}] {label} ({type})", defaults={"label": f"Group {i}", "type": "Unknown"}, i=i)
                    group_section.append("Duration: {elapsed_time} seconds (moving: {moving_time} seconds)", none_val=0)
                    group_section.append("Distance: {distance} meters")
                    group_section.append("Start-End Indices: {start_index}-{end_index}", none_val=0)

                    group_section.append("Power: Avg {average_watts} watts ({average_watts_kg} W/kg), Max {max_watts} watts ({max_watts_kg} W/kg)", defaults={"average_watts_kg": 0, "max_watts_kg": 0})
                    group_section.append("W. Avg Power: {weighted_average_watts} watts, Intensity: {intensity}")
                    group_section.append("Heart Rate: Avg {average_heartrate}, Max {max_heartrate} bpm")
                    group_section.append("Speed: Avg {average_speed}, Max {max_speed} m/s")
                    group_section.append("Cadence: Avg {average_cadence}, Max {max_cadence} rpm")

    return "\n".join(lines)
