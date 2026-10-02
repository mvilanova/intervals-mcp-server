"""
Training review MCP tools for Intervals.icu.

This module contains read-only tools for a weekly training review:
- get_weekly_summary: per ISO week and sport totals plus end-of-week CTL/ATL/form.
- get_plan_compliance: planned workouts vs. executed activities.
"""

from datetime import date, datetime
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.utils.validation import resolve_athlete_id, validate_date

# Import mcp instance from shared module for tool registration
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401

config = get_config()


def _today() -> date:
    """Return today's date (separate function so tests can patch it)."""
    return date.today()


def _fmt_load(item: dict[str, Any]) -> str:
    """Training load as text; "n/a" when missing or null."""
    load = item.get("icu_training_load")
    return "n/a" if load is None else str(load)


def _fmt_duration(seconds: Any) -> str:
    """Format seconds as H:MM:SS (or 'n/a' if missing)."""
    if not isinstance(seconds, (int, float)):
        return "n/a"
    total = int(seconds)
    return f"{total // 3600}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def _fmt_km(meters: Any) -> str:
    """Format meters as kilometers with one decimal."""
    if not isinstance(meters, (int, float)):
        return "0.0 km"
    return f"{meters / 1000:.1f} km"


def _fmt_num(value: Any, digits: int = 1) -> str:
    """Format a number with fixed digits, or 'n/a' if missing."""
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{value:.{digits}f}"


def _validate_range(start_date: str, end_date: str) -> str | None:
    """Validate a date range; return an error message or None."""
    try:
        validate_date(start_date)
        validate_date(end_date)
    except ValueError as exc:
        return f"Error: {exc}"
    if start_date > end_date:
        return "Error: start_date must not be after end_date."
    return None


