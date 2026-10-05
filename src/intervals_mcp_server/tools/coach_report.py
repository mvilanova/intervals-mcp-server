"""
Coach report MCP tool for Intervals.icu.

This module only fetches data. All numbers are computed by the pure
``intervals_mcp_server.coach_metrics`` module.
"""

import asyncio
import json
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.coach_metrics import (
    DEFAULT_CONFIG,
    RACE_CATEGORIES,
    build_coach_report,
    default_load_end,
)
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()

MIN_DAYS = 7
MAX_DAYS = 90
MAX_PLAN_DAYS = 90
MIN_END_DATE = date(2000, 1, 1)
MAX_END_DATE = date(2100, 12, 31)
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def _parse_end_date(value: str) -> date | None:
    """Strict YYYY-MM-DD within a plausible range, else None.

    The range keeps the window arithmetic away from date.min/date.max.
    """
    if not _DATE_PATTERN.fullmatch(value):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if MIN_END_DATE <= parsed <= MAX_END_DATE else None


def _athlete_today(athlete: Any) -> date:
    """Today in the athlete's time zone; the server itself may run in UTC."""
    timezone_name = athlete.get("timezone") if isinstance(athlete, dict) else None
    if isinstance(timezone_name, str) and timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name)).date()
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return date.today()


def _error_message(result: Any) -> str | None:
    """Message of an error dict returned by make_intervals_request, else None."""
    if isinstance(result, dict) and result.get("error"):
        return str(result.get("message"))
    return None


async def _fetch_activities(athlete_id: str, anchor: date, days: int) -> Any:
    # ``anchor`` = min(end, today): no activities exist after today.
    # One extra day so the load windows still fit if they end the day before ``anchor``.
    oldest = anchor - timedelta(days=max(days, DEFAULT_CONFIG.chronic_days))
    # newest is padded by one day; activities after the end date are dropped later.
    params = {"oldest": oldest.isoformat(), "newest": (anchor + timedelta(days=1)).isoformat()}
    return await make_intervals_request(url=f"/athlete/{athlete_id}/activities", params=params)


async def _fetch_wellness(athlete_id: str, anchor: date, end: date, days: int) -> Any:
    # Baselines end at ``anchor``; days after it carry the projected CTL/ATL.
    oldest = anchor - timedelta(days=max(days, DEFAULT_CONFIG.baseline_days) - 1)
    params = {"oldest": oldest.isoformat(), "newest": end.isoformat()}
    return await make_intervals_request(url=f"/athlete/{athlete_id}/wellness", params=params)


async def _fetch_plan_events(athlete_id: str, today: date, end: date) -> Any:
    """Calendar events up to ``end`` plus races within the look-ahead, deduplicated by id.

    Returns the error dict of the first failed request instead.
    """
    race_until = max(end, today + timedelta(days=DEFAULT_CONFIG.race_lookahead_days))
    url = f"/athlete/{athlete_id}/events"
    results = await asyncio.gather(
        make_intervals_request(url=url, params={"oldest": today.isoformat(), "newest": end.isoformat()}),
        make_intervals_request(
            url=url,
            params={
                "oldest": today.isoformat(),
                "newest": race_until.isoformat(),
                "category": ",".join(RACE_CATEGORIES),
            },
        ),
    )
    events: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for result in results:
        if _error_message(result) is not None:
            return result
        for event in result if isinstance(result, list) else []:
            if not isinstance(event, dict):
                continue
            event_id = event.get("id")
            if event_id is not None:
                if event_id in seen:
                    continue
                seen.add(event_id)
            events.append(event)
    return events


async def _fetch_report_data(
    athlete_id: str, today: date, end: date, days: int
) -> tuple[Any, Any, Any]:
    """Activities, wellness and (only for an end date after today) calendar events."""
    anchor = min(end, today)
    if end <= today:
        activities, wellness = await asyncio.gather(
            _fetch_activities(athlete_id, anchor, days),
            _fetch_wellness(athlete_id, anchor, end, days),
        )
        return activities, wellness, None
    return await asyncio.gather(
        _fetch_activities(athlete_id, anchor, days),
        _fetch_wellness(athlete_id, anchor, end, days),
        _fetch_plan_events(athlete_id, today, end),
    )


