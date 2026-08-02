"""
Planning-related MCP tools for Intervals.icu.

ATP (Annual Training Plan) tools that adapt to the available time and the
athlete's current fitness level:
- create_atp_plan  fetches current CTL and auto-determines which phases are
                   needed, how long they should be, and posts them as NOTE
                   events on the Intervals.icu calendar.
- get_atp_plan     reads all phase notes from the calendar.
- get_atp_week_note  returns the phase note covering a specific week.
- get_planning_context  returns fitness + ATP note + events for weekly planning.
- add_race_event   adds a race event with priority A, B, or C.
"""

import asyncio
import re
from datetime import date, datetime, timedelta
from typing import Any

from intervals_mcp_server.api.client import make_intervals_request
from intervals_mcp_server.config import get_config
from intervals_mcp_server.mcp_instance import mcp  # noqa: F401
from intervals_mcp_server.utils.validation import resolve_athlete_id, validate_date

config = get_config()

# ---------------------------------------------------------------------------
# Phase definitions
# ---------------------------------------------------------------------------

_PHASES: dict[str, dict[str, Any]] = {
    "preparation": {
        "label": "Preparation",
        "color": "green",
        "focus": "Build general fitness. Establish aerobic base, strength and technique.",
        "intensity": "80% Z2, 15% sweet spot, 5% threshold.",
        "key_sessions": ["Long Z2 endurance rides", "Strength training", "Flexibility / technique"],
        "tss_factor": 0.60,
        "recovery_factor": 0.60,
    },
    "base": {
        "label": "Base",
        "color": "blue",
        "focus": "Strengthen the aerobic engine. High Z2 volume, sweet spot, threshold introduction.",
        "intensity": "65% Z2, 25% sweet spot, 10% threshold.",
        "key_sessions": ["Long endurance rides (3–5 h)", "2× sweet spot per week", "1× threshold interval"],
        "tss_factor": 0.80,
        "recovery_factor": 0.60,
    },
    "build": {
        "label": "Build",
        "color": "orange",
        "focus": "Race-specific qualities. Develop threshold, VO2max and anaerobic capacity.",
        "intensity": "40% Z2, 30% threshold, 30% VO2max / anaerobic.",
        "key_sessions": ["2× VO2max or threshold per week", "Long endurance ride", "Race simulation"],
        "tss_factor": 1.00,
        "recovery_factor": 0.60,
    },
    "peak": {
        "label": "Peak",
        "color": "red",
        "focus": "Get sharp for the race. Volume drops, intensity stays high. Taper.",
        "intensity": "50% Z2, 25% threshold, 25% VO2max — shorter intervals.",
        "key_sessions": ["Race-pace intervals", "Activation ride 2 days before race", "Rest day before race"],
        "tss_factor": 0.65,
        "recovery_factor": 0.60,
    },
    "race": {
        "label": "Race",
        "color": "red",
        "focus": "Perform at the A-race. Minimal training, full focus on racing and recovery.",
        "intensity": "Race + recovery rides.",
        "key_sessions": ["Activation ride the day before", "Race", "Active recovery afterwards"],
        "tss_factor": 0.50,
        "recovery_factor": 0.60,
    },
}

_ATP_PREFIX = "ATP — "
_TRAILING_PRIORITY_RE = re.compile(r'^(.*?)\s*\[([A-Ca-c])\]\s*$')

# Thresholds for aerobic basis assessment via 30-day power curve.
# Adjust these constants to tune how strict the basis check is.
_BASIS_20MIN_THRESHOLD: float = 0.85  # 20-min power must be >= ftp * this
_BASIS_60MIN_THRESHOLD: float = 0.75  # 60-min power must be >= ftp * this


def _is_atp_note(e: object) -> bool:
    return (
        isinstance(e, dict)
        and e.get("category") == "NOTE"  # type: ignore[union-attr]
        and (e.get("name") or "").startswith(_ATP_PREFIX)  # type: ignore[union-attr]
    )


# ---------------------------------------------------------------------------
# Power zone, strength, and multi-sport helpers
# ---------------------------------------------------------------------------

def _ftp_power_ranges(ftp: int) -> dict[str, str]:
    return {
        "sweet spot": f"{round(ftp * 0.88)}–{round(ftp * 0.93)} W",
        "threshold": f"{round(ftp * 0.95)}–{round(ftp * 1.05)} W",
        "vo2max": f"{round(ftp * 1.06)}–{round(ftp * 1.20)} W",
    }


def _annotate_sessions_with_power(sessions: list[str], ftp: int) -> list[str]:
    ranges = _ftp_power_ranges(ftp)
    result = []
    for s in sessions:
        s_lower = s.lower()
        for keyword, watt_range in ranges.items():
            if keyword in s_lower and " W" not in s:
                s = re.sub(r"\s+per week$", "", s, flags=re.IGNORECASE).strip()
                s = f"{s} ({watt_range})"
                break
        result.append(s)
    return result