def _format_week(week: dict[str, Any]) -> str:
    """Format one SummaryWithCats entry (one ISO week) as compact text."""
    date_str = str(week.get("date", ""))
    try:
        iso = datetime.strptime(date_str[:10], "%Y-%m-%d").isocalendar()
        label = f"{date_str[:10]} (ISO {iso.year}-W{iso.week:02d})"
    except ValueError:
        label = date_str or "unknown week"

    lines = [
        f"Week {label}: {week.get('count', 0)} sessions | "
        f"time {_fmt_duration(week.get('moving_time'))} | "
        f"distance {_fmt_km(week.get('distance'))} | "
        f"load {week.get('training_load', 0)}"
    ]
    as_of = week.get("mostRecentWellnessId")
    lines.append(
        f"  End of week{f' (as of {as_of})' if as_of else ''}: "
        f"CTL/fitness {_fmt_num(week.get('fitness'))} | "
        f"ATL/fatigue {_fmt_num(week.get('fatigue'))} | "
        f"form {_fmt_num(week.get('form'))} | "
        f"ramp rate {_fmt_num(week.get('rampRate'), 2)}"
    )
    # timeInZones are HR zones (Z1..Z7 plus a trailing 8th slot). Verified against live
    # responses (the spec does not document it): a week's values equalled the sum of the
    # activities' icu_hr_zone_times.
    zones = week.get("timeInZones")
    if isinstance(zones, list) and zones:
        zone_text = ", ".join(f"Z{i + 1} {_fmt_duration(z)}" for i, z in enumerate(zones) if z)
        lines.append(f"  Time in HR zones: {zone_text or 'none'}")

    categories = [
        c for c in (week.get("byCategory") or []) if isinstance(c, dict) and c.get("count", 0) > 0
    ]
    for cat in categories:
        lines.append(
            f"  - {cat.get('category', 'Unknown')}: {cat.get('count', 0)} sessions | "
            f"time {_fmt_duration(cat.get('moving_time'))} | "
            f"distance {_fmt_km(cat.get('distance'))} | "
            f"load {cat.get('training_load', 0)}"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_weekly_summary(
    start_date: str,
    end_date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get a weekly training summary (read-only) from Intervals.icu.

    Returns one block per ISO week (weeks start on Monday) with the number of sessions,
    moving time, distance and training load, a breakdown per sport category, the time
    spent in heart rate zones (non-zero zones only), and the
    CTL (fitness), ATL (fatigue) and form at the END of the week (or the latest day with
    data for the current week). Sessions without heart rate data (e.g. strength) are
    still counted; in live data, WeightTraining activities were reported under the
    "Workout" category. Rows belonging to other athletes (followed/coached) are ignored.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    range_error = _validate_range(start_date, end_date)
    if range_error:
        return range_error

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/athlete-summary.json",
        api_key=api_key,
        params={"start": start_date, "end": end_date},
    )
    if isinstance(result, dict) and "error" in result:
        return f"Error fetching weekly summary: {result.get('message')}"
    if not isinstance(result, list) or not result:
        return f"No weekly summary data found for athlete {athlete_id_to_use} in the specified date range."

    # The endpoint may also return rows for other athletes (followed/coached) when called
    # with an API key; keep only the requested athlete (rows without athlete_id are kept).
    rows = [
        w
        for w in result
        if isinstance(w, dict)
        and (w.get("athlete_id") is None or str(w.get("athlete_id")) == str(athlete_id_to_use))
    ]
    if not rows:
        return f"No weekly summary data found for athlete {athlete_id_to_use} in the specified date range."
    # Week start (Monday) in `date` and end-of-week fitness/fatigue/form were verified
    # against live responses (wellness ctl/atl of the Sunday); the spec does not document it.
    weeks = sorted(rows, key=lambda w: str(w.get("date")))
    header = (
        f"Weekly summary {start_date} to {end_date} "
        "(weeks start on Monday; CTL/ATL/form are end-of-week values):"
    )
    return header + "\n\n" + "\n\n".join(_format_week(w) for w in weeks)


def _day(item: dict[str, Any]) -> str:
    """Return the local calendar day (YYYY-MM-DD) of an event or activity."""
    return str(item.get("start_date_local") or "")[:10]


def _pair_events_and_activities(
    events: list[dict[str, Any]], activities: list[dict[str, Any]]
) -> tuple[list[tuple[dict[str, Any], dict[str, Any] | None]], set[Any]]:
    """Pair events with activities using both paired_activity_id and paired_event_id.

    Returns:
        (pairs, used_activity_ids). A pair's activity is None if the event references an
        activity that is not in the fetched activity list.
    """
    by_id = {a.get("id"): a for a in activities if a.get("id") is not None}
    by_paired_event: dict[Any, dict[str, Any]] = {}
    for candidate in activities:
        if candidate.get("paired_event_id") is not None:
            by_paired_event.setdefault(candidate["paired_event_id"], candidate)

    pairs: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    used: set[Any] = set()
    for ev in events:
        # paired_activity_id is returned by the live API but is not in the OpenAPI Event
        # schema; activity.paired_event_id is the documented fallback.
        paired_id = ev.get("paired_activity_id")
        act: dict[str, Any] | None = by_id.get(paired_id) if paired_id is not None else None
        if act is None:
            act = by_paired_event.get(ev.get("id"))
        if act is not None:
            if act.get("id") in used:
                # Activity already claimed by another event: do not count it twice.
                continue
            used.add(act.get("id"))
            pairs.append((ev, act))
        elif paired_id is not None:
            pairs.append((ev, None))
    return pairs, used


def _deviation(planned: Any, actual: Any) -> str:
    """Return 'planned -> actual (+x%)' for numeric values, tolerant to missing data."""
    if not isinstance(planned, (int, float)) or not isinstance(actual, (int, float)):
        return "n/a"
    if planned == 0:
        return f"{planned} -> {actual} (n/a)"
    return f"{planned} -> {actual} ({(actual - planned) / planned * 100:+.0f}%)"


def _duration_deviation(planned: Any, actual: Any) -> str:
    """Return duration deviation text with H:MM:SS values."""
    if not isinstance(planned, (int, float)) or not isinstance(actual, (int, float)):
        return "n/a"
    pct = f"{(actual - planned) / planned * 100:+.0f}%" if planned else "n/a"
    return f"{_fmt_duration(planned)} -> {_fmt_duration(actual)} ({pct})"


def _event_label(ev: dict[str, Any]) -> str:
    """Short label for an event."""
    return (
        f"{_day(ev)} {ev.get('type') or 'Unknown'} '{ev.get('name') or 'unnamed'}' "
        f"(planned {_fmt_duration(ev.get('moving_time'))}, load {_fmt_load(ev)})"
    )


def _format_pair(ev: dict[str, Any], act: dict[str, Any] | None) -> str:
    """Format one completed planned workout."""
    head = f"- {_day(ev)} {ev.get('type') or 'Unknown'} '{ev.get('name') or 'unnamed'}'"
    if act is None:
        return head + ": completed (linked activity not in fetched range, no actuals)"
    return (
        f"{head} -> activity {act.get('id')} on {_day(act)}\n"
        f"    duration: {_duration_deviation(ev.get('moving_time'), act.get('moving_time'))}\n"
        f"    load: {_deviation(ev.get('icu_training_load'), act.get('icu_training_load'))}"
    )


def _format_availability(notes: list[dict[str, Any]]) -> list[str]:
    """Format NOTE events that carry training availability information."""
    lines: list[str] = []
    for note in notes:
        availability = note.get("training_availability")
        sports = note.get("can_train_sports")
        max_time = note.get("max_training_time")
        if not (availability or sports or max_time):
            continue
        parts = []
        if availability:
            parts.append(f"availability {availability}")
        if sports:
            parts.append(f"can train {', '.join(str(s) for s in sports)}")
        if max_time:
            parts.append(f"max training time {_fmt_duration(max_time)}")
        lines.append(f"- {_day(note)} '{note.get('name') or 'note'}': " + "; ".join(parts))
    return lines


def _build_compliance_report(  # pylint: disable=too-many-locals
    start_date: str,
    end_date: str,
    events: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    today: str,
) -> str:
    """Build the plan compliance report text from raw events and activities."""
    workouts = sorted(
        (e for e in events if e.get("category") == "WORKOUT"),
        key=lambda e: (_day(e), e.get("id") or 0),
    )
    notes = [e for e in events if e.get("category") == "NOTE"]
    activities = [a for a in activities if isinstance(a, dict)]

    pairs, used = _pair_events_and_activities(workouts, activities)
    paired_event_ids = {ev.get("id") for ev, _ in pairs}
    unpaired = [e for e in workouts if e.get("id") not in paired_event_ids]
    missed = [e for e in unpaired if _day(e) < today]
    upcoming = [e for e in unpaired if _day(e) >= today]
    candidates = [a for a in activities if a.get("id") not in used and a.get("start_date_local")]
    # Activities linked to an event that was not fetched (outside the queried range) were
    # planned, so they are not unplanned; they are listed separately.
    outside = [a for a in candidates if a.get("paired_event_id") is not None]
    unplanned = [a for a in candidates if a.get("paired_event_id") is None]

    due = len(pairs) + len(missed)
    pct = f"{len(pairs) / due * 100:.0f}%" if due else "n/a"
    lines = [
        f"Plan compliance {start_date} to {end_date} (today: {today}):",
        f"Planned workouts: {len(workouts)} | completed: {len(pairs)} | missed: {len(missed)} "
        f"| upcoming: {len(upcoming)} | unplanned activities: {len(unplanned)}",
        f"Completion: {pct} ({len(pairs)} of {due} planned workouts due)",
        "",
        f"Completed ({len(pairs)}):",
    ]
    lines += [_format_pair(ev, act) for ev, act in pairs] or ["- none"]
    lines += ["", f"Missed ({len(missed)}):"]
    lines += [f"- {_event_label(e)}" for e in missed] or ["- none"]
    lines += ["", f"Upcoming, not yet due ({len(upcoming)}):"]
    lines += [f"- {_event_label(e)}" for e in upcoming] or ["- none"]
    lines += ["", f"Unplanned activities ({len(unplanned)}):"]
    lines += [
        f"- {_day(a)} {a.get('type') or 'Unknown'} '{a.get('name') or 'unnamed'}' "
        f"(id {a.get('id')}, {_fmt_duration(a.get('moving_time'))}, load {_fmt_load(a)})"
        for a in unplanned
    ] or ["- none"]
    if outside:
        lines += ["", f"Completed, planned outside range ({len(outside)}):"]
        lines += [
            f"- {_day(a)} {a.get('type') or 'Unknown'} '{a.get('name') or 'unnamed'}' "
            f"(id {a.get('id')}, event {a.get('paired_event_id')}, "
            f"{_fmt_duration(a.get('moving_time'))}, load {_fmt_load(a)})"
            for a in outside
        ]
    availability = _format_availability(notes)
    if availability:
        lines += ["", "Training availability notes:"] + availability
    return "\n".join(lines)


@mcp.tool()
async def get_plan_compliance(
    start_date: str,
    end_date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Compare planned workouts with executed activities (read-only) for a date range.

    Planned workouts are calendar events with category WORKOUT. They are linked to
    activities via the event's paired_activity_id and/or the activity's paired_event_id.
    For each pair the planned vs. actual duration and training load are shown with the
    deviation in percent. Planned workouts in the past without a linked activity are listed
    as missed; unpaired workouts today or in the future are listed as upcoming (not
    missed); "today" is the server's local date. Activities without a linked planned
    workout are listed as unplanned; activities linked to a planned workout outside the
    queried range are listed separately as "planned outside range" (not unplanned and not
    counted in the completion percentage). An activity is never counted for two events.
    The completion percentage is completed / (completed + missed). NOTE events that set
    training availability, allowed sports or a maximum training time are listed as well.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        athlete_id: The Intervals.icu athlete ID (optional, will use ATHLETE_ID from .env if not provided)
        api_key: The Intervals.icu API key (optional, will use API_KEY from .env if not provided)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg
    range_error = _validate_range(start_date, end_date)
    if range_error:
        return range_error

    params = {"oldest": start_date, "newest": end_date}
    events = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events", api_key=api_key, params=params
    )
    if isinstance(events, dict) and "error" in events:
        return f"Error fetching events: {events.get('message')}"
    activities = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/activities", api_key=api_key, params=params
    )
    if isinstance(activities, dict) and "error" in activities:
        return f"Error fetching activities: {activities.get('message')}"

    events_list = [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []
    activities_list = (
        [a for a in activities if isinstance(a, dict)] if isinstance(activities, list) else []
    )
    if not events_list and not activities_list:
        return f"No events or activities found for athlete {athlete_id_to_use} in the specified date range."

    return _build_compliance_report(
        start_date, end_date, events_list, activities_list, _today().isoformat()
    )