@mcp.tool()
async def get_coach_report(  # pylint: disable=too-many-return-statements
    days: int = 28, end_date: str | None = None, athlete_id: str | None = None
) -> str:
    """Compact, pre-computed training report (JSON) for coaching questions.

    Use this FIRST for overview questions: how training is going, load, fatigue and
    form, recovery (HRV, resting HR, sleep), weekly volume per sport, intensity
    distribution, durability, FTP vs. eFTP, weekly reviews and planning the next
    days. All numbers are computed deterministically on the server; interpret them,
    do not recompute them from raw activities. Use get_activities,
    get_activity_details or get_activity_intervals only to inspect single sessions.

    Args:
        days: Report window in days (7-90, default 28). ACWR/monotony (7 and 28 days)
            and the HRV/RHR baselines (60 days) always use their fixed windows.
        end_date: Report date, YYYY-MM-DD (default: today in the athlete's time
            zone). With the default, load-based sections (volume, load, intensity,
            capability, top_sessions) end yesterday until today's first activity is
            recorded (period.load_end), so an untrained morning does not look like a
            rest day. Recovery and CTL/ATL/TSB refer to the report date. A future
            end_date (at most 90 days ahead) gives a projection to check planned
            weeks, see "Projection mode" below.
        athlete_id: Intervals.icu athlete ID of a coached athlete (optional; default:
            ATHLETE_ID from .env, i.e. your own account). Profile, time zone and
            thresholds are then those of that athlete.

    Output keys (schema_version 1.1); null always means "not enough data", never 0:
    - period: mode (actual, or projection when end_date is after today), start,
      end, load_end, days.
    - flags: rule-based hints {code, sev: alarm|warning|info, val, thr}, most
      severe first. Start here.
    - load: ctl, atl, tsb, ramp at the end date. src says what they contain: api
      (completed training), recomputed_without_planned (today's value without
      planned but not yet done workouts), api_incl_planned (Intervals.icu
      projection including planned workouts). load_7d, load_28d, acwr, monotony
      (Foster, 7 days incl. rest days), strain, primary_sport, primary_monotony,
      effective_monotony (multi-sport corrected, used for flags), deload.
    - recovery.hrv: 7-day mean of ln(rMSSD) vs. 60-day band (mean +/- 0.5 SD),
      status below|within|above|insufficient_data, days_below (streak).
      recovery.rhr: 7-day vs. 60-day mean, delta (bpm), days_high (streak >= +5).
      recovery.sleep: avg_h, avg_7d_h, nights_short (< 7 h), recent_h (last 3
      nights, oldest first).
    - volume: per ISO week and sport family (Rad = Ride + VirtualRide, Lauf,
      Schwimmen, Kraft, Sonstige): h, load, n, km; rest_days, hard_days,
      weekly monotony.
    - intensity: 3-zone shares pct [low, moderate, high] for all sports and for
      Rad (power for cycling, HR otherwise; mapping in intensity.map), Treff
      polarization index pi (pi_note explains edge cases), class cls, and drift
      of the last 7 vs. 28 days.
    - capability: durability = median aerobic decoupling (%) of steady rides/runs
      >= 60 min after a quality filter, with excluded count and reasons;
      ef = efficiency factor 7 vs. 28 days; eftp = cycling eFTP now vs. 28/56
      days ago.
    - top_sessions: up to 5 notable sessions (highest load, plus the highest IF).
    - thresholds: FTP, indoor FTP, LTHR. coverage: available data (days with
      HRV/RHR/sleep, sessions with power/HR zones, RPE/feel).

    Projection mode (end_date after today): sections from completed training use
    the `days` up to period.load_end (last completed day); recovery, eftp and
    coverage refer to today (recovery.as_of). Only then these keys are added:
    - load.actual: ctl, atl, tsb, ramp today. load.projected: at end_date incl.
      planned workouts (same as the top-level load values).
    - plan: from (load_end + 1), to (end_date). weeks per ISO week: load (planned
      load only; null = Intervals.icu computed no load), h, n, by_sport, rest_days
      (days without a planned workout), missing_load (workouts without load), ctl
      and ramp at the week's last day, tsb_min; the current week also has
      done_load/done_h (completed, never included in load). races: RACE_A/B/C up
      to 12 weeks ahead. projection: same as load.projected.
    - every flag has basis: actual (completed data up to today) or projection
      (plan flags, with week): ramp_planned_high (ramp > 6), tsb_planned_low
      (tsb_min < -20 warning, < -30 alarm), planned_rest_days_low (fully planned
      week without rest day).
    """
    if not MIN_DAYS <= days <= MAX_DAYS:
        return f"Error: days must be between {MIN_DAYS} and {MAX_DAYS}."
    end: date | None = None
    if end_date:
        end = _parse_end_date(end_date)
        if end is None:
            return (
                "Error: end_date must be a valid date in YYYY-MM-DD format between "
                f"{MIN_END_DATE.isoformat()} and {MAX_END_DATE.isoformat()}."
            )

    athlete_id, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    # The athlete comes first: "today" (athlete time zone) decides the mode and windows.
    athlete = await make_intervals_request(url=f"/athlete/{athlete_id}")
    if (message := _error_message(athlete)) is not None:
        return f"Error fetching athlete: {message}"
    today = _athlete_today(athlete)
    use_default_end = end is None
    if end is None:
        end = today
    if (end - today).days > MAX_PLAN_DAYS:
        return f"Error: end_date may be at most {MAX_PLAN_DAYS} days after today ({today.isoformat()})."

    activities, wellness, events = await _fetch_report_data(athlete_id, today, end, days)
    if (message := _error_message(activities)) is not None:
        return f"Error fetching activities: {message}"
    if (message := _error_message(wellness)) is not None:
        return f"Error fetching wellness data: {message}"
    if (message := _error_message(events)) is not None:
        return f"Error fetching events: {message}"

    # An explicit end date up to today is not shifted; the default end date and
    # projections end the load windows at the last completed day.
    load_end = default_load_end(activities, today) if use_default_end or end > today else end
    report = build_coach_report(
        activities, wellness, athlete, end, days, load_end=load_end, today=today, events=events
    )
    return json.dumps(report, separators=(",", ":"), ensure_ascii=False)