def _build_strength_section(phase: str, strength: dict[str, Any]) -> list[str]:
    if phase == "race":
        return []

    sessions_per_week: int = strength.get("sessions_per_week", 0)
    duration: int = strength.get("session_duration_minutes", 0)
    equipment: list[str] = strength.get("equipment", [])
    all_blocks: list[dict[str, Any]] = strength.get("blocks", [])

    if phase == "peak":
        active_sessions = strength.get("peak_phase_sessions", sessions_per_week)
        peak_block_names: list[str] = strength.get("peak_phase_blocks", [])
        active_blocks = (
            [b for b in all_blocks if any(b.get("name", "").startswith(n) for n in peak_block_names)]
            if peak_block_names else all_blocks
        )
        header = f"Strength ({active_sessions}x/week, ~{duration} min — peak phase, reduced):"
        show_recovery_note = False
    else:
        active_sessions = sessions_per_week
        active_blocks = all_blocks
        eq_str = f", equipment: {', '.join(equipment)}" if equipment else ""
        header = f"Strength ({active_sessions}x/week, ~{duration} min{eq_str}):"
        show_recovery_note = "recovery_week_sessions" in strength

    lines = [header]
    for block in active_blocks:
        name = block.get("name", "")
        spw = block.get("sessions_per_week", "")
        exercises: list[str] = block.get("exercises", [])
        freq_str = f" ({spw}x/week)" if spw else ""
        lines.append(f"  {name}{freq_str}:")
        lines.append(f"    {', '.join(exercises)}")

    if show_recovery_note:
        rec_sessions: int = strength["recovery_week_sessions"]
        rec_blocks: list[str] = strength.get("recovery_week_blocks", [])
        block_str = ", ".join(rec_blocks) if rec_blocks else "all blocks"
        lines.append(f"  Recovery week: {block_str} only, {rec_sessions}x")

    return lines


_GENERIC_STRENGTH_PHASE: dict[str, str] = {
    "preparation": "2–3× per week. Core, functional strength. Keep sessions short (20–30 min).",
    "base": "2–3× per week. Core, functional strength. Keep sessions short (20–30 min).",
    "build": "2× per week. Maintenance. Core and stability only.",
    "peak": "2× per week, core/stability only. Skip heavy lifts.",
    "race": "No strength training — rest and race.",
}

_SPORT_PHASE_GUIDANCE: dict[str, dict[str, str]] = {
    "running": {
        "preparation": "2× per week, easy Z2 runs (30–45 min). Focus on running form and consistency.",
        "base": "2–3× per week, Z2 easy runs (45–60 min). Build aerobic base.",
        "build": "2–3× per week, include 1× tempo or interval run.",
        "peak": "2× per week, 1× race-pace strides + 1× easy run. Keep it fresh.",
        "race": "Easy jog (20–30 min) or rest. Save legs for racing.",
    },
    "swimming": {
        "preparation": "2× per week, technique drills (1,500–2,000 m). Stroke efficiency focus.",
        "base": "2–3× per week, aerobic sets (2,000–3,000 m). Technique + endurance.",
        "build": "2–3× per week, include CSS-pace threshold intervals (2,500–3,500 m).",
        "peak": "2× per week, short race-pace sets. Maintain feel for water.",
        "race": "1× activation swim (800–1,000 m easy). Race day: warm-up as planned.",
    },
}


def _build_extra_sports_sections(phase: str, sports: list[str]) -> list[str]:
    lines: list[str] = []
    for sport in sports:
        if sport == "cycling":
            continue
        if sport == "strength":
            guidance = _GENERIC_STRENGTH_PHASE.get(phase, "Follow strength plan.")
            lines += ["\nStrength this phase:", f"  {guidance}"]
            continue
        guidance = _SPORT_PHASE_GUIDANCE.get(sport, {}).get(phase)
        lines.append(f"\n{sport.capitalize()} this phase:")
        lines.append(f"  {guidance}" if guidance else "  Follow sport-specific plan; scale to available hours.")
    return lines


# ---------------------------------------------------------------------------
# Aerobic basis assessment via 30-day power curve
# ---------------------------------------------------------------------------

def _extract_30d_power(
    curve_result: Any,
) -> tuple[float | None, float | None]:
    """Extract 20-min (1200 s) and 60-min (3600 s) best power from a power-curves API response."""
    if not isinstance(curve_result, dict):
        return None, None
    curve_list: list[dict[str, Any]] = curve_result.get("list", [])
    if not curve_list:
        return None, None
    curve = curve_list[0]
    secs: list[int] = curve.get("secs", [])
    values: list[Any] = curve.get("values", [])
    sec_to_idx = {s: i for i, s in enumerate(secs)}

    def _get(duration: int) -> float | None:
        idx = sec_to_idx.get(duration)
        if idx is None or idx >= len(values):
            return None
        v = values[idx]
        return float(v) if v is not None else None

    return _get(1200), _get(3600)


def _assess_basis(
    power_20min: float | None,
    power_60min: float | None,
    ftp: int | None,
) -> tuple[bool | None, float | None, float | None, float | None]:
    """Determine whether the aerobic basis is present from the 30-day power curve.

    Returns (basis_present, ftp_ref, ratio_20min, ratio_60min).
    basis_present=None means insufficient data to make a determination.
    """
    if power_20min is None and power_60min is None:
        return None, None, None, None

    ftp_ref: float
    if ftp is not None:
        ftp_ref = float(ftp)
    elif power_20min is not None:
        ftp_ref = power_20min * 0.95  # standard 20-min proxy
    else:
        return None, None, None, None

    ratio_20 = power_20min / ftp_ref if power_20min is not None else None
    ratio_60 = power_60min / ftp_ref if power_60min is not None else None

    meets_20 = ratio_20 is not None and ratio_20 >= _BASIS_20MIN_THRESHOLD
    meets_60 = ratio_60 is not None and ratio_60 >= _BASIS_60MIN_THRESHOLD
    return meets_20 and meets_60, ftp_ref, ratio_20, ratio_60


# ---------------------------------------------------------------------------
# Phase auto-selection logic (relative to goal CTL, not absolute thresholds)
# ---------------------------------------------------------------------------


