"""
Deterministic training metrics for the coach report.

This module is pure: no network access, no clock, no logging. The MCP tool in
``tools/coach_report.py`` fetches raw Intervals.icu data and passes it in together
with an explicit end date. Every number an LLM coach needs is computed here so the
model only has to interpret, not calculate.

All thresholds and mappings live in :class:`CoachConfig`.
"""

# pylint: disable=too-many-lines

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

SCHEMA_VERSION = "1.1"

Activity = dict[str, Any]
WellnessRecord = dict[str, Any]

RAD = "Rad"
LAUF = "Lauf"
SCHWIMMEN = "Schwimmen"
KRAFT = "Kraft"
SONSTIGE = "Sonstige"

# Intervals.icu activity type -> sport family used throughout the report.
SPORT_FAMILIES: dict[str, str] = {
    "Ride": RAD,
    "VirtualRide": RAD,
    "GravelRide": RAD,
    "MountainBikeRide": RAD,
    "EBikeRide": RAD,
    "Run": LAUF,
    "TrailRun": LAUF,
    "VirtualRun": LAUF,
    "Swim": SCHWIMMEN,
    "OpenWaterSwim": SCHWIMMEN,
    "WeightTraining": KRAFT,
}

# Calendar event categories used by the plan section.
WORKOUT = "WORKOUT"
RACE_CATEGORIES: tuple[str, ...] = ("RACE_A", "RACE_B", "RACE_C")


@dataclass(frozen=True)
class CoachConfig:  # pylint: disable=too-many-instance-attributes
    """Central place for every threshold, window and mapping used by the report."""

    # Fixed analysis windows (days, inclusive of the end date).
    acute_days: int = 7
    chronic_days: int = 28
    baseline_days: int = 60

    # Load
    acwr_low_warn: float = 0.8
    acwr_high_warn: float = 1.3
    acwr_low_alarm: float = 0.75
    acwr_high_alarm: float = 1.35
    monotony_warn: float = 2.0
    monotony_alarm: float = 2.5
    primary_sport_min_active_days: int = 3
    deload_ratio: float = 0.8
    week_monotony_min_days: int = 5
    week_monotony_min_active_days: int = 3

    # Thresholds and data quality
    ftp_eftp_max_dev_pct: float = 2.0
    sport_inactive_days: int = 7
    tracked_sports: tuple[str, ...] = (RAD, LAUF, SCHWIMMEN, KRAFT)
    subjective_missing_share: float = 0.8

    # Recovery
    hrv_valid_min: float = 10.0
    hrv_valid_max: float = 250.0
    hrv_band_k: float = 0.5
    hrv_min_points_acute: int = 4
    hrv_min_points_baseline: int = 21
    hrv_alarm_days: int = 3
    rhr_high_delta_bpm: float = 5.0
    rhr_warn_days: int = 2
    rhr_alarm_days: int = 3
    rhr_min_points_acute: int = 4
    rhr_min_points_baseline: int = 21
    sleep_short_hours: float = 7.0
    sleep_recent_nights: int = 3
    sleep_short_min_nights: int = 2

    # Intensity: 7-zone -> 3-zone mapping per zone basis (index 0 = Z1 ... 6 = Z7).
    # Power (Coggan zones): Z4 = 91-105 % FTP spans LT2 and counts as high
    # (Treff et al. 2019 / Section 11). HR (LTHR-based zones): Z4 = 94-99 % LTHR is
    # still below LT2 and counts as moderate.
    power_zone_map: tuple[int, ...] = (1, 1, 2, 3, 3, 3, 3)
    hr_zone_map: tuple[int, ...] = (1, 1, 2, 2, 3, 3, 3)
    pi_z2_substitute: float = 0.01
    pi_z3_min: float = 0.01
    pi_polarized_min: float = 2.0
    # Hard-day ladders: (lowest zone, minimum seconds at or above that zone).
    # Power per Seiler/Foster, but with 60 instead of 30 min for Z3+: on hilly
    # endurance rides 30 min of incidental tempo is common and should not make the
    # day hard. HR is coarser and lags, so only sustained work above LT2 counts
    # (Section 11).
    hard_day_power_ladder: tuple[tuple[int, int], ...] = (
        (3, 3600),
        (4, 600),
        (5, 300),
        (6, 120),
        (7, 60),
    )
    hard_day_hr_ladder: tuple[tuple[int, int], ...] = ((4, 600), (5, 300))

    # Durability (aerobic decoupling) quality filter. VI and pause limits are set
    # for hilly outdoor riding (typical VI 1.1-1.3, cafe stops); stricter values
    # (VI 1.10, 0.9) excluded every ride of the reference athlete.
    durability_ride_types: tuple[str, ...] = ("Ride", "VirtualRide")
    durability_run_types: tuple[str, ...] = ("Run",)
    durability_min_moving_s: int = 3600
    durability_max_vi: float = 1.20
    durability_min_moving_ratio: float = 0.85
    durability_max_temp_c: float = 25.0
    durability_high_drift_pct: float = 5.0
    durability_high_drift_count_7d: int = 3
    durability_trend_band_pct: float = 1.0
    durability_min_sessions_trend: int = 2

    # Efficiency factor (NP / avg HR) of reasonably steady rides; VI 1.05 (Section 11)
    # leaves no outdoor ride in hilly terrain, so the durability VI limit is used.
    ef_types: tuple[str, ...] = ("Ride", "VirtualRide", "GravelRide", "MountainBikeRide")
    ef_max_vi: float = 1.20
    ef_min_moving_s: int = 1200
    ef_min_sessions: int = 2
    ef_trend_band: float = 0.03

    # eFTP trend from wellness.sportInfo
    eftp_lookback_days: tuple[int, ...] = (28, 56)
    eftp_tolerance_days: int = 3

    # Top sessions
    top_n: int = 5

    # Plan (projection mode): coach rule ramp <= 6 CTL per week
    ramp_planned_warn: float = 6.0
    tsb_planned_warn: float = -20.0
    tsb_planned_alarm: float = -30.0
    planned_min_rest_days: int = 1
    race_lookahead_days: int = 84


DEFAULT_CONFIG = CoachConfig()


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _num(value: Any) -> float | None:
    """Return ``value`` as float if it is a finite number, else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _r(value: float | None, digits: int = 1) -> float | int | None:
    """Round for output; 0 digits yields an int, None stays None."""
    if value is None or not math.isfinite(value):
        return None
    if digits == 0:
        return int(round(value))
    return round(value, digits) + 0.0  # + 0.0 turns -0.0 into 0.0


def parse_day(value: Any) -> date | None:
    """Parse the date part of an ISO date/datetime string."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def days_back(end: date, count: int) -> list[date]:
    """Return ``count`` consecutive days ending at ``end`` (oldest first)."""
    return [end - timedelta(days=offset) for offset in range(count - 1, -1, -1)]


def sport_family(activity_type: Any) -> str:
    """Map an Intervals.icu activity type to a report sport family."""
    if not isinstance(activity_type, str):
        return SONSTIGE
    return SPORT_FAMILIES.get(activity_type, SONSTIGE)


def activity_day(activity: Activity) -> date | None:
    """Local calendar day of an activity."""
    return parse_day(activity.get("start_date_local"))


def activity_load(activity: Activity) -> float:
    """Training load of an activity; missing or negative loads count as 0."""
    load = _num(activity.get("icu_training_load"))
    return max(load, 0.0) if load is not None else 0.0


def activities_between(activities: list[Activity], start: date, end: date) -> list[Activity]:
    """Activities whose local day lies within [start, end]."""
    selected = []
    for activity in activities:
        day = activity_day(activity)
        if day is not None and start <= day <= end:
            selected.append(activity)
    return selected


def daily_loads(
    activities: list[Activity], end: date, count: int, family: str | None = None
) -> list[float]:
    """Daily training load for ``count`` days ending at ``end``, zero-filled."""
    per_day: dict[date, float] = defaultdict(float)
    for activity in activities:
        if family is not None and sport_family(activity.get("type")) != family:
            continue
        day = activity_day(activity)
        if day is not None:
            per_day[day] += activity_load(activity)
    return [per_day.get(day, 0.0) for day in days_back(end, count)]


def monotony(daily: list[float]) -> float | None:
    """Foster monotony: mean / sample SD of daily load (0-days included).

    Returns None when fewer than two days are given or the SD is 0 (every day
    identical, including a period without any training), because the ratio is
    undefined there.
    """
    if len(daily) < 2:
        return None
    sd = statistics.stdev(daily)
    if sd == 0:
        return None
    return statistics.mean(daily) / sd


def wellness_by_day(wellness: Any) -> dict[date, WellnessRecord]:
    """Index wellness records (list or date-keyed dict from the API) by day."""
    records: list[tuple[Any, Any]] = []
    if isinstance(wellness, dict):
        records = list(wellness.items())
    elif isinstance(wellness, list):
        records = [(item.get("id") if isinstance(item, dict) else None, item) for item in wellness]
    indexed: dict[date, WellnessRecord] = {}
    for key, record in records:
        if not isinstance(record, dict):
            continue
        day = parse_day(record.get("id")) or parse_day(key)
        if day is not None:
            indexed[day] = record
    return indexed


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_metrics(  # pylint: disable=too-many-locals
    activities: list[Activity], end: date, config: CoachConfig = DEFAULT_CONFIG
) -> dict[str, Any]:
    """Acute/chronic load, ACWR, Foster monotony and strain, primary-sport monotony, deload.

    * ACWR = load of the last 7 days / (load of the last 28 days / 4); None if the
      28-day load is 0.
    * Monotony over the last 7 daily loads including rest days (None if undefined,
      see :func:`monotony`); strain = 7-day load x monotony.
    * Primary sport = sport family with the highest 7-day load. Its own monotony is
      only computed with at least ``primary_sport_min_active_days`` active days.
      With more than one sport family, ``effective_monotony`` uses the primary
      sport value, because a steady cross-training floor (e.g. strength) inflates
      total monotony without adding overuse risk (Section 11 approach).
    * Deload: 7-day load <= ``deload_ratio`` x 28-day weekly average.
    """
    acute = daily_loads(activities, end, config.acute_days)
    chronic = daily_loads(activities, end, config.chronic_days)
    load_acute = sum(acute)
    load_chronic = sum(chronic)
    weeks_chronic = config.chronic_days / 7

    acwr = load_acute / (load_chronic / weeks_chronic) if load_chronic > 0 else None
    total_monotony = monotony(acute)
    monotony_note = None
    if total_monotony is None:
        monotony_note = "no_load" if load_acute == 0 else "no_variation"
    strain = load_acute * total_monotony if total_monotony is not None else None

    acute_start = end - timedelta(days=config.acute_days - 1)
    families = sorted(
        {
            sport_family(a.get("type"))
            for a in activities_between(activities, acute_start, end)
            if activity_load(a) > 0
        }
    )
    family_loads = {
        family: daily_loads(activities, end, config.acute_days, family) for family in families
    }
    primary = None
    primary_monotony = None
    if family_loads:
        primary = max(families, key=lambda family: sum(family_loads[family]))
        active_days = sum(1 for load in family_loads[primary] if load > 0)
        if active_days >= config.primary_sport_min_active_days:
            primary_monotony = monotony(family_loads[primary])
    multi_sport = len(family_loads) > 1
    effective = (
        primary_monotony if multi_sport and primary_monotony is not None else total_monotony
    )

    deload = load_chronic > 0 and load_acute <= config.deload_ratio * load_chronic / weeks_chronic

    return {
        "load_7d": _r(load_acute, 0),
        "load_28d": _r(load_chronic, 0),
        "acwr": _r(acwr, 2),
        "monotony": _r(total_monotony, 2),
        "monotony_note": monotony_note,
        "strain": _r(strain, 0),
        "primary_sport": primary,
        "primary_monotony": _r(primary_monotony, 2),
        "effective_monotony": _r(effective, 2),
        "deload": deload,
    }


def fitness_status(  # pylint: disable=too-many-locals
    wellness: dict[date, WellnessRecord],
    activities: list[Activity],
    end: date,
    today: date | None = None,
) -> dict[str, Any]:
    """CTL, ATL, TSB (= CTL - ATL) and ramp rate at the end date.

    Uses the Intervals.icu values of the end date, or the last earlier day that has
    them (reported as ``as_of``). A value after ``today`` is the Intervals.icu
    projection, which includes planned workouts; it is returned unchanged with
    ``src`` = ``api_incl_planned``. Otherwise, if the end date's ``ctlLoad`` is
    higher than the load actually completed that day, Intervals.icu has counted
    planned but not yet done workouts. CTL/ATL are then recomputed from the
    previous (completed) day with the Intervals.icu exponential model (time
    constants 42 and 7 days) and only the completed load; ramp rate becomes
    CTL(end) - CTL(end - 7 days).
    """
    record_day = None
    for day in days_back(end, 8)[::-1]:
        record = wellness.get(day, {})
        if _num(record.get("ctl")) is not None and _num(record.get("atl")) is not None:
            record_day = day
            break
    if record_day is None:
        return {"ctl": None, "atl": None, "tsb": None, "ramp": None, "src": None}

    record = wellness[record_day]
    ctl = _num(record.get("ctl"))
    atl = _num(record.get("atl"))
    ramp = _num(record.get("rampRate"))
    source = "api"

    if today is not None and record_day > today:
        source = "api_incl_planned"
    elif record_day == end:
        planned_load = _num(record.get("ctlLoad"))
        done_load = daily_loads(activities, end, 1)[0]
        previous = wellness.get(end - timedelta(days=1), {})
        prev_ctl = _num(previous.get("ctl"))
        prev_atl = _num(previous.get("atl"))
        if (
            planned_load is not None
            and planned_load > done_load + 1
            and prev_ctl is not None
            and prev_atl is not None
        ):
            ctl = prev_ctl + (done_load - prev_ctl) * (1 - math.exp(-1 / 42))
            atl = prev_atl + (done_load - prev_atl) * (1 - math.exp(-1 / 7))
            week_ago_ctl = _num(wellness.get(end - timedelta(days=7), {}).get("ctl"))
            ramp = ctl - week_ago_ctl if week_ago_ctl is not None else None
            source = "recomputed_without_planned"

    if ctl is None or atl is None:  # unreachable: the search above requires both
        return {"ctl": None, "atl": None, "tsb": None, "ramp": None, "src": None}
    result: dict[str, Any] = {
        "ctl": _r(ctl, 1),
        "atl": _r(atl, 1),
        "tsb": _r(ctl - atl, 1),
        "ramp": _r(ramp, 1),
        "src": source,
    }
    if record_day != end:
        result["as_of"] = record_day.isoformat()
    return result


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------