def _determine_phases(
    total_weeks: int,
    current_ctl: float,
    goal_ctl: float,
    basis_present: bool | None = None,
) -> list[tuple[str, int]]:
    """Return ordered (phase_name, weeks) based on available weeks, CTL gap, and aerobic basis.

    basis_present=True  → skip or shorten Base when power curve shows the athlete
                          has been riding at threshold level in the last 30 days.
    basis_present=False → add Base even when CTL ratio would normally skip it.
    basis_present=None  → fall back to CTL-gap-only logic (original behaviour).
    """
    if total_weeks <= 1:
        return [("race", total_weeks)]
    race_wks = 1
    remaining_after_race = total_weeks - race_wks
    peak_wks = 2 if remaining_after_race >= 4 else 1
    if peak_wks >= remaining_after_race:
        peak_wks = remaining_after_race
    remaining = total_weeks - peak_wks - race_wks

    tail = [("peak", peak_wks), ("race", race_wks)]

    if remaining <= 0:
        return tail

    ratio = current_ctl / max(goal_ctl, 1.0)

    # Short plans: always collapse to pure build regardless of basis signal
    if remaining <= 4:
        return [("build", remaining)] + tail

    # ---- Basis-aware branch ----------------------------------------
    if basis_present is True:
        # Powercurve is leading: basis confirmed → skip Base regardless of CTL gap
        return [("build", remaining)] + tail

    # ---- CTL-gap logic (basis absent or no powercurve data) --------
    if ratio >= 0.90:
        # Almost at goal CTL → straight to build
        return [("build", remaining)] + tail

    if ratio >= 0.70:
        # Moderate gap (70–90% of goal) → short base block + build
        base_wks = max(3, remaining // 3)
        build_wks = remaining - base_wks
        if build_wks < 3:
            return [("build", remaining)] + tail
        return [("base", base_wks), ("build", build_wks)] + tail

    # Large gap (< 70% of goal) → prep + base + build
    prep_wks = max(2, remaining // 5)
    base_wks = max(3, (remaining - prep_wks) * 2 // 3)
    build_wks = remaining - prep_wks - base_wks

    if build_wks < 3:
        prep_wks = 0
        base_wks = max(3, remaining // 2)
        build_wks = remaining - base_wks
        if build_wks < 3:
            return [("build", remaining)] + tail

    phases: list[tuple[str, int]] = []
    if prep_wks >= 2:
        phases.append(("preparation", prep_wks))
    if base_wks > 0:
        phases.append(("base", base_wks))
    if build_wks > 0:
        phases.append(("build", build_wks))
    return phases + tail


def _basis_decision_note(basis_present: bool | None, ratio: float) -> str:
    """Return a short descriptive prefix for the Decision line."""
    if basis_present is True:
        return "basis present (powercurve) → skipping Base"
    # Basis absent or no powercurve data — ratio is the deciding signal
    if ratio >= 0.90:
        return "no powercurve signal, CTL gap small"
    if ratio >= 0.70:
        return "no powercurve signal, moderate CTL gap"
    return "no powercurve signal, large CTL gap"


def _phase_selection_summary(
    current_ctl: float,
    goal_ctl: float,
    total_weeks: int,
    phase_list: list[tuple[str, int]],
    power_20min: float | None = None,
    power_60min: float | None = None,
    ftp_ref: float | None = None,
    ratio_20min: float | None = None,
    ratio_60min: float | None = None,
    basis_present: bool | None = None,
) -> str:
    """Return a multi-line phase-selection explanation for the tool summary."""
    goal_ctl_int = round(goal_ctl)
    current_ctl_int = round(current_ctl)
    gap = goal_ctl_int - current_ctl_int
    ratio = current_ctl / max(goal_ctl, 1.0)
    phase_seq = " → ".join(_PHASES[name]["label"] for name, _ in phase_list)

    lines = [
        f"  Current CTL: {current_ctl_int} (goal: {goal_ctl_int}, gap: {gap} pts, ratio: {round(ratio * 100)}%)",
    ]

    # Power curve line
    if power_20min is None and power_60min is None:
        lines.append("  Power curve (last 30 days): no recent data (last activity > 30 days ago)")
    else:
        ftp_str = f" | FTP ref: {round(ftp_ref)}W" if ftp_ref is not None else ""
        p20_str = (
            f"20min = {round(power_20min)}W ({round(ratio_20min * 100)}% of FTP ref)"
            if power_20min is not None and ratio_20min is not None
            else "20min = n/a"
        )
        p60_str = (
            f"60min = {round(power_60min)}W ({round(ratio_60min * 100)}% of FTP ref)"
            if power_60min is not None and ratio_60min is not None
            else "60min = n/a"
        )
        lines.append(f"  Power curve (last 30 days): {p20_str}, {p60_str}{ftp_str}")

    # Basis assessment line
    if basis_present is True:
        lines.append("  Basis assessment: PRESENT — strong 20min and 60min values in last 30 days")
    elif basis_present is False:
        if power_20min is None and power_60min is None:
            lines.append("  Basis assessment: ABSENT — no recent riding detected")
        else:
            lines.append(
                f"  Basis assessment: ABSENT — 20min/60min below threshold "
                f"(need ≥{round(_BASIS_20MIN_THRESHOLD * 100)}% / ≥{round(_BASIS_60MIN_THRESHOLD * 100)}% of FTP ref)"
            )
    else:
        lines.append("  Basis assessment: N/A — no power curve data, using CTL-gap only")

    note = _basis_decision_note(basis_present, ratio)
    lines.append(f"  Decision: {note} → {phase_seq}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Note content builders
# ---------------------------------------------------------------------------

def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _weeks_in(start: date, end: date) -> int:
    return max(1, ((end - start).days + 1 + 6) // 7)



def _week_tss(phase: str, goal_tss: int, week: int, cycle: int, load_week_idx: dict[int, int]) -> str:
    p = _PHASES[phase]
    factor = p["tss_factor"]
    if week % cycle == 0:
        tss = max(50, round(goal_tss * factor * p["recovery_factor"] / 50) * 50)
        return f"~{tss} TSS  ← recovery week"
    idx = load_week_idx.get(week, 0)
    prog = 0.85 + 0.15 * (idx / max(len(load_week_idx) - 1, 1))
    tss = max(50, round(goal_tss * factor * prog / 50) * 50)
    return f"~{tss} TSS"


def _build_phase_note(
    phase: str,
    phase_num: int,
    total_phases: int,
    start: date,
    end: date,
    cycle: int,
    goal_tss: int,
    race_name: str,
    race_date: date,
    phase_races: list[dict],
    ftp: int | None = None,
    strength_training: dict[str, Any] | None = None,
    sports: list[str] | None = None,
    fixed_weekly_events: list[str] | None = None,
) -> str:
    p = _PHASES[phase]
    total_wks = _weeks_in(start, end)
    load_week_idx = {w: i for i, w in enumerate(w for w in range(1, total_wks + 1) if w % cycle != 0)}

    multi_sport = sports is not None and len([s for s in sports if s != "strength"]) > 1
    sessions_label = "Key cycling sessions per week:" if multi_sport else "Key sessions per week:"

    key_sessions = p["key_sessions"]
    if ftp is not None:
        key_sessions = _annotate_sessions_with_power(key_sessions, ftp)

    lines = [
        f"Phase {phase_num}/{total_phases}: {p['label']}",
        f"Period: {start} – {end} ({total_wks} weeks)",
        f"Goal: {p['focus']}",
        f"Intensity: {p['intensity']}",
        "",
        sessions_label,
        *[f"  • {s}" for s in key_sessions],
        "",
        "Weekly schedule:",
    ]
    for w in range(1, total_wks + 1):
        w_start = start + timedelta(weeks=w - 1)
        w_end = min(w_start + timedelta(days=6), end)
        lines.append(f"  Week {w} ({w_start} – {w_end}): {_week_tss(phase, goal_tss, w, cycle, load_week_idx)}")

    if sports:
        extra_sports = [s for s in sports if s != "strength" or strength_training is None]
        lines.extend(_build_extra_sports_sections(phase, extra_sports))

    if strength_training:
        strength_lines = _build_strength_section(phase, strength_training)
        if strength_lines:
            lines.append("")
            lines.extend(strength_lines)

    if fixed_weekly_events:
        lines.append("")
        lines.append("Fixed weekly events (do not modify):")
        for ev in fixed_weekly_events:
            lines.append(f"  • {ev}")

    lines += ["", f"A-race: {race_name} ({race_date})"]
    if phase_races:
        lines.append("Races in this phase:")
        for r in phase_races:
            lines.append(f"  • {r['date']} — {r['name']} [{r.get('priority', 'C')}]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def create_atp_plan(
    race_date: str,
    race_name: str,
    goal_ctl: int,
    recovery_cycle: int = 4,
    additional_races: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
    ftp: int | None = None,
    weekly_hours: float | None = None,
    sports: list[str] | None = None,
    strength_training: dict[str, Any] | None = None,
    fixed_weekly_events: list[str] | None = None,
) -> str:
    """Create an ATP (Annual Training Plan) in Intervals.icu for a goal race.

    Fetches current CTL, compares it to goal_ctl, and automatically determines
    which phases are needed and how long they should be. The bigger the gap
    between current and goal CTL, the more base-building phases are added.

    Phase selection (based on current CTL as % of goal CTL):
    - >= 90% of goal: already close → Build → Peak → Race
    - 70–90% of goal: moderate gap → Base → Build → Peak → Race
    - < 70% of goal:  large gap   → Preparation → Base → Build → Peak → Race

    goal_ctl reference values (CTL needed at race day):
    - Finish a sportive / gran fondo:       50–70
    - Club-level amateur racer:             70–90
    - Competitive amateur / cat. 3–4:       90–110
    - Semi-pro / UCI U23:                  100–130
    - Pro continental / WorldTour:         130+

    Each phase is posted as a NOTE event spanning its full date range on the
    Intervals.icu calendar. The note contains training focus, intensity split,
    weekly TSS targets, key sessions, and recovery-week schedule.

    Args:
        race_date: Date of the A-race in YYYY-MM-DD format
        race_name: Name of the A-race (e.g. "Tour of Flanders")
        goal_ctl: Target CTL (fitness) needed at race day — see reference above
        recovery_cycle: Recovery week every N weeks — 3 for older/less experienced
                        athletes, 4 for younger/experienced athletes (default 4)
        additional_races: Optional B/C races, one per line as
                          "YYYY-MM-DD Name [A/B/C]"
                          e.g. "2026-03-21 Dwars door Vlaanderen [C]"
        athlete_id: The Intervals.icu athlete ID (optional)
        api_key: The Intervals.icu API key (optional)
        ftp: FTP in watts (optional). When provided, power targets in phase notes
             are made concrete: sweet spot ftp×0.88–0.93, threshold ftp×0.95–1.05,
             VO2max ftp×1.06–1.20.
        weekly_hours: Available training hours per week (optional). Used to
                      validate TSS targets; if the goal exceeds ~65 TSS/h the
                      peak-week target is capped to what is achievable.
        sports: Sports trained alongside cycling (optional). Supported:
                "cycling", "running", "swimming", "strength". Cycling stays
                primary. With 3+ non-strength sports, cycling TSS is reduced
                by 10% to keep total load manageable.
        strength_training: Detailed weekly strength routine (optional). Object
                           with blocks, exercises, equipment. Automatically
                           scaled for recovery weeks and the peak phase.
                           No strength in the race phase.
        fixed_weekly_events: Recurring events that must not be overridden
                             (optional). Listed in each phase note so the
                             weekly planner can account for them.
                             e.g. ["Tuesday evening criterium (Papendal)"]
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    try:
        validate_date(race_date)
        race_dt = date.fromisoformat(race_date)
    except ValueError as e:
        return f"Error in race_date: {e}"

    if goal_ctl < 1:
        return "Error: goal_ctl must be at least 1."

    if recovery_cycle not in (3, 4):
        return "Error: recovery_cycle must be 3 or 4."

    if ftp is not None and ftp < 50:
        return "Error: ftp must be at least 50 W."

    if weekly_hours is not None and weekly_hours <= 0:
        return "Error: weekly_hours must be a positive number."

    _valid_sports = {"cycling", "running", "swimming", "strength"}
    if sports is not None:
        invalid = [s for s in sports if s.lower() not in _valid_sports]
        if invalid:
            return f"Error: unsupported sports: {invalid}. Supported: cycling, running, swimming, strength."
        sports = [s.lower() for s in sports]

    today = date.today()
    if race_dt < today:
        return f"Error: race_date {race_date} is in the past. Provide a future date."

    days_ahead = (7 - today.weekday()) % 7 or 7  # next Monday, never today
    today_monday = today + timedelta(days=days_ahead)
    race_monday = _monday_of(race_dt)
    total_weeks = max(1, (race_monday - today_monday).days // 7 + 1)

    # Fetch CTL (wellness) and 30-day power curve in parallel
    curve_start = (today - timedelta(days=30)).isoformat()
    curve_end = today.isoformat()
    wellness_result, curve_result = await asyncio.gather(
        make_intervals_request(
            url=f"/athlete/{athlete_id_to_use}/wellness",
            api_key=api_key,
            params={
                "oldest": (today - timedelta(days=7)).isoformat(),
                "newest": today.isoformat(),
            },
        ),
        make_intervals_request(
            url=f"/athlete/{athlete_id_to_use}/power-curves",
            api_key=api_key,
            params={
                "curves": [f"r.{curve_start}.{curve_end}"],
                "type": "Ride",
                "includeRanks": False,
            },
        ),
        return_exceptions=True,
    )

    current_ctl: float = 30.0  # fallback if no data
    ctl_source = "unknown (no wellness data)"
    if isinstance(wellness_result, list) and wellness_result:
        for entry in reversed(wellness_result):
            if isinstance(entry, dict) and entry.get("ctl") is not None:
                current_ctl = float(entry["ctl"])
                ctl_source = f"{round(current_ctl, 1)} (from wellness {entry.get('id', '')})"
                break

    # Assess aerobic basis from power curve; fall back gracefully on any error
    power_20min: float | None = None
    power_60min: float | None = None
    if not isinstance(curve_result, Exception):
        power_20min, power_60min = _extract_30d_power(curve_result)
    basis_present, ftp_ref, ratio_20min, ratio_60min = _assess_basis(power_20min, power_60min, ftp)

    # Weekly TSS in peak build weeks ≈ goal_ctl × 7
    goal_weekly_tss = max(50, round(goal_ctl * 7 / 50) * 50)

    # Multi-sport: reduce cycling TSS by 10% when 3+ non-strength sports
    tss_sport_note = ""
    if sports is not None:
        active_sport_count = len([s for s in sports if s != "strength"])
        if active_sport_count >= 3:
            original_tss = goal_weekly_tss
            goal_weekly_tss = max(50, round(goal_weekly_tss * 0.90 / 50) * 50)
            tss_sport_note = f" (reduced from {original_tss} for multi-sport load)"

    # Weekly hours: cap TSS if goal exceeds what is achievable (~65 TSS/h)
    tss_hours_note = ""
    if weekly_hours is not None:
        max_feasible_tss = max(50, round(weekly_hours * 65 / 50) * 50)
        if goal_weekly_tss > max_feasible_tss:
            original_tss = goal_weekly_tss
            goal_weekly_tss = max_feasible_tss
            tss_hours_note = f" (capped from {original_tss} to fit {weekly_hours}h/week)"

    # Parse additional races
    extra_races: list[dict] = []
    if additional_races:
        for line in additional_races.strip().splitlines():
            if not line.strip():
                continue
            parts = line.strip().split(None, 1)  # split on first whitespace: [date, rest]
            if len(parts) != 2:
                return f"Error: malformed additional_races line '{line.strip()}'. Expected format: 'YYYY-MM-DD Race name [A/B/C]'."
            raw_date, rest = parts[0], parts[1].strip()
            try:
                validate_date(raw_date)
            except ValueError:
                return f"Error: invalid date '{raw_date}' in additional_races. Use YYYY-MM-DD."
            m = _TRAILING_PRIORITY_RE.match(rest)
            if m:
                name_part, priority = m.group(1).strip(), m.group(2).upper()
            else:
                name_part, priority = rest, "C"
            extra_races.append({"date": raw_date, "name": name_part, "priority": priority})

    # Fetch existing ATP notes now; delete them only after new ones are created
    plan_end = _monday_of(race_dt) + timedelta(days=6)
    existing = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events",
        api_key=api_key,
        params={"oldest": today_monday.isoformat(), "newest": plan_end.isoformat()},
    )
    old_ids = [
        ev.get("id") for ev in (existing if isinstance(existing, list) else [])
        if _is_atp_note(ev) and isinstance(ev, dict) and ev.get("id")
    ]

    _sem = asyncio.Semaphore(3)

    async def _delete(ev_id: str) -> None:
        async with _sem:
            await make_intervals_request(
                url=f"/athlete/{athlete_id_to_use}/events/{ev_id}",
                api_key=api_key,
                method="DELETE",
            )

    # Determine phases (basis_present=None falls back to CTL-gap-only logic)
    phase_list = _determine_phases(total_weeks, current_ctl, float(goal_ctl), basis_present)
    phase_selection = _phase_selection_summary(
        current_ctl=current_ctl,
        goal_ctl=float(goal_ctl),
        total_weeks=total_weeks,
        phase_list=phase_list,
        power_20min=power_20min,
        power_60min=power_60min,
        ftp_ref=ftp_ref,
        ratio_20min=ratio_20min,
        ratio_60min=ratio_60min,
        basis_present=basis_present,
    )

    # Calculate date ranges (forward from today)
    cursor = today_monday
    phase_ranges: list[dict[str, Any]] = []
    for phase_name, wks in phase_list:
        p_start = cursor
        p_end = cursor + timedelta(weeks=wks) - timedelta(days=1)
        if phase_name == "race":
            p_end = race_monday + timedelta(days=6)
        phase_ranges.append({"name": phase_name, "start": p_start, "end": p_end, "weeks": wks})
        cursor = p_end + timedelta(days=1)

    total_phases = len(phase_ranges)

    # Build all event payloads up front (pure computation, no I/O)
    phase_events: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for i, ph in enumerate(phase_ranges, start=1):
        phase_races = [r for r in extra_races if ph["start"].isoformat() <= r["date"] <= ph["end"].isoformat()]
        description = _build_phase_note(
            phase=ph["name"],
            phase_num=i,
            total_phases=total_phases,
            start=ph["start"],
            end=ph["end"],
            cycle=recovery_cycle,
            goal_tss=goal_weekly_tss,
            race_name=race_name,
            race_date=race_dt,
            phase_races=phase_races,
            ftp=ftp,
            strength_training=strength_training,
            sports=sports,
            fixed_weekly_events=fixed_weekly_events,
        )
        event_data: dict[str, Any] = {
            "category": "NOTE",
            "name": f"ATP — {_PHASES[ph['name']]['label']}",
            "description": description,
            "start_date_local": ph["start"].isoformat() + "T00:00:00",
            "end_date_local": (ph["end"] + timedelta(days=1)).isoformat() + "T00:00:00",
            "color": _PHASES[ph["name"]]["color"],
        }
        phase_events.append((ph, event_data))

    async def _post_phase(ph: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        async with _sem:
            return await make_intervals_request(
                url=f"/athlete/{athlete_id_to_use}/events",
                api_key=api_key,
                data=data,
                method="POST",
            )

    post_results = await asyncio.gather(
        *(_post_phase(ph, ev) for ph, ev in phase_events),
        return_exceptions=True,
    )

    # On any failure: rollback newly created events (old notes are still intact)
    created_ids = [
        r["id"] for r in post_results
        if isinstance(r, dict) and "id" in r and "error" not in r
    ]
    failed = [r for r in post_results if isinstance(r, Exception) or (isinstance(r, dict) and "error" in r)]
    if failed:
        await asyncio.gather(*(_delete(ev_id) for ev_id in created_ids), return_exceptions=True)
        f = failed[0]
        err_msg = (f.get("message") or f.get("error") or str(f)) if isinstance(f, dict) else str(f)
        return f"Error creating ATP plan (rolled back, existing plan preserved): {err_msg}"

    # All POSTs succeeded — now safe to remove the old notes
    if old_ids:
        delete_results = await asyncio.gather(*(_delete(ev_id) for ev_id in old_ids), return_exceptions=True)
        delete_failures = [r for r in delete_results if isinstance(r, Exception)]
        if delete_failures:
            return (
                f"ATP plan created but {len(delete_failures)} old note(s) could not be deleted "
                f"(may cause duplicates): {delete_failures[0]}"
            )

    posted_lines: list[str] = []
    for (ph, _), _ in zip(phase_events, post_results):
        label = _PHASES[ph["name"]]["label"]
        posted_lines.append(f"  ✓ {label}: {ph['start']} – {ph['end']} ({ph['weeks']} wk)")

    phase_names = " → ".join(_PHASES[ph["name"]]["label"] for ph in phase_ranges)
    summary = [
        f"ATP created for {race_name} ({race_date})",
        f"Period: {today_monday} – {race_monday + timedelta(days=6)} ({total_weeks} weeks)",
        f"Current CTL: {ctl_source}",
        f"Goal CTL: {goal_ctl}  →  Peak week TSS target: ~{goal_weekly_tss}{tss_sport_note}{tss_hours_note}",
        f"Phase selection:\n{phase_selection}",
        f"Phases: {phase_names}",
        f"Recovery cycle: every {recovery_cycle} weeks",
    ]
    if sports:
        summary.append(f"Sports: {', '.join(sports)}")
    if ftp is not None:
        summary.append(f"FTP: {ftp} W")
    if weekly_hours is not None:
        summary.append(f"Weekly hours: {weekly_hours} h")
    if fixed_weekly_events:
        summary.append(f"Fixed events: {'; '.join(fixed_weekly_events)}")
    summary += ["", "Posted to calendar:"] + posted_lines

    return "\n".join(summary)


@mcp.tool()
async def get_atp_plan(
    start_date: str | None = None,
    end_date: str | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Read the current ATP plan from the Intervals.icu calendar.

    Returns all ATP phase NOTE events in the given date range with their
    training guidelines — a full season overview.

    Args:
        start_date: Start of range in YYYY-MM-DD format
                    (optional, defaults to 3 months ago)
        end_date: End of range in YYYY-MM-DD format
                  (optional, defaults to 18 months from today)
        athlete_id: The Intervals.icu athlete ID (optional)
        api_key: The Intervals.icu API key (optional)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    today = date.today()
    if not start_date:
        start_date = (today - timedelta(days=90)).isoformat()
    if not end_date:
        end_date = (today + timedelta(days=550)).isoformat()

    try:
        validate_date(start_date)
        validate_date(end_date)
    except ValueError as e:
        return f"Error: {e}"

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events",
        api_key=api_key,
        params={"oldest": start_date, "newest": end_date},
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching ATP plan: {result.get('message') or result.get('error') or str(result)}"

    events = result if isinstance(result, list) else []
    notes = [
        e for e in events
        if _is_atp_note(e)
    ]

    if not notes:
        return (
            f"No ATP notes found between {start_date} and {end_date}. "
            "Use create_atp_plan to create a plan."
        )

    lines = [f"ATP overview ({start_date} – {end_date})\n"]
    for note in notes:
        name = note.get("name", "")
        s = (note.get("start_date_local") or "")[:10]
        e_end_raw = (note.get("end_date_local") or note.get("start_date_local") or "")[:10]
        try:
            e_end = (date.fromisoformat(e_end_raw) - timedelta(days=1)).isoformat() if e_end_raw else ""
        except ValueError:
            e_end = e_end_raw
        desc = note.get("description", "")
        lines.append(f"## {name}  ({s} – {e_end})")
        if desc:
            lines.append(desc)
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_atp_week_note(
    week_date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get the ATP phase note covering the week that contains week_date.

    Returns which phase the week falls in and its training guidelines
    (focus, intensity, TSS target). Use this before planning a week's workouts.

    Args:
        week_date: Any date within the target week in YYYY-MM-DD format
        athlete_id: The Intervals.icu athlete ID (optional)
        api_key: The Intervals.icu API key (optional)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    try:
        validate_date(week_date)
    except ValueError as e:
        return f"Error: {e}"

    monday = _monday_of(date.fromisoformat(week_date))
    sunday = monday + timedelta(days=6)

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events",
        api_key=api_key,
        params={"oldest": monday.isoformat(), "newest": sunday.isoformat()},
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error fetching events: {result.get('message')}"

    events = result if isinstance(result, list) else []
    notes = [
        e for e in events
        if _is_atp_note(e)
    ]

    if not notes:
        return (
            f"No ATP note found for week {monday} – {sunday}. "
            "Use create_atp_plan to structure the season."
        )

    lines = [f"ATP for week {monday} – {sunday}:\n"]
    for note in notes:
        name = note.get("name", "")
        desc = note.get("description", "")
        lines.append(f"### {name}\n{desc}" if name else desc)

    return "\n\n".join(lines)


@mcp.tool()
async def get_planning_context(
    week_date: str,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Get full planning context for a training week.

    Returns in one call:
    - The ATP phase note for this week (focus, TSS target, key sessions)
    - Current fitness: CTL, ATL, TSB, HRV, ramp rate
    - Workouts already scheduled this week
    - Upcoming races (next 120 days)

    Use this before planning the week's workouts, then use add_or_update_event
    to post each day's workout.

    Args:
        week_date: Any date within the target week in YYYY-MM-DD format
        athlete_id: The Intervals.icu athlete ID (optional)
        api_key: The Intervals.icu API key (optional)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    try:
        validate_date(week_date)
    except ValueError as e:
        return f"Error: {e}"

    monday = _monday_of(date.fromisoformat(week_date))
    sunday = monday + timedelta(days=6)
    today = date.today()

    _raw = await asyncio.gather(
        make_intervals_request(
            url=f"/athlete/{athlete_id_to_use}/wellness",
            api_key=api_key,
            params={
                "oldest": (today - timedelta(days=14)).isoformat(),
                "newest": today.isoformat(),
            },
        ),
        make_intervals_request(
            url=f"/athlete/{athlete_id_to_use}/events",
            api_key=api_key,
            params={"oldest": monday.isoformat(), "newest": sunday.isoformat()},
        ),
        make_intervals_request(
            url=f"/athlete/{athlete_id_to_use}/events",
            api_key=api_key,
            params={
                "oldest": today.isoformat(),
                "newest": (today + timedelta(days=120)).isoformat(),
            },
        ),
        return_exceptions=True,
    )
    _fallback: list[Any] = []
    _api_warnings: list[str] = []
    _labels = ("wellness", "week events", "upcoming races")

    def _is_failed(item: Any) -> bool:
        return isinstance(item, Exception) or (isinstance(item, dict) and "error" in item)

    def _warn_msg(item: Any) -> str:
        if isinstance(item, dict):
            return item.get("message") or item.get("error") or str(item)
        return str(item)

    for _label, _raw_item in zip(_labels, _raw):
        if isinstance(_raw_item, asyncio.CancelledError):
            raise _raw_item
        if _is_failed(_raw_item):
            _api_warnings.append(f"  • {_label}: {_warn_msg(_raw_item)}")
    wellness_result: dict[str, Any] | list[dict[str, Any]] = (
        _raw[0] if not _is_failed(_raw[0]) else _fallback
    )
    week_events: dict[str, Any] | list[dict[str, Any]] = (
        _raw[1] if not _is_failed(_raw[1]) else _fallback
    )
    races_result: dict[str, Any] | list[dict[str, Any]] = (
        _raw[2] if not _is_failed(_raw[2]) else _fallback
    )

    week_list = week_events if isinstance(week_events, list) else []
    sections: list[str] = [f"# Planning context: week {monday} – {sunday}\n"]

    # ATP phase note
    sections.append("## ATP phase")
    atp_notes = [
        e for e in week_list
        if _is_atp_note(e)
    ]
    if atp_notes:
        for n in atp_notes:
            name = n.get("name", "")
            desc = n.get("description", "")
            sections.append(f"**{name}**\n{desc}" if name else desc)
    else:
        sections.append(
            "No ATP note for this week. Use create_atp_plan to structure the season."
        )

    # Fitness
    sections.append("\n## Current fitness (last 14 days)")
    if isinstance(wellness_result, list) and wellness_result:
        latest = next(
            (e for e in reversed(wellness_result) if isinstance(e, dict) and e.get("ctl") is not None),
            None,
        )
        if latest:
            ctl = latest.get("ctl")
            atl = latest.get("atl")
            tsb = round(ctl - atl, 1) if ctl is not None and atl is not None else None
            form = ""
            if tsb is not None:
                form = " (fresh)" if tsb > 10 else (" (fatigued)" if tsb < -10 else " (neutral)")
            lines = []
            if ctl is not None:
                lines.append(f"CTL (fitness): {round(ctl, 1)}")
            if atl is not None:
                lines.append(f"ATL (fatigue): {round(atl, 1)}")
            if tsb is not None:
                lines.append(f"TSB (form): {tsb}{form}")
            hrv = latest.get("hrv")
            if hrv is not None:
                lines.append(f"HRV: {hrv}")
            ramp = latest.get("rampRate")
            if ramp is not None:
                lines.append(f"Ramp rate: {round(ramp, 1)} CTL/week")
            sections.append("\n".join(lines))
        else:
            sections.append("No CTL/ATL data available.")
    else:
        sections.append("No wellness data available.")

    # Planned workouts
    sections.append("\n## Planned workouts this week")
    workouts = [e for e in week_list if isinstance(e, dict) and e.get("category") == "WORKOUT"]
    if workouts:
        for w in workouts:
            d = (w.get("start_date_local") or "")[:10]
            name = w.get("name", "workout")
            wtype = w.get("type", "")
            mt = w.get("moving_time")
            dur = f" ({int(mt) // 60} min)" if mt else ""
            sections.append(f"- {d} [{wtype}] {name}{dur}")
    else:
        sections.append("No workouts scheduled yet.")

    # Upcoming races
    sections.append("\n## Upcoming races (120 days)")
    if isinstance(races_result, list) and races_result:
        races = [e for e in races_result if isinstance(e, dict) and e.get("category") in ("RACE_A", "RACE_B", "RACE_C")]
        if races:
            for r in races:
                d = (r.get("start_date_local") or "")[:10]
                name = r.get("name", "race")
                cat = r.get("category", "")
                sections.append(f"- {d}: {name} [{cat}]")
        else:
            sections.append("No races scheduled.")
    else:
        sections.append("No races scheduled.")

    if _api_warnings:
        sections.append("\n## ⚠ API fetch warnings (data may be incomplete)")
        sections.extend(_api_warnings)

    return "\n".join(sections)


@mcp.tool()
async def add_race_event(
    name: str,
    race_date: str,
    priority: str = "A",
    start_time: str = "10:00:00",
    sport: str = "Ride",
    duration_minutes: int | None = None,
    distance_km: float | None = None,
    expected_tss: int | None = None,
    athlete_id: str | None = None,
    api_key: str | None = None,
) -> str:
    """Add a race event to the Intervals.icu calendar.

    Creates an event with category RACE_A, RACE_B, or RACE_C. The priority
    determines how the ATP and HRV coach treat the event:
    - A: most important race — full taper, no heavy training the week before
    - B: important race — reduce load 2 days before
    - C: training race — treat as a hard training day

    Args:
        name: Name of the race (e.g. "Tour of Flanders")
        race_date: Date of the race in YYYY-MM-DD format
        priority: Race priority — A, B, or C (default A)
        start_time: Start time in HH:MM:SS format (default 10:00:00)
        sport: Sport type — Ride, Run, Swim, etc. (default Ride)
        duration_minutes: Expected race duration in minutes (optional)
        distance_km: Expected race distance in km (optional)
        expected_tss: Expected Training Stress Score for the race (optional)
        athlete_id: The Intervals.icu athlete ID (optional)
        api_key: The Intervals.icu API key (optional)
    """
    athlete_id_to_use, error_msg = resolve_athlete_id(athlete_id, config.athlete_id)
    if error_msg:
        return error_msg

    try:
        validate_date(race_date)
    except ValueError as e:
        return f"Error in race_date: {e}"

    priority_upper = priority.strip().upper()
    if priority_upper not in ("A", "B", "C"):
        return "Error: priority must be A, B, or C."

    try:
        datetime.strptime(start_time, "%H:%M:%S")
    except ValueError:
        return "Error: start_time must be in HH:MM:SS format (e.g. '10:00:00')."

    event_data: dict[str, Any] = {
        "category": f"RACE_{priority_upper}",
        "type": sport,
        "name": name,
        "start_date_local": f"{race_date}T{start_time}",
    }

    if duration_minutes is not None:
        event_data["moving_time"] = duration_minutes * 60
    if distance_km is not None:
        event_data["distance"] = round(distance_km * 1000)
    if expected_tss is not None:
        event_data["icu_training_load"] = expected_tss

    result = await make_intervals_request(
        url=f"/athlete/{athlete_id_to_use}/events",
        api_key=api_key,
        data=event_data,
        method="POST",
    )

    if isinstance(result, dict) and "error" in result:
        return f"Error adding race: {result.get('message') or result.get('error') or str(result)}"

    if not isinstance(result, dict):
        return f"Unexpected response adding race: {result}"

    event_id = result.get("id")
    saved_category = result.get("category", "not returned")
    id_str = f" (id: {event_id})" if event_id else ""
    category_ok = saved_category == f"RACE_{priority_upper}"
    category_note = "" if category_ok else f" — WARNING: API saved category as '{saved_category}', expected 'RACE_{priority_upper}'"
    return f"Race '{name}' added on {race_date} [RACE_{priority_upper}]{id_str}.{category_note}"