def iso_week_label(day: date) -> str:
    """ISO week label such as ``2026-W53`` (ISO year, not calendar year)."""
    iso = day.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def weekly_volume(  # pylint: disable=too-many-locals
    activities: list[Activity], end: date, days: int, config: CoachConfig = DEFAULT_CONFIG
) -> list[dict[str, Any]]:
    """Per ISO week (Mon-Sun) and sport family: hours, load, sessions, km.

    Only days inside the report window count, so the first/last week can be partial
    (``days`` < 7). Also returns rest days (daily load 0), hard days (see
    :func:`is_hard_day`) and the week's Foster monotony, which is only reported for
    weeks with enough days and active days (short weeks produce meaningless values).
    """
    window = days_back(end, days)
    by_day: dict[date, list[Activity]] = defaultdict(list)
    for activity in activities_between(activities, window[0], end):
        day = activity_day(activity)
        if day is not None:
            by_day[day].append(activity)

    weeks: dict[str, list[date]] = {}
    for day in window:
        weeks.setdefault(iso_week_label(day), []).append(day)

    rows = []
    for label, week_days in weeks.items():
        sports: dict[str, dict[str, float]] = defaultdict(
            lambda: {"secs": 0.0, "load": 0.0, "n": 0.0, "meters": 0.0}
        )
        daily = []
        hard_days = 0
        for day in week_days:
            if is_hard_day(by_day.get(day, []), config):
                hard_days += 1
            day_load = 0.0
            for activity in by_day.get(day, []):
                totals = sports[sport_family(activity.get("type"))]
                totals["secs"] += _num(activity.get("moving_time")) or 0.0
                totals["load"] += activity_load(activity)
                totals["n"] += 1
                totals["meters"] += _num(activity.get("distance")) or 0.0
                day_load += activity_load(activity)
            daily.append(day_load)

        active_days = sum(1 for load in daily if load > 0)
        week_monotony = None
        if (
            len(daily) >= config.week_monotony_min_days
            and active_days >= config.week_monotony_min_active_days
        ):
            week_monotony = monotony(daily)

        sport_rows: dict[str, dict[str, Any]] = {}
        for family in sorted(sports):
            totals = sports[family]
            row: dict[str, Any] = {
                "h": _r(totals["secs"] / 3600, 1),
                "load": _r(totals["load"], 0),
                "n": int(totals["n"]),
            }
            if totals["meters"] > 0:
                row["km"] = _r(totals["meters"] / 1000, 1)
            sport_rows[family] = row

        rows.append(
            {
                "week": label,
                "days": len(week_days),
                "sports": sport_rows,
                "total": {
                    "h": _r(sum(t["secs"] for t in sports.values()) / 3600, 1),
                    "load": _r(sum(daily), 0),
                    "n": int(sum(t["n"] for t in sports.values())),
                },
                "rest_days": sum(1 for load in daily if load == 0),
                "hard_days": hard_days,
                "monotony": _r(week_monotony, 2),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


def _valid_hrv(record: WellnessRecord, config: CoachConfig) -> float | None:
    """rMSSD if it lies in the plausible range, else None (sensor errors)."""
    value = _num(record.get("hrv"))
    if value is None or not config.hrv_valid_min <= value <= config.hrv_valid_max:
        return None
    return value


def hrv_status(  # pylint: disable=too-many-locals
    wellness: dict[date, WellnessRecord], end: date, config: CoachConfig = DEFAULT_CONFIG
) -> dict[str, Any]:
    """HRV trend: 7-day mean of ln(rMSSD) vs. the baseline normal range.

    Baseline = all valid values in the ``baseline_days`` ending at ``end``; normal
    range = baseline mean +/- ``hrv_band_k`` x baseline SD. Status is
    ``below``/``within``/``above``, or ``insufficient_data`` when the 7-day window
    or the baseline has too few values. ``days_below`` counts consecutive days
    (backwards from ``end``) whose ln(rMSSD) is below the range; a day without a
    value ends the streak.
    """
    baseline_window = days_back(end, config.baseline_days)
    raw = {
        day: value
        for day in baseline_window
        if (value := _valid_hrv(wellness.get(day, {}), config)) is not None
    }
    ln_values = {day: math.log(value) for day, value in raw.items()}
    acute_window = baseline_window[-config.acute_days :]
    acute_ln = [ln_values[day] for day in acute_window if day in ln_values]
    baseline_ln = list(ln_values.values())

    counts = {"n_7d": len(acute_ln), "n_base": len(baseline_ln)}
    if (
        len(acute_ln) < config.hrv_min_points_acute
        or len(baseline_ln) < max(config.hrv_min_points_baseline, 2)
    ):
        return {"status": "insufficient_data", **counts}

    acute_mean = statistics.mean(acute_ln)
    baseline_mean = statistics.mean(baseline_ln)
    baseline_sd = statistics.stdev(baseline_ln)
    lower = baseline_mean - config.hrv_band_k * baseline_sd
    upper = baseline_mean + config.hrv_band_k * baseline_sd
    if acute_mean < lower:
        status = "below"
    elif acute_mean > upper:
        status = "above"
    else:
        status = "within"

    days_below = 0
    for day in reversed(baseline_window):
        if day in ln_values and ln_values[day] < lower:
            days_below += 1
        else:
            break

    return {
        "status": status,
        "ln_7d": _r(acute_mean, 2),
        "ln_base": _r(baseline_mean, 2),
        "band": [_r(lower, 2), _r(upper, 2)],
        "rmssd_7d": _r(statistics.mean(raw[day] for day in acute_window if day in raw), 0),
        "days_below": days_below,
        **counts,
    }


def rhr_status(
    wellness: dict[date, WellnessRecord], end: date, config: CoachConfig = DEFAULT_CONFIG
) -> dict[str, Any]:
    """Resting HR: 7-day mean vs. baseline mean (difference in bpm).

    ``days_high`` counts consecutive days (backwards from ``end``) with a resting
    HR at least ``rhr_high_delta_bpm`` above the baseline mean.
    """
    baseline_window = days_back(end, config.baseline_days)
    values = {}
    for day in baseline_window:
        value = _num(wellness.get(day, {}).get("restingHR"))
        if value is not None and value > 0:
            values[day] = value
    acute = [values[day] for day in baseline_window[-config.acute_days :] if day in values]
    counts = {"n_7d": len(acute), "n_base": len(values)}
    if len(acute) < config.rhr_min_points_acute or len(values) < config.rhr_min_points_baseline:
        return {"status": "insufficient_data", **counts}

    acute_mean = statistics.mean(acute)
    baseline_mean = statistics.mean(values.values())
    days_high = 0
    for day in reversed(baseline_window):
        if day in values and values[day] >= baseline_mean + config.rhr_high_delta_bpm:
            days_high += 1
        else:
            break
    return {
        "avg_7d": _r(acute_mean, 1),
        "avg_base": _r(baseline_mean, 1),
        "delta": _r(acute_mean - baseline_mean, 1),
        "days_high": days_high,
        **counts,
    }


def sleep_summary(
    wellness: dict[date, WellnessRecord],
    end: date,
    days: int,
    config: CoachConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Sleep over the report window: average, 7-day average, short nights, last nights.

    ``recent_h`` lists the last ``sleep_recent_nights`` nights oldest first, with
    None for nights without data.
    """
    hours = {}
    for day in days_back(end, max(days, config.acute_days)):
        secs = _num(wellness.get(day, {}).get("sleepSecs"))
        if secs is not None and secs > 0:
            hours[day] = secs / 3600
    window = [hours[day] for day in days_back(end, days) if day in hours]
    acute = [hours[day] for day in days_back(end, config.acute_days) if day in hours]
    return {
        "avg_h": _r(statistics.mean(window), 1) if window else None,
        "avg_7d_h": _r(statistics.mean(acute), 1) if acute else None,
        "nights_short": sum(1 for value in window if value < config.sleep_short_hours),
        "recent_h": [
            _r(hours[day], 1) if day in hours else None
            for day in days_back(end, config.sleep_recent_nights)
        ],
        "n": len(window),
    }


# ---------------------------------------------------------------------------
# Intensity distribution
# ---------------------------------------------------------------------------

ZONE_COUNT = 7


def _power_zone_secs(activity: Activity) -> list[float] | None:
    """Seconds in power zones Z1..Z7 from ``icu_zone_times``.

    Only the ids Z1..Z7 are used; the extra sweet-spot bucket (id ``SS``) overlaps
    Z3/Z4 and is ignored so time is not counted twice.
    """
    zones = activity.get("icu_zone_times")
    if not isinstance(zones, list):
        return None
    secs = [0.0] * ZONE_COUNT
    for zone in zones:
        if not isinstance(zone, dict) or not isinstance(zone.get("id"), str):
            continue
        zone_id = zone["id"].strip().upper()
        if len(zone_id) == 2 and zone_id[0] == "Z" and zone_id[1] in "1234567":
            secs[int(zone_id[1]) - 1] += max(_num(zone.get("secs")) or 0.0, 0.0)
    return secs if sum(secs) > 0 else None


def _hr_zone_secs(activity: Activity) -> list[float] | None:
    """Seconds in HR zones Z1..Z7 from the ``icu_hr_zone_times`` array (index = zone)."""
    zones = activity.get("icu_hr_zone_times")
    if not isinstance(zones, list):
        return None
    secs = [0.0] * ZONE_COUNT
    for index, value in enumerate(zones[:ZONE_COUNT]):
        secs[index] = max(_num(value) or 0.0, 0.0)
    return secs if sum(secs) > 0 else None


def activity_zones(activity: Activity) -> tuple[list[float] | None, str | None]:
    """Zone seconds (Z1..Z7) and their basis (``power`` or ``hr``) for one activity.

    Cycling uses power zones with HR as fallback; every other sport uses HR zones
    with power as fallback. Returns (None, None) without any zone data.
    """
    power = _power_zone_secs(activity)
    heart_rate = _hr_zone_secs(activity)
    candidates = [(power, "power"), (heart_rate, "hr")]
    if sport_family(activity.get("type")) != RAD:
        candidates.reverse()
    for secs, basis in candidates:
        if secs is not None:
            return secs, basis
    return None, None


def three_zone_seconds(
    secs: list[float], basis: str, config: CoachConfig = DEFAULT_CONFIG
) -> list[float]:
    """Collapse Z1..Z7 seconds into the 3-zone model with the basis-specific mapping."""
    mapping = config.power_zone_map if basis == "power" else config.hr_zone_map
    result = [0.0, 0.0, 0.0]
    for index, value in enumerate(secs):
        result[mapping[index] - 1] += value
    return result


def polarization_index(
    z1: float, z2: float, z3: float, config: CoachConfig = DEFAULT_CONFIG
) -> tuple[float | None, str | None]:
    """Polarization index after Treff et al. (2019), Front Physiol 10:707.

    PI = log10((Z1 / Z2) x Z3 x 100) with Z1..Z3 as fractions of total time.
    Edge cases (returned as a note):

    * no zone time at all -> (None, ``no_zone_data``)
    * Z3 < ``pi_z3_min`` (1 %) -> (None, ``z3_zero``): the logarithm is undefined
      for Z3 = 0 and such a distribution is by definition not polarized
    * Z1 = 0 -> (None, ``z1_zero``) for the same reason
    * Z2 = 0 -> Z2 is replaced by ``pi_z2_substitute`` (0.01) as proposed by Treff
      et al., note ``z2_substituted``

    The index is returned for any distribution where it is defined; whether the
    structure is actually polarized is decided in :func:`classify_tid`.
    """
    if z1 + z2 + z3 <= 0:
        return None, "no_zone_data"
    if z3 < config.pi_z3_min:
        return None, "z3_zero"
    if z1 <= 0:
        return None, "z1_zero"
    note = None
    if z2 <= 0:
        z2 = config.pi_z2_substitute
        note = "z2_substituted"
    return math.log10(z1 / z2 * z3 * 100), note


def classify_tid(
    z1: float, z2: float, z3: float, pi: float | None, config: CoachConfig = DEFAULT_CONFIG
) -> str:
    """Training intensity distribution class (Section 11 priority order).

    1. Base: Z3 below 1 % and Z1 largest
    2. Polarized: Z1 > Z3 > Z2 and PI > 2.0
    3. Pyramidal: Z1 > Z2 > Z3
    4. Threshold: Z2 largest
    5. HIT: Z3 largest
    Anything else (e.g. Z1 > Z3 > Z2 with PI <= 2.0) is reported as Pyramidal.
    """
    if z3 < config.pi_z3_min and z1 >= z2:
        return "Base"
    if z1 > z3 > z2 and pi is not None and pi > config.pi_polarized_min:
        return "Polarized"
    if z1 > z2 > z3:
        return "Pyramidal"
    if z2 >= z1 and z2 >= z3:
        return "Threshold"
    if z3 >= z1 and z3 >= z2:
        return "HIT"
    return "Pyramidal"


def intensity_distribution(  # pylint: disable=too-many-locals
    activities: list[Activity], config: CoachConfig = DEFAULT_CONFIG, family: str | None = None
) -> dict[str, Any]:
    """3-zone distribution, polarization index and TID class over the given activities.

    Power and HR zone times are mapped separately (each with its own mapping) and
    then summed; ``basis_pct`` shows how much of the time came from each basis.
    """
    totals = [0.0, 0.0, 0.0]
    by_basis = {"power": 0.0, "hr": 0.0}
    for activity in activities:
        if family is not None and sport_family(activity.get("type")) != family:
            continue
        secs, basis = activity_zones(activity)
        if secs is None or basis is None:
            continue
        collapsed = three_zone_seconds(secs, basis, config)
        for index in range(3):
            totals[index] += collapsed[index]
        by_basis[basis] += sum(collapsed)

    total = sum(totals)
    if total <= 0:
        return {"pct": None, "h": 0, "pi": None, "pi_note": "no_zone_data", "cls": None}
    z1, z2, z3 = (value / total for value in totals)
    pi, note = polarization_index(z1, z2, z3, config)
    result: dict[str, Any] = {
        "pct": [_r(z1 * 100, 1), _r(z2 * 100, 1), _r(z3 * 100, 1)],
        "h": _r(total / 3600, 1),
        "pi": _r(pi, 2),
        "cls": classify_tid(z1, z2, z3, pi, config),
        "basis_pct": {basis: _r(secs / total * 100, 0) for basis, secs in by_basis.items()},
    }
    if note is not None:
        result["pi_note"] = note
    return result


def tid_drift(
    activities: list[Activity], end: date, config: CoachConfig = DEFAULT_CONFIG
) -> dict[str, Any]:
    """Compare the 7-day with the 28-day distribution (all sports).

    ``acute_depolarization``: PI dropped below the polarized threshold in the last
    7 days while the 28-day PI is above it; ``shifting``: the class changed;
    ``consistent``: same class. None when either window lacks zone data.
    """
    acute = intensity_distribution(
        activities_between(activities, end - timedelta(days=config.acute_days - 1), end), config
    )
    chronic = intensity_distribution(
        activities_between(activities, end - timedelta(days=config.chronic_days - 1), end), config
    )
    cls_acute, cls_chronic = acute["cls"], chronic["cls"]
    pi_acute, pi_chronic = acute["pi"], chronic["pi"]
    drift = None
    if cls_acute is not None and cls_chronic is not None:
        if (
            pi_acute is not None
            and pi_chronic is not None
            and pi_acute < config.pi_polarized_min <= pi_chronic
        ):
            drift = "acute_depolarization"
        elif cls_acute != cls_chronic:
            drift = "shifting"
        else:
            drift = "consistent"
    return {
        "cls_7d": cls_acute,
        "cls_28d": cls_chronic,
        "pi_7d": pi_acute,
        "pi_28d": pi_chronic,
        "drift": drift,
    }


def is_hard_day(day_activities: list[Activity], config: CoachConfig = DEFAULT_CONFIG) -> bool | None:
    """Whether a day counts as hard, from the day's summed zone times.

    Power and HR zone times are accumulated separately. A day is hard if any rung
    of the power ladder or the HR ladder is reached (time at or above a zone).
    Returns None when no activity of the day has zone data.
    """
    by_basis: dict[str, list[float]] = {}
    for activity in day_activities:
        secs, basis = activity_zones(activity)
        if secs is None or basis is None:
            continue
        accumulated = by_basis.setdefault(basis, [0.0] * ZONE_COUNT)
        for index, value in enumerate(secs):
            accumulated[index] += value
    if not by_basis:
        return None
    ladders = {"power": config.hard_day_power_ladder, "hr": config.hard_day_hr_ladder}
    for basis, secs in by_basis.items():
        for zone, min_secs in ladders[basis]:
            if sum(secs[zone - 1 :]) >= min_secs:
                return True
    return False


# ---------------------------------------------------------------------------
# Capability: durability, efficiency factor, eFTP
# ---------------------------------------------------------------------------


def _durability_exclusion(  # pylint: disable=too-many-return-statements
    activity: Activity, family: str, config: CoachConfig
) -> str | None:
    """First failed quality criterion for a decoupling value, or None if it qualifies.

    Reasons (limits from ``config``): ``short`` (moving time too short), ``pauses``
    (moving/elapsed too low), ``heat`` (avg temperature too high; a missing
    temperature, e.g. indoors, passes), ``no_power`` (ride without VI), ``vi`` (VI too
    high; runs without power skip this check), ``no_decoupling`` (value missing).
    """
    moving = _num(activity.get("moving_time")) or 0.0
    if moving < config.durability_min_moving_s:
        return "short"
    elapsed = _num(activity.get("elapsed_time"))
    if elapsed is not None and elapsed > 0 and moving / elapsed < config.durability_min_moving_ratio:
        return "pauses"
    temp = _num(activity.get("average_temp"))
    if temp is not None and temp > config.durability_max_temp_c:
        return "heat"
    vi = _num(activity.get("icu_variability_index"))
    if vi is None or vi <= 0:
        if family == RAD:
            return "no_power"
    elif vi > config.durability_max_vi:
        return "vi"
    if _num(activity.get("decoupling")) is None:
        return "no_decoupling"
    return None


def durability(  # pylint: disable=too-many-locals
    activities: list[Activity], end: date, days: int, config: CoachConfig = DEFAULT_CONFIG
) -> dict[str, Any]:
    """Aerobic decoupling (Pa:HR / Pace:HR drift, %) of steady long sessions.

    Only rides (Ride, VirtualRide) and runs that pass the quality filter count (see
    :func:`_durability_exclusion`). Per sport: median over the report window, number
    of values, number above ``durability_high_drift_pct`` (in the window and in the
    last 7 days) and the trend of the 7-day median vs. the window median
    (+/- ``durability_trend_band_pct`` = stable). Negative values (HR drifting down)
    are kept. Excluded sessions are counted per reason.
    """
    window_start = end - timedelta(days=days - 1)
    acute_start = end - timedelta(days=config.acute_days - 1)
    reasons: dict[str, int] = defaultdict(int)
    values: dict[str, list[tuple[date, float]]] = {RAD: [], LAUF: []}
    for activity in activities_between(activities, window_start, end):
        activity_type = activity.get("type")
        if activity_type in config.durability_ride_types:
            family = RAD
        elif activity_type in config.durability_run_types:
            family = LAUF
        else:
            continue
        reason = _durability_exclusion(activity, family, config)
        if reason is not None:
            reasons[reason] += 1
            continue
        day = activity_day(activity)
        decoupling = _num(activity.get("decoupling"))
        if day is not None and decoupling is not None:
            values[family].append((day, decoupling))

    result: dict[str, Any] = {}
    for family, entries in values.items():
        window_values = [value for _, value in entries]
        acute_values = [value for day, value in entries if day >= acute_start]
        median = statistics.median(window_values) if window_values else None
        trend = None
        if (
            median is not None
            and days > config.acute_days
            and len(acute_values) >= config.durability_min_sessions_trend
            and len(window_values) >= config.durability_min_sessions_trend
        ):
            delta = statistics.median(acute_values) - median
            if delta < -config.durability_trend_band_pct:
                trend = "improving"
            elif delta > config.durability_trend_band_pct:
                trend = "declining"
            else:
                trend = "stable"
        result[family] = {
            "median": _r(median, 1),
            "n": len(window_values),
            "high": sum(1 for v in window_values if v > config.durability_high_drift_pct),
            "high_7d": sum(1 for v in acute_values if v > config.durability_high_drift_pct),
            "trend": trend,
        }
    result["excluded"] = sum(reasons.values())
    result["reasons"] = dict(sorted(reasons.items()))
    return result


def efficiency_factor(
    activities: list[Activity], end: date, config: CoachConfig = DEFAULT_CONFIG
) -> dict[str, Any]:
    """Mean efficiency factor (NP / avg HR) of steady rides, 7 vs. 28 days.

    Qualifying: cycling type, ``icu_efficiency_factor`` present, 0 < VI <=
    ``ef_max_vi`` and at least ``ef_min_moving_s`` moving. Each mean needs ``ef_min_sessions`` values. Trend:
    7-day minus 28-day mean, +/- ``ef_trend_band`` = stable; rising = better aerobic
    efficiency.
    """

    def qualifying(window_days: int) -> list[float]:
        start = end - timedelta(days=window_days - 1)
        values = []
        for activity in activities_between(activities, start, end):
            ef = _num(activity.get("icu_efficiency_factor"))
            vi = _num(activity.get("icu_variability_index"))
            moving = _num(activity.get("moving_time")) or 0.0
            if (
                activity.get("type") in config.ef_types
                and ef is not None
                and vi is not None
                and 0 < vi <= config.ef_max_vi
                and moving >= config.ef_min_moving_s
            ):
                values.append(ef)
        return values

    acute = qualifying(config.acute_days)
    chronic = qualifying(config.chronic_days)
    acute_mean = statistics.mean(acute) if len(acute) >= config.ef_min_sessions else None
    chronic_mean = statistics.mean(chronic) if len(chronic) >= config.ef_min_sessions else None
    trend = None
    if acute_mean is not None and chronic_mean is not None:
        delta = acute_mean - chronic_mean
        if delta > config.ef_trend_band:
            trend = "improving"
        elif delta < -config.ef_trend_band:
            trend = "declining"
        else:
            trend = "stable"
    return {
        "ef_7d": _r(acute_mean, 2),
        "ef_28d": _r(chronic_mean, 2),
        "n_7d": len(acute),
        "n_28d": len(chronic),
        "trend": trend,
    }


def eftp_by_day(wellness: dict[date, WellnessRecord]) -> dict[date, float]:
    """Cycling eFTP per day from ``wellness.sportInfo`` (entry with type Ride)."""
    series = {}
    for day, record in wellness.items():
        sport_info = record.get("sportInfo")
        if not isinstance(sport_info, list):
            continue
        for entry in sport_info:
            if isinstance(entry, dict) and entry.get("type") == "Ride":
                value = _num(entry.get("eftp"))
                if value is not None and value > 0:
                    series[day] = value
    return series


def _nearest_value(series: dict[date, float], target: date, tolerance: int) -> float | None:
    """Value of the day closest to ``target`` within +/- ``tolerance`` days (earlier wins ties)."""
    for distance in range(tolerance + 1):
        for day in (target - timedelta(days=distance), target + timedelta(days=distance)):
            if day in series:
                return series[day]
    return None


def eftp_trend(
    wellness: dict[date, WellnessRecord], end: date, config: CoachConfig = DEFAULT_CONFIG
) -> dict[str, Any]:
    """Cycling eFTP now vs. 28 and 56 days ago, in W and %.

    Stateless replacement for Section 11's benchmark index (which needs a local FTP
    history file): Intervals.icu stores the eFTP estimate on every wellness day.
    """
    series = {day: value for day, value in eftp_by_day(wellness).items() if day <= end}
    now = _nearest_value(series, end, config.eftp_tolerance_days)
    result: dict[str, Any] = {"now": _r(now, 0)}
    for lookback in config.eftp_lookback_days:
        past = _nearest_value(series, end - timedelta(days=lookback), config.eftp_tolerance_days)
        result[f"d{lookback}"] = _r(past, 0)
        result[f"pct_{lookback}"] = (
            _r((now / past - 1) * 100, 1) if now is not None and past is not None else None
        )
    return result


# ---------------------------------------------------------------------------
# Thresholds, top sessions, coverage
# ---------------------------------------------------------------------------


def _sport_setting(athlete: dict[str, Any], activity_type: str) -> dict[str, Any]:
    """First sport settings entry that covers ``activity_type``."""
    settings = athlete.get("sportSettings")
    if isinstance(settings, list):
        for entry in settings:
            types = entry.get("types") if isinstance(entry, dict) else None
            if isinstance(types, list) and activity_type in types:
                return entry
    return {}


def _ftp_of_latest_ride(activities: list[Activity], types: tuple[str, ...]) -> float | None:
    """FTP (``icu_ftp``) that was in force on the most recent ride of the given types."""
    rides = [
        a for a in activities if a.get("type") in types and (_num(a.get("icu_ftp")) or 0) > 0
    ]
    if not rides:
        return None
    latest = max(rides, key=lambda a: a.get("start_date_local") or "")
    return _num(latest.get("icu_ftp"))


def athlete_thresholds(
    athlete: dict[str, Any], activities: list[Activity] | None = None
) -> dict[str, Any]:
    """FTP (outdoor/indoor) and LTHR.

    FTP comes from the latest outdoor ride / virtual ride in ``activities`` (the FTP
    Intervals.icu used at that time, so reports for past dates compare eFTP with the
    FTP of that period). Without such rides the current sport settings are used.
    """
    ride = _sport_setting(athlete, "Ride")
    run = _sport_setting(athlete, "Run")
    rides = activities or []
    outdoor_ftp = _ftp_of_latest_ride(rides, ("Ride", "GravelRide", "MountainBikeRide"))
    indoor_ftp = _ftp_of_latest_ride(rides, ("VirtualRide",))
    return {
        "ftp": _r(outdoor_ftp or _num(ride.get("ftp")), 0),
        "ftp_indoor": _r(indoor_ftp or _num(ride.get("indoor_ftp")), 0),
        "lthr_rad": _r(_num(ride.get("lthr")), 0),
        "lthr_lauf": _r(_num(run.get("lthr")), 0),
    }


def intensity_factor(activity: Activity) -> float | None:
    """IF as a fraction; Intervals.icu reports ``icu_intensity`` in percent."""
    value = _num(activity.get("icu_intensity"))
    if value is None or value <= 0:
        return None
    return value / 100 if value > 3 else value


def top_sessions(activities: list[Activity], config: CoachConfig = DEFAULT_CONFIG) -> list[dict[str, Any]]:
    """The ``top_n`` most notable sessions: highest load first.

    If the session with the highest IF is not among them, it replaces the last
    entry, so the hardest short session is not hidden behind long easy ones.
    Ties are broken by IF, then by the most recent date.
    """
    if config.top_n <= 0 or not activities:
        return []
    ordered = sorted(
        activities,
        key=lambda a: (
            -activity_load(a),
            -(intensity_factor(a) or 0.0),
            -(activity_day(a) or date.min).toordinal(),
        ),
    )
    top = ordered[: config.top_n]
    with_if = [a for a in activities if intensity_factor(a) is not None]
    if with_if and len(top) == config.top_n:
        hardest = max(with_if, key=lambda a: (intensity_factor(a) or 0.0, activity_load(a)))
        if not any(entry is hardest for entry in top):
            top[-1] = hardest
    return [
        {
            "date": (activity_day(a) or date.min).isoformat(),
            "type": sport_family(a.get("type")),
            "min": _r((_num(a.get("moving_time")) or 0.0) / 60, 0),
            "load": _r(activity_load(a), 0),
            "if": _r(intensity_factor(a), 2),
        }
        for a in top
    ]


def _has_rpe(activity: Activity) -> bool:
    return _num(activity.get("icu_rpe")) is not None or _num(activity.get("perceived_exertion")) is not None


def _has_feel(activity: Activity) -> bool:
    return _num(activity.get("feel")) is not None


def coverage(
    activities: list[Activity],
    wellness: dict[date, WellnessRecord],
    end: date,
    days: int,
    config: CoachConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """How much data the report is based on (window days and sessions)."""
    window = days_back(end, days)
    zones = {"power": 0, "hr": 0, "none": 0}
    for activity in activities:
        _, basis = activity_zones(activity)
        zones[basis or "none"] += 1
    return {
        "days": days,
        "hrv_days": sum(1 for day in window if _valid_hrv(wellness.get(day, {}), config) is not None),
        "rhr_days": sum(1 for day in window if (_num(wellness.get(day, {}).get("restingHR")) or 0) > 0),
        "sleep_days": sum(1 for day in window if (_num(wellness.get(day, {}).get("sleepSecs")) or 0) > 0),
        "sessions": len(activities),
        "zones": zones,
        "rpe": sum(1 for a in activities if _has_rpe(a)),
        "feel": sum(1 for a in activities if _has_feel(a)),
    }


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = {"alarm": 0, "warning": 1, "info": 2}


def _flag(code: str, severity: str, value: Any, threshold: Any) -> dict[str, Any]:
    return {"code": code, "sev": severity, "val": value, "thr": threshold}


def _last_session_days(
    activities: list[Activity], end: date, family: str
) -> int | None:
    days = [
        (end - day).days
        for a in activities
        if sport_family(a.get("type")) == family and (day := activity_day(a)) is not None and day <= end
    ]
    return min(days) if days else None


def build_flags(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    report: dict[str, Any],
    activities: list[Activity],
    window_activities: list[Activity],
    end: date,
    history_days: int,
    config: CoachConfig = DEFAULT_CONFIG,
) -> list[dict[str, Any]]:
    """Rule-based hints from the computed report, sorted alarm > warning > info.

    Every flag is ``{code, sev, val, thr}``; all thresholds come from ``config``.
    """
    flags: list[dict[str, Any]] = []

    thresholds = report["thresholds"]
    eftp_now = report["capability"]["eftp"]["now"]
    if eftp_now:
        for key, code in (("ftp", "ftp_eftp_dev"), ("ftp_indoor", "ftp_indoor_eftp_dev")):
            ftp = thresholds.get(key)
            if not ftp or (key == "ftp_indoor" and ftp == thresholds.get("ftp")):
                continue
            deviation = (ftp / eftp_now - 1) * 100
            if abs(deviation) > config.ftp_eftp_max_dev_pct:
                flags.append(_flag(code, "warning", _r(deviation, 1), config.ftp_eftp_max_dev_pct))

    for sport in config.tracked_sports:
        since = _last_session_days(activities, end, sport)
        if since is None:
            flags.append(_flag(f"sport_inactive:{sport}", "info", f">{history_days}", config.sport_inactive_days))
        elif since > config.sport_inactive_days:
            flags.append(_flag(f"sport_inactive:{sport}", "info", since, config.sport_inactive_days))

    load = report["load"]
    acwr = load["acwr"]
    if acwr is not None:
        if acwr >= config.acwr_high_alarm:
            flags.append(_flag("acwr_high", "alarm", acwr, config.acwr_high_alarm))
        elif acwr > config.acwr_high_warn:
            flags.append(_flag("acwr_high", "warning", acwr, config.acwr_high_warn))
        elif acwr <= config.acwr_low_alarm:
            flags.append(_flag("acwr_low", "alarm", acwr, config.acwr_low_alarm))
        elif acwr < config.acwr_low_warn:
            flags.append(_flag("acwr_low", "warning", acwr, config.acwr_low_warn))

    effective = load["effective_monotony"]
    if effective is not None and effective > config.monotony_warn:
        severity, threshold = "warning", config.monotony_warn
        if effective >= config.monotony_alarm:
            severity, threshold = "alarm", config.monotony_alarm
        if load["deload"]:
            severity = "info"
        flags.append(_flag("monotony_high", severity, effective, threshold))

    hrv = report["recovery"]["hrv"]
    if hrv["status"] == "below":
        severity = "alarm" if hrv["days_below"] >= config.hrv_alarm_days else "warning"
        flags.append(_flag("hrv_below", severity, hrv["ln_7d"], hrv["band"][0]))
    elif hrv["status"] == "insufficient_data":
        flags.append(_flag("hrv_insufficient", "info", hrv["n_7d"], config.hrv_min_points_acute))

    rhr = report["recovery"]["rhr"]
    days_high = rhr.get("days_high", 0)
    if days_high >= config.rhr_alarm_days:
        flags.append(_flag("rhr_elevated_days", "alarm", days_high, config.rhr_alarm_days))
    elif days_high >= config.rhr_warn_days:
        flags.append(_flag("rhr_elevated_days", "warning", days_high, config.rhr_warn_days))

    recent = report["recovery"]["sleep"]["recent_h"]
    short_nights = sum(1 for hours in recent if hours is not None and hours < config.sleep_short_hours)
    if short_nights >= config.sleep_short_min_nights:
        flags.append(_flag("sleep_short", "warning", short_nights, config.sleep_short_min_nights))

    if window_activities:
        missing = sum(1 for a in window_activities if not _has_rpe(a) and not _has_feel(a))
        share = missing / len(window_activities)
        if share > config.subjective_missing_share:
            flags.append(_flag("subjective_missing", "info", _r(share, 2), config.subjective_missing_share))

    durability_result = report["capability"]["durability"]
    for family in (RAD, LAUF):
        entry = durability_result[family]
        if entry["median"] is not None and entry["median"] > config.durability_high_drift_pct:
            flags.append(_flag(f"durability_high:{family}", "warning", entry["median"], config.durability_high_drift_pct))
        elif entry["high_7d"] >= config.durability_high_drift_count_7d:
            flags.append(_flag(f"durability_high_7d:{family}", "warning", entry["high_7d"], config.durability_high_drift_count_7d))

    drift = report["intensity"]["drift"]
    if drift["drift"] == "acute_depolarization":
        flags.append(_flag("tid_depolarization", "warning", drift["pi_7d"], config.pi_polarized_min))

    return sorted(flags, key=lambda flag: _SEVERITY_ORDER[flag["sev"]])


# ---------------------------------------------------------------------------
# Plan (projection mode)
# ---------------------------------------------------------------------------

CalendarEvent = dict[str, Any]


def event_day(event: CalendarEvent) -> date | None:
    """Local calendar day of a calendar event."""
    return parse_day(event.get("start_date_local"))


def event_load(event: CalendarEvent) -> float | None:
    """Load Intervals.icu computed for a planned event; None if it computed none.

    Unlike :func:`activity_load`, a missing load stays None (e.g. strength sessions
    without targets) so the report can say so instead of counting it as 0.
    """
    load = _num(event.get("icu_training_load"))
    return max(load, 0.0) if load is not None else None


def _collect_plan_events(
    events: list[CalendarEvent], plan_start: date, end: date, race_until: date
) -> tuple[dict[date, list[CalendarEvent]], set[date], list[dict[str, Any]]]:
    """WORKOUT events per day up to ``end``, race days and races up to ``race_until``."""
    workouts: dict[date, list[CalendarEvent]] = defaultdict(list)
    race_days: set[date] = set()
    races = []
    for event in events:
        day = event_day(event)
        if day is None or day < plan_start:
            continue
        category = event.get("category")
        if category == WORKOUT and day <= end:
            workouts[day].append(event)
        elif category in RACE_CATEGORIES and day <= race_until:
            race_days.add(day)
            races.append({"date": day.isoformat(), "name": event.get("name"), "category": category})
    return workouts, race_days, sorted(races, key=lambda race: race["date"])


def _planned_load(totals: list[dict[str, float]]) -> float | int | None:
    """Sum of the known loads; None if there are events but none has a load."""
    if sum(t["n"] for t in totals) > 0 and sum(t["with_load"] for t in totals) == 0:
        return None
    return _r(sum(t["load"] for t in totals), 0)


def _plan_week(
    label: str,
    week_days: list[date],
    workouts: dict[date, list[CalendarEvent]],
    race_days: set[date],
) -> dict[str, Any]:
    """Planned load, hours and sessions of one ISO week, in total and per sport family."""
    sports: dict[str, dict[str, float]] = defaultdict(
        lambda: {"secs": 0.0, "load": 0.0, "n": 0.0, "with_load": 0.0}
    )
    for day in week_days:
        for event in workouts.get(day, []):
            totals = sports[sport_family(event.get("type"))]
            totals["secs"] += _num(event.get("moving_time")) or 0.0
            totals["n"] += 1
            load = event_load(event)
            if load is not None:
                totals["load"] += load
                totals["with_load"] += 1
    all_totals = list(sports.values())
    return {
        "week": label,
        "days": len(week_days),
        "load": _planned_load(all_totals),
        "h": _r(sum(t["secs"] for t in all_totals) / 3600, 1),
        "n": int(sum(t["n"] for t in all_totals)),
        "by_sport": {
            family: {
                "load": _planned_load([sports[family]]),
                "h": _r(sports[family]["secs"] / 3600, 1),
                "n": int(sports[family]["n"]),
            }
            for family in sorted(sports)
        },
        "rest_days": sum(1 for day in week_days if not workouts.get(day) and day not in race_days),
        "missing_load": int(sum(t["n"] - t["with_load"] for t in all_totals)),
    }


def _week_fitness(wellness: dict[date, WellnessRecord], week_days: list[date]) -> dict[str, Any]:
    """Projected CTL and ramp at the week's last day and the lowest TSB of its days.

    Ramp is Intervals.icu's ``rampRate``, or CTL(day) - CTL(day - 7) without it.
    """
    last = week_days[-1]
    ctl = _num(wellness.get(last, {}).get("ctl"))
    ramp = _num(wellness.get(last, {}).get("rampRate"))
    if ramp is None and ctl is not None:
        week_ago = _num(wellness.get(last - timedelta(days=7), {}).get("ctl"))
        ramp = ctl - week_ago if week_ago is not None else None
    tsb_values = []
    for day in week_days:
        record = wellness.get(day, {})
        day_ctl, day_atl = _num(record.get("ctl")), _num(record.get("atl"))
        if day_ctl is not None and day_atl is not None:
            tsb_values.append(day_ctl - day_atl)
    return {
        "ctl": _r(ctl, 1),
        "ramp": _r(ramp, 1),
        "tsb_min": _r(min(tsb_values), 1) if tsb_values else None,
    }


def plan_summary(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    events: list[CalendarEvent],
    wellness: dict[date, WellnessRecord],
    activities: list[Activity],
    plan_start: date,
    end: date,
    race_until: date,
) -> dict[str, Any]:
    """Planned workouts per ISO week from ``plan_start`` to ``end``, plus upcoming races.

    * Only events with category WORKOUT count; sport families as in the volume section.
    * ``load`` is the planned load only: the sum of the loads Intervals.icu computed,
      None if a week (or sport) has events but none of them has a load.
      ``missing_load`` counts events without a load.
    * ``rest_days``: plan days without a WORKOUT event; a race day is no rest day.
    * ``ctl``/``ramp``/``tsb_min`` come from the Intervals.icu projection in the
      wellness data, which includes planned workouts (see :func:`_week_fitness`).
    * The week that also has completed days (it contains ``plan_start - 1``) gets
      ``done_load`` and ``done_h`` from ``activities``; they are never added to ``load``.
    * ``races``: RACE_A/B/C events from ``plan_start`` to ``race_until``.
    """
    workouts, race_days, races = _collect_plan_events(events, plan_start, end, race_until)
    weeks: dict[str, list[date]] = {}
    for offset in range((end - plan_start).days + 1):
        day = plan_start + timedelta(days=offset)
        weeks.setdefault(iso_week_label(day), []).append(day)

    done_end = plan_start - timedelta(days=1)
    rows = []
    for label, week_days in weeks.items():
        row = _plan_week(label, week_days, workouts, race_days)
        row.update(_week_fitness(wellness, week_days))
        if iso_week_label(done_end) == label:
            monday = done_end - timedelta(days=done_end.weekday())
            done = activities_between(activities, monday, done_end)
            row["done_load"] = _r(sum(activity_load(a) for a in done), 0)
            row["done_h"] = _r(sum(_num(a.get("moving_time")) or 0.0 for a in done) / 3600, 1)
        rows.append(row)
    return {"from": plan_start.isoformat(), "to": end.isoformat(), "weeks": rows, "races": races}


def plan_flags(plan: dict[str, Any], config: CoachConfig = DEFAULT_CONFIG) -> list[dict[str, Any]]:
    """Flags on the planned weeks, each with ``basis`` = projection and its ``week``.

    * ``ramp_planned_high``: projected ramp above ``ramp_planned_warn`` (coach rule).
    * ``tsb_planned_low``: lowest projected TSB below ``tsb_planned_warn`` /
      ``tsb_planned_alarm``.
    * ``planned_rest_days_low``: a week that lies completely in the plan has fewer
      than ``planned_min_rest_days`` rest days.
    """
    flags: list[dict[str, Any]] = []
    for week in plan["weeks"]:
        found = []
        ramp = week["ramp"]
        if ramp is not None and ramp > config.ramp_planned_warn:
            found.append(_flag("ramp_planned_high", "warning", ramp, config.ramp_planned_warn))
        tsb = week["tsb_min"]
        if tsb is not None and tsb < config.tsb_planned_alarm:
            found.append(_flag("tsb_planned_low", "alarm", tsb, config.tsb_planned_alarm))
        elif tsb is not None and tsb < config.tsb_planned_warn:
            found.append(_flag("tsb_planned_low", "warning", tsb, config.tsb_planned_warn))
        if week["days"] == 7 and week["rest_days"] < config.planned_min_rest_days:
            found.append(
                _flag("planned_rest_days_low", "info", week["rest_days"], config.planned_min_rest_days)
            )
        flags.extend({**flag, "basis": "projection", "week": week["week"]} for flag in found)
    return flags


def _with_projection(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    report: dict[str, Any],
    wellness: dict[date, WellnessRecord],
    activities: list[Activity],
    events: list[CalendarEvent],
    today: date,
    config: CoachConfig,
) -> dict[str, Any]:
    """Projection-mode additions: load.actual/projected, recovery.as_of, plan, flag basis.

    ``plan`` is inserted right after ``volume``; the other keys keep their order.
    """
    end = date.fromisoformat(report["period"]["end"])
    load_end = date.fromisoformat(report["period"]["load_end"])
    load = report["load"]
    projected = {
        "date": load.get("as_of", end.isoformat()),
        **{key: load[key] for key in ("ctl", "atl", "tsb", "ramp", "src")},
    }
    load["actual"] = {"date": today.isoformat(), **fitness_status(wellness, activities, today, today)}
    load["projected"] = projected
    report["recovery"] = {"as_of": today.isoformat(), **report["recovery"]}

    race_until = max(end, today + timedelta(days=config.race_lookahead_days))
    plan = plan_summary(events, wellness, activities, load_end + timedelta(days=1), end, race_until)
    plan["projection"] = dict(projected)

    flags = [{**flag, "basis": "actual"} for flag in report["flags"]] + plan_flags(plan, config)
    report["flags"] = sorted(flags, key=lambda flag: _SEVERITY_ORDER[flag["sev"]])

    result: dict[str, Any] = {}
    for key, value in report.items():
        result[key] = value
        if key == "volume":
            result["plan"] = plan
    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _zone_map_label(mapping: tuple[int, ...]) -> str:
    """Readable mapping such as ``Z1-Z2|Z3|Z4-Z7``."""
    groups = []
    for target in (1, 2, 3):
        zones = [index + 1 for index, value in enumerate(mapping) if value == target]
        if not zones:
            groups.append("-")
        elif len(zones) == 1:
            groups.append(f"Z{zones[0]}")
        else:
            groups.append(f"Z{zones[0]}-Z{zones[-1]}")
    return "|".join(groups)


def default_load_end(activities: Any, today: date) -> date:
    """Last day to include in load windows when the report ends today.

    Returns ``today`` once an activity is recorded for today, otherwise yesterday:
    a morning report would otherwise count today as a rest day and understate the
    7-day load, ACWR and the current week.
    """
    if isinstance(activities, list):
        for activity in activities:
            if isinstance(activity, dict) and activity_day(activity) == today:
                return today
    return today - timedelta(days=1)


def build_coach_report(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    activities: Any,
    wellness: Any,
    athlete: Any,
    end: date,
    days: int,
    config: CoachConfig = DEFAULT_CONFIG,
    load_end: date | None = None,
    *,
    today: date | None = None,
    events: Any = None,
) -> dict[str, Any]:
    """Assemble the complete coach report from raw Intervals.icu data.

    Args:
        activities: activity dicts covering at least ``max(days, 28)`` days up to
            ``load_end``.
        wellness: wellness records (list or date-keyed dict) covering at least
            ``max(days, 60)`` days up to ``end``.
        athlete: the athlete record (for sport settings).
        end: report date (inclusive). CTL/ATL/TSB are evaluated on this day;
            recovery, eFTP, coverage and inactivity flags too, unless it lies after
            ``today``.
        days: length of the report window in days.
        config: thresholds and mappings.
        load_end: last day of the load-based windows (volume, ACWR, monotony,
            intensity, durability, EF, top sessions); defaults to ``end`` and is
            capped at ``end`` (at ``today`` in projection mode). See
            :func:`default_load_end`.
        today: the athlete's current day. If ``end`` lies after it, the report is a
            projection (``period.mode``): everything based on completed data is
            evaluated up to ``today`` / ``load_end``, and ``plan`` summarises
            ``events`` from ``load_end + 1`` to ``end`` (see :func:`_with_projection`).
        events: calendar events (planned workouts and races) for projection mode.

    Returns:
        A JSON-serialisable dict with fixed keys and ``schema_version``.
    """
    if days < 1:
        raise ValueError("days must be at least 1")
    # Day that recovery and other "current state" values refer to.
    as_of = today if today is not None and end > today else end
    projection = as_of != end
    load_end = as_of if load_end is None else min(load_end, as_of)
    acts = [a for a in activities if isinstance(a, dict)] if isinstance(activities, list) else []
    acts = [a for a in acts if (day := activity_day(a)) is not None and day <= end]
    load_acts = [a for a in acts if (day := activity_day(a)) is not None and day <= load_end]
    well = wellness_by_day(wellness)
    athlete_record = athlete if isinstance(athlete, dict) else {}
    start = load_end - timedelta(days=days - 1)
    window_acts = activities_between(acts, start, load_end)

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "period": {
            "mode": "projection" if projection else "actual",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "load_end": load_end.isoformat(),
            "days": days,
            "windows": {
                "acute": config.acute_days,
                "chronic": config.chronic_days,
                "baseline": config.baseline_days,
            },
        },
        "flags": [],
        "load": {
            **fitness_status(well, acts, end, today),
            **load_metrics(load_acts, load_end, config),
        },
        "recovery": {
            "hrv": hrv_status(well, as_of, config),
            "rhr": rhr_status(well, as_of, config),
            "sleep": sleep_summary(well, as_of, days, config),
        },
        "volume": weekly_volume(load_acts, load_end, days, config),
        "intensity": {
            "map": {
                "power": _zone_map_label(config.power_zone_map),
                "hr": _zone_map_label(config.hr_zone_map),
            },
            "all": intensity_distribution(window_acts, config),
            "rad": intensity_distribution(window_acts, config, RAD),
            "drift": tid_drift(load_acts, load_end, config),
        },
        "capability": {
            "durability": durability(load_acts, load_end, days, config),
            "ef": efficiency_factor(load_acts, load_end, config),
            "eftp": eftp_trend(well, as_of, config),
        },
        "top_sessions": top_sessions(window_acts, config),
        "thresholds": athlete_thresholds(athlete_record, load_acts),
        "coverage": coverage(window_acts, well, as_of, days, config),
    }
    report["flags"] = build_flags(
        report, acts, window_acts, as_of, max(days, config.chronic_days), config
    )
    if projection:
        plan_events = [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []
        report = _with_projection(report, well, acts, plan_events, as_of, config)
    return report
