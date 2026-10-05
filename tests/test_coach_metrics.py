"""
Unit tests for the pure coach_metrics module (no network).
"""

# pylint: disable=missing-function-docstring

import json
import math
import pathlib
import sys
from datetime import date

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from intervals_mcp_server import coach_metrics as cm  # pylint: disable=wrong-import-position  # noqa: E402
from tests.coach_fixtures import END, activity, athlete, days_before, power_zones, realistic_scenario, wellness  # pylint: disable=wrong-import-position  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_sport_family_merges_ride_types():
    assert cm.sport_family("Ride") == cm.RAD
    assert cm.sport_family("VirtualRide") == cm.RAD
    assert cm.sport_family("Run") == cm.LAUF
    assert cm.sport_family("Swim") == cm.SCHWIMMEN
    assert cm.sport_family("WeightTraining") == cm.KRAFT
    assert cm.sport_family("Yoga") == cm.SONSTIGE
    assert cm.sport_family(None) == cm.SONSTIGE


def test_rounding_avoids_negative_zero():
    assert str(cm._r(-0.04, 1)) == "0.0"  # pylint: disable=protected-access
    assert cm._r(-0.04, 0) == 0  # pylint: disable=protected-access
    assert cm._r(None) is None  # pylint: disable=protected-access


def test_daily_loads_zero_fills_days_without_training():
    acts = [activity(END, load=50), activity(END, load=30, hour=18), activity(days_before(END, 2), load=20)]
    assert cm.daily_loads(acts, END, 4) == [0.0, 20.0, 0.0, 80.0]


def test_daily_loads_treats_missing_load_as_zero():
    acts = [activity(END, load=None), activity(END, load=-5)]
    assert cm.daily_loads(acts, END, 1) == [0.0]


def test_monotony_undefined_cases():
    assert cm.monotony([]) is None
    assert cm.monotony([50.0]) is None
    assert cm.monotony([0.0] * 7) is None  # no training
    assert cm.monotony([60.0] * 7) is None  # SD = 0 -> division by zero avoided


def test_monotony_includes_rest_days():
    daily = [100.0, 0.0, 100.0, 0.0, 100.0, 0.0, 100.0]
    expected = (400 / 7) / math.sqrt(sum((x - 400 / 7) ** 2 for x in daily) / 6)
    assert cm.monotony(daily) == pytest.approx(expected)


def test_wellness_by_day_accepts_list_and_dict():
    record = wellness(END)
    assert cm.wellness_by_day([record])[END] is record
    assert END in cm.wellness_by_day({END.isoformat(): {"hrv": 70}})
    assert not cm.wellness_by_day(None)


def test_iso_week_label_crosses_year_boundary():
    assert cm.iso_week_label(date(2027, 1, 1)) == "2026-W53"
    assert cm.iso_week_label(date(2027, 1, 4)) == "2027-W01"


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def test_load_metrics_acwr_monotony_strain():
    acts = [activity(days_before(END, offset), load=100) for offset in range(28) if offset % 2 == 0]
    result = cm.load_metrics(acts, END)
    assert result["load_7d"] == 400
    assert result["load_28d"] == 1400
    assert result["acwr"] == round(400 / (1400 / 4), 2)
    mono = cm.monotony([100.0, 0.0, 100.0, 0.0, 100.0, 0.0, 100.0])
    assert mono is not None
    assert result["monotony"] == round(mono, 2)
    assert result["strain"] == round(400 * mono)
    assert result["monotony_note"] is None


def test_load_metrics_empty_period_avoids_division_by_zero():
    result = cm.load_metrics([], END)
    assert result["acwr"] is None
    assert result["monotony"] is None
    assert result["monotony_note"] == "no_load"
    assert result["strain"] is None
    assert result["primary_sport"] is None
    assert result["deload"] is False


def test_load_metrics_identical_daily_load():
    acts = [activity(days_before(END, offset), load=60) for offset in range(7)]
    result = cm.load_metrics(acts, END)
    assert result["monotony"] is None
    assert result["monotony_note"] == "no_variation"
    assert result["strain"] is None


def test_primary_sport_monotony_removes_cross_training_floor():
    acts = []
    for offset in range(7):
        acts.append(activity(days_before(END, offset), "WeightTraining", load=15, hour=18))
    for offset, load in [(0, 200), (1, 50), (3, 120), (5, 60)]:
        acts.append(activity(days_before(END, offset), "Ride", load=load))
    result = cm.load_metrics(acts, END)
    assert result["primary_sport"] == cm.RAD
    assert result["primary_monotony"] is not None
    assert result["effective_monotony"] == result["primary_monotony"]
    assert result["primary_monotony"] < result["monotony"]


def test_primary_monotony_needs_three_active_days():
    acts = [activity(days_before(END, 0), load=200), activity(days_before(END, 3), load=100)]
    acts += [activity(days_before(END, offset), "Run", load=10) for offset in range(7)]
    result = cm.load_metrics(acts, END)
    assert result["primary_sport"] == cm.RAD
    assert result["primary_monotony"] is None
    assert result["effective_monotony"] == result["monotony"]


def test_deload_detected():
    acts = [activity(days_before(END, offset), load=100) for offset in range(7, 28)]
    acts += [activity(days_before(END, offset), load=40) for offset in range(7)]
    assert cm.load_metrics(acts, END)["deload"] is True


# ---------------------------------------------------------------------------
# Fitness
# ---------------------------------------------------------------------------


def test_fitness_uses_api_values_and_tsb():
    days = {END: wellness(END, ctl=101.23, atl=93.9, ramp=-4.9)}
    result = cm.fitness_status(days, [], END)
    assert result == {"ctl": 101.2, "atl": 93.9, "tsb": 7.3, "ramp": -4.9, "src": "api"}


def test_fitness_falls_back_to_latest_day():
    yesterday = days_before(END, 1)
    days = {yesterday: wellness(yesterday, ctl=100, atl=90), END: wellness(END, ctl=None, atl=None)}
    result = cm.fitness_status(days, [], END)
    assert result["ctl"] == 100
    assert result["as_of"] == yesterday.isoformat()


def test_fitness_missing_entirely():
    assert cm.fitness_status({}, [], END)["ctl"] is None


def test_fitness_recomputed_when_planned_load_is_counted():
    week_ago = days_before(END, 7)
    yesterday = days_before(END, 1)
    days = {
        week_ago: wellness(week_ago, ctl=95.0),
        yesterday: wellness(yesterday, ctl=100.0, atl=110.0),
        END: wellness(END, ctl=102.0, atl=120.0, ctl_load=150.0),
    }
    result = cm.fitness_status(days, [], END)
    assert result["src"] == "recomputed_without_planned"
    assert result["ctl"] == round(100.0 * math.exp(-1 / 42), 1)
    assert result["atl"] == round(110.0 * math.exp(-1 / 7), 1)
    assert result["ramp"] == round(100.0 * math.exp(-1 / 42) - 95.0, 1)
    assert result["ctl"] < 100.0 and result["atl"] < 110.0  # no load -> both fall
    assert cm.fitness_status(days, [], END, today=END) == result


def test_fitness_after_today_is_projection_including_planned():
    yesterday = days_before(END, 1)
    days = {
        yesterday: wellness(yesterday, ctl=100.0, atl=110.0),
        END: wellness(END, ctl=102.0, atl=120.0, ramp=6.5, ctl_load=150.0),
    }
    result = cm.fitness_status(days, [], END, today=yesterday)
    assert result == {"ctl": 102.0, "atl": 120.0, "tsb": -18.0, "ramp": 6.5, "src": "api_incl_planned"}


def test_fitness_not_recomputed_when_load_was_done():
    yesterday = days_before(END, 1)
    days = {
        yesterday: wellness(yesterday, ctl=100.0, atl=110.0),
        END: wellness(END, ctl=102.0, atl=120.0, ctl_load=150.0),
    }
    result = cm.fitness_status(days, [activity(END, load=150)], END)
    assert result["src"] == "api"
    assert result["ctl"] == 102.0


# ---------------------------------------------------------------------------
# Volume
# ---------------------------------------------------------------------------


def test_weekly_volume_groups_iso_weeks_and_merges_rad():
    acts = [
        activity(END, "Ride", load=100, moving=7200, distance=60000),
        activity(END, "VirtualRide", load=50, moving=3600, distance=None, hour=18),
        activity(days_before(END, 1), "Run", load=60, moving=3600, distance=10000),
        activity(days_before(END, 3), "WeightTraining", load=10, moving=1800, distance=None),
    ]
    rows = cm.weekly_volume(acts, END, 14)
    assert [row["week"] for row in rows] == ["2026-W38", "2026-W39"]
    week = rows[1]
    assert week["days"] == 7
    assert week["sports"][cm.RAD] == {"h": 3.0, "load": 150, "n": 2, "km": 60.0}
    assert week["sports"][cm.LAUF] == {"h": 1.0, "load": 60, "n": 1, "km": 10.0}
    assert week["sports"][cm.KRAFT] == {"h": 0.5, "load": 10, "n": 1}
    assert week["total"] == {"h": 4.5, "load": 220, "n": 4}
    assert week["rest_days"] == 4
    assert week["monotony"] == round(cm.monotony([0, 0, 0, 10, 0, 60, 150]) or 0, 2)
    assert rows[0]["sports"] == {}
    assert rows[0]["rest_days"] == 7
    assert rows[0]["monotony"] is None


def test_weekly_volume_partial_week_has_no_monotony():
    acts = [activity(days_before(END, offset), load=50 + offset) for offset in range(9)]
    rows = cm.weekly_volume(acts, END, 9)
    assert rows[0]["days"] == 2
    assert rows[0]["monotony"] is None
    assert rows[1]["monotony"] is not None


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


def _hrv_days(values_by_offset):
    return cm.wellness_by_day(
        [wellness(days_before(END, offset), hrv=value) for offset, value in values_by_offset.items()]
    )


def test_hrv_within_band():
    days = _hrv_days({offset: 80.0 + (offset % 4) for offset in range(60)})
    result = cm.hrv_status(days, END)
    assert result["status"] == "within"
    assert result["n_7d"] == 7
    assert result["n_base"] == 60
    assert result["band"][0] < result["ln_7d"] < result["band"][1]


def test_hrv_below_and_persistence():
    values = {offset: 80.0 + (offset % 4) for offset in range(7, 60)}
    values.update(dict.fromkeys(range(7), 55.0))
    result = cm.hrv_status(_hrv_days(values), END)
    assert result["status"] == "below"
    assert result["days_below"] == 7
    assert result["rmssd_7d"] == 55


def test_hrv_above():
    values = {offset: 80.0 + (offset % 4) for offset in range(7, 60)}
    values.update(dict.fromkeys(range(7), 120.0))
    assert cm.hrv_status(_hrv_days(values), END)["status"] == "above"


def test_hrv_missing_value_breaks_streak():
    values = {offset: 80.0 + (offset % 4) for offset in range(3, 60)}
    values.update({0: 50.0, 2: 50.0, 1: None})
    result = cm.hrv_status(_hrv_days(values), END)
    assert result["days_below"] == 1


def test_hrv_insufficient_data_and_invalid_values():
    values = dict.fromkeys(range(10, 60), 80.0)
    values.update({0: 5.0, 1: 300.0, 2: None, 3: 80.0})  # 5 and 300 are sensor errors
    result = cm.hrv_status(_hrv_days(values), END)
    assert result == {"status": "insufficient_data", "n_7d": 1, "n_base": 51}
    assert cm.hrv_status({}, END)["status"] == "insufficient_data"


def test_hrv_zero_sd_baseline_collapses_band():
    result = cm.hrv_status(_hrv_days(dict.fromkeys(range(60), 80.0)), END)
    assert result["status"] == "within"
    assert result["band"][0] == result["band"][1]


def test_rhr_delta_and_days_high():
    records = [wellness(days_before(END, offset), rhr=40.0) for offset in range(3, 60)]
    records += [wellness(days_before(END, offset), rhr=47.0) for offset in range(3)]
    result = cm.rhr_status(cm.wellness_by_day(records), END)
    assert result["avg_base"] == round((57 * 40 + 3 * 47) / 60, 1)
    assert result["days_high"] == 3
    assert result["delta"] > 0


def test_rhr_missing():
    records = [wellness(days_before(END, offset), rhr=None) for offset in range(60)]
    assert cm.rhr_status(cm.wellness_by_day(records), END)["status"] == "insufficient_data"


def test_sleep_summary_with_missing_nights():
    records = [wellness(days_before(END, offset), sleep_h=7.5) for offset in range(3, 28)]
    records += [
        wellness(END, sleep_h=6.5),
        wellness(days_before(END, 1), sleep_h=None),
        wellness(days_before(END, 2), sleep_h=6.0),
    ]
    result = cm.sleep_summary(cm.wellness_by_day(records), END, 28)
    assert result["n"] == 27
    assert result["nights_short"] == 2
    assert result["recent_h"] == [6.0, None, 6.5]
    assert result["avg_7d_h"] == round((4 * 7.5 + 6.5 + 6.0) / 6, 1)


def test_sleep_summary_without_data():
    result = cm.sleep_summary({}, END, 28)
    assert result["avg_h"] is None
    assert result["recent_h"] == [None, None, None]
    assert result["n"] == 0


# ---------------------------------------------------------------------------
# Intensity
# ---------------------------------------------------------------------------


def test_power_zones_ignore_sweet_spot_bucket():
    ride = activity(END, zones=power_zones(100, 200, 300, 400, 0, 0, 0, sweet_spot=500))
    secs, basis = cm.activity_zones(ride)
    assert basis == "power"
    assert secs == [100, 200, 300, 400, 0, 0, 0]


def test_ride_without_power_falls_back_to_hr():
    ride = activity(END, zones=None, hr_zones=[600, 1200, 300, 0, 0])
    secs, basis = cm.activity_zones(ride)
    assert basis == "hr"
    assert secs == [600, 1200, 300, 0, 0, 0, 0]


def test_run_prefers_hr_and_falls_back_to_power():
    run = activity(END, "Run", zones=power_zones(100, 100, 0, 0, 0, 0, 0), hr_zones=[10, 20, 30, 40, 50, 60, 70])
    assert cm.activity_zones(run) == ([10, 20, 30, 40, 50, 60, 70], "hr")
    run_power_only = activity(END, "Run", zones=power_zones(100, 100, 0, 0, 0, 0, 0), hr_zones=None)
    assert cm.activity_zones(run_power_only)[1] == "power"


def test_activity_without_hr_or_power_has_no_zones():
    assert cm.activity_zones(activity(END, "WeightTraining", zones=None, hr_zones=None)) == (None, None)
    assert cm.activity_zones(activity(END, zones=[], hr_zones=[0, 0, 0])) == (None, None)


def test_three_zone_mapping_differs_per_basis():
    secs = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0]
    assert cm.three_zone_seconds(secs, "power") == [30.0, 30.0, 220.0]
    assert cm.three_zone_seconds(secs, "hr") == [30.0, 70.0, 180.0]
    custom = cm.CoachConfig(power_zone_map=(1, 1, 2, 2, 3, 3, 3))
    assert cm.three_zone_seconds(secs, "power", custom) == [30.0, 70.0, 180.0]


def test_polarization_index_regular():
    pi, note = cm.polarization_index(0.8, 0.05, 0.15)
    assert pi == pytest.approx(math.log10(0.8 / 0.05 * 0.15 * 100))
    assert note is None


def test_polarization_index_edge_cases():
    pi, note = cm.polarization_index(0.85, 0.0, 0.15)
    assert pi == pytest.approx(math.log10(0.85 / 0.01 * 0.15 * 100))
    assert note == "z2_substituted"
    assert cm.polarization_index(0.9, 0.1, 0.0) == (None, "z3_zero")
    assert cm.polarization_index(0.0, 0.0, 0.0) == (None, "no_zone_data")
    assert cm.polarization_index(0.0, 0.5, 0.5) == (None, "z1_zero")


@pytest.mark.parametrize(
    ("fractions", "expected"),
    [
        ((0.95, 0.05, 0.0), "Base"),
        ((0.8, 0.05, 0.15), "Polarized"),
        ((0.75, 0.2, 0.05), "Pyramidal"),
        ((0.5, 0.2, 0.3), "Pyramidal"),  # polarized shape but PI <= 2
        ((0.3, 0.5, 0.2), "Threshold"),
        ((0.3, 0.2, 0.5), "HIT"),
    ],
)
def test_classify_tid(fractions, expected):
    pi, _ = cm.polarization_index(*fractions)
    assert cm.classify_tid(*fractions, pi) == expected


def test_intensity_distribution_mixes_bases_and_filters_family():
    acts = [
        activity(END, "Ride", zones=power_zones(3600, 3600, 0, 0, 720, 0, 0)),
        activity(END, "Run", zones=None, hr_zones=[1800, 1800, 0, 360, 0]),
        activity(END, "WeightTraining", zones=None, hr_zones=None),
    ]
    result = cm.intensity_distribution(acts)
    total = 7200 + 720 + 3600 + 360
    assert result["pct"] == [round(10800 / total * 100, 1), round(360 / total * 100, 1), round(720 / total * 100, 1)]
    assert result["basis_pct"] == {"power": round(7920 / total * 100), "hr": round(3960 / total * 100)}
    assert result["h"] == round(total / 3600, 1)
    rad = cm.intensity_distribution(acts, family=cm.RAD)
    assert rad["pct"] == [round(7200 / 7920 * 100, 1), 0.0, round(720 / 7920 * 100, 1)]
    assert rad["pi_note"] == "z2_substituted"
    assert rad["cls"] == "Polarized"


def test_intensity_distribution_without_zone_data():
    result = cm.intensity_distribution([activity(END, zones=None, hr_zones=None)])
    assert result["pct"] is None
    assert result["pi_note"] == "no_zone_data"
    assert result["cls"] is None


def test_tid_drift_acute_depolarization():
    polarized = power_zones(7000, 200, 0, 800, 0, 0, 0)
    threshold = power_zones(1000, 1000, 3000, 200, 0, 0, 0)
    acts = [activity(days_before(END, offset), zones=polarized) for offset in range(7, 28)]
    acts += [activity(days_before(END, offset), zones=threshold) for offset in range(3)]
    result = cm.tid_drift(acts, END)
    assert result["cls_28d"] == "Polarized"
    assert result["cls_7d"] == "Threshold"
    assert result["drift"] == "acute_depolarization"


def test_tid_drift_without_data():
    assert cm.tid_drift([], END)["drift"] is None


def test_hard_day_ladders():
    easy = activity(END, zones=power_zones(3600, 3600, 1200, 300, 0, 0, 0))
    assert cm.is_hard_day([easy]) is False
    incidental_tempo = activity(END, zones=power_zones(3600, 0, 1800, 0, 0, 0, 0))
    assert cm.is_hard_day([incidental_tempo]) is False
    tempo = activity(END, zones=power_zones(3600, 0, 3000, 600, 0, 0, 0))
    assert cm.is_hard_day([tempo]) is True
    sprints = activity(END, zones=power_zones(3600, 0, 0, 0, 0, 0, 60))
    assert cm.is_hard_day([sprints]) is True
    hr_z3_only = activity(END, "Run", zones=None, hr_zones=[0, 0, 3600, 0, 0])
    assert cm.is_hard_day([hr_z3_only]) is False  # HR ladder ignores Z3
    hr_threshold = activity(END, "Run", zones=None, hr_zones=[0, 0, 0, 400, 200])
    assert cm.is_hard_day([hr_threshold]) is True
    assert cm.is_hard_day([activity(END, zones=None, hr_zones=None)]) is None
    assert cm.is_hard_day([]) is None


def test_hard_day_sums_activities_of_the_day():
    half = activity(END, zones=power_zones(0, 0, 0, 300, 0, 0, 0))
    assert cm.is_hard_day([half]) is False
    assert cm.is_hard_day([half, half]) is True


def test_weekly_volume_counts_hard_days():
    hard = power_zones(1800, 1800, 0, 900, 0, 0, 0)
    acts = [activity(days_before(END, offset), zones=hard) for offset in (0, 2)]
    acts.append(activity(days_before(END, 4), zones=power_zones(3600, 0, 0, 0, 0, 0, 0)))
    assert cm.weekly_volume(acts, END, 7)[0]["hard_days"] == 2


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------


def _steady_ride(day, decoupling=3.0, **kwargs):
    params = {"moving": 7200, "elapsed": 7400, "vi": 1.05, "temp": 18.0, "decoupling": decoupling}
    params.update(kwargs)
    return activity(day, "Ride", **params)


def test_durability_exclusion_reasons():
    acts = [
        _steady_ride(END, moving=3000),  # short
        _steady_ride(END, elapsed=9000),  # pauses
        _steady_ride(END, temp=28.0),  # heat
        _steady_ride(END, vi=None),  # no_power
        _steady_ride(END, vi=1.3),  # vi
        _steady_ride(END, decoupling=None),  # no_decoupling
        activity(END, "WeightTraining", moving=3600),  # not considered at all
        activity(END, "GravelRide", moving=7200),  # not a durability type
    ]
    result = cm.durability(acts, END, 28)
    assert result["excluded"] == 6
    assert result["reasons"] == {
        "heat": 1,
        "no_decoupling": 1,
        "no_power": 1,
        "pauses": 1,
        "short": 1,
        "vi": 1,
    }
    assert result[cm.RAD]["median"] is None
    assert result[cm.RAD]["n"] == 0


def test_durability_run_without_power_and_indoor_without_temp_pass():
    acts = [
        activity(END, "Run", moving=4000, vi=None, temp=15.0, decoupling=2.5),
        activity(END, "VirtualRide", moving=4000, vi=1.02, temp=None, decoupling=1.5),
    ]
    result = cm.durability(acts, END, 28)
    assert result[cm.LAUF]["median"] == 2.5
    assert result[cm.RAD]["median"] == 1.5
    assert result["excluded"] == 0


def test_durability_median_high_drift_and_trend():
    acts = [_steady_ride(days_before(END, offset), decoupling=2.0) for offset in (10, 12, 14, 20)]
    acts += [_steady_ride(days_before(END, offset), decoupling=6.5) for offset in (0, 2, 4)]
    rad = cm.durability(acts, END, 28)[cm.RAD]
    assert rad["n"] == 7
    assert rad["median"] == 2.0
    assert rad["high"] == 3
    assert rad["high_7d"] == 3
    assert rad["trend"] == "declining"


def test_durability_negative_decoupling_kept():
    rad = cm.durability([_steady_ride(END, decoupling=-2.0)], END, 28)[cm.RAD]
    assert rad["median"] == -2.0
    assert rad["trend"] is None  # needs 2 sessions per window


def test_efficiency_factor_trend():
    acts = [activity(days_before(END, offset), vi=1.02, ef=1.80, moving=3600) for offset in (10, 15, 20)]
    acts += [activity(days_before(END, offset), vi=1.02, ef=1.90, moving=3600) for offset in (1, 3)]
    acts.append(activity(END, vi=1.3, ef=2.5))  # not steady
    acts.append(activity(END, vi=1.0, ef=2.5, moving=600))  # too short
    acts.append(activity(END, "Run", vi=1.0, ef=2.5))  # not cycling
    result = cm.efficiency_factor(acts, END)
    assert result["n_7d"] == 2
    assert result["n_28d"] == 5
    assert result["ef_7d"] == 1.9
    assert result["ef_28d"] == round((3 * 1.8 + 2 * 1.9) / 5, 2)
    assert result["trend"] == "improving"


def test_efficiency_factor_insufficient():
    result = cm.efficiency_factor([activity(END, vi=1.0, ef=1.8)], END)
    assert result["ef_7d"] is None
    assert result["trend"] is None


def test_eftp_trend_with_gaps():
    records = [
        wellness(END, eftp=352.0),
        wellness(days_before(END, 30), eftp=340.0),  # within 3 days of the 28-day target
        wellness(days_before(END, 56), eftp=None),
        wellness(days_before(END, 70), eftp=320.0),  # outside tolerance
    ]
    result = cm.eftp_trend(cm.wellness_by_day(records), END)
    assert result == {
        "now": 352,
        "d28": 340,
        "pct_28": round((352 / 340 - 1) * 100, 1),
        "d56": None,
        "pct_56": None,
    }


def test_eftp_trend_without_data():
    assert cm.eftp_trend({}, END)["now"] is None


# ---------------------------------------------------------------------------
# Thresholds, top sessions, coverage
# ---------------------------------------------------------------------------


def test_athlete_thresholds():
    assert cm.athlete_thresholds(athlete(ftp=343, indoor_ftp=330)) == {
        "ftp": 343,
        "ftp_indoor": 330,
        "lthr_rad": 170,
        "lthr_lauf": 173,
    }
    assert cm.athlete_thresholds({}) == {"ftp": None, "ftp_indoor": None, "lthr_rad": None, "lthr_lauf": None}


def test_athlete_thresholds_use_ftp_of_latest_ride():
    old_ride = dict(activity(days_before(END, 40)), icu_ftp=320)
    recent_ride = dict(activity(days_before(END, 3)), icu_ftp=335)
    indoor = dict(activity(days_before(END, 2), "VirtualRide"), icu_ftp=330)
    run = dict(activity(END, "Run"), icu_ftp=None)
    result = cm.athlete_thresholds(athlete(ftp=343, indoor_ftp=340), [old_ride, recent_ride, indoor, run])
    assert result["ftp"] == 335
    assert result["ftp_indoor"] == 330
    only_outdoor = cm.athlete_thresholds(athlete(ftp=343, indoor_ftp=340), [recent_ride])
    assert only_outdoor["ftp_indoor"] == 340  # falls back to the sport settings


def test_intensity_factor_converts_percent():
    assert cm.intensity_factor(activity(END, intensity=56.85)) == pytest.approx(0.5685)
    assert cm.intensity_factor(activity(END, intensity=0.85)) == pytest.approx(0.85)
    assert cm.intensity_factor(activity(END, intensity=None)) is None


def test_top_sessions_by_load_with_hardest_session_included():
    acts = [activity(days_before(END, offset), load=load, intensity=60.0) for offset, load in enumerate([300, 250, 200, 150, 100])]
    acts.append(activity(days_before(END, 6), load=40, moving=1800, intensity=105.0))
    top = cm.top_sessions(acts)
    assert [entry["load"] for entry in top] == [300, 250, 200, 150, 40]
    assert top[-1] == {"date": days_before(END, 6).isoformat(), "type": cm.RAD, "min": 30, "load": 40, "if": 1.05}


def test_top_sessions_ties_prefer_recent():
    acts = [activity(days_before(END, offset), load=100, intensity=70.0) for offset in (5, 1, 3)]
    assert [entry["date"] for entry in cm.top_sessions(acts)] == [
        days_before(END, 1).isoformat(),
        days_before(END, 3).isoformat(),
        days_before(END, 5).isoformat(),
    ]
    assert cm.top_sessions([]) == []


def test_coverage_counts():
    acts = [
        activity(END, zones=power_zones(100, 0, 0, 0, 0, 0, 0), rpe=5),
        activity(END, "Run", zones=None, hr_zones=[100, 0, 0, 0, 0], feel=2),
        activity(END, "WeightTraining", zones=None, hr_zones=None),
    ]
    records = cm.wellness_by_day([wellness(END), wellness(days_before(END, 1), hrv=None, rhr=None, sleep_h=None)])
    assert cm.coverage(acts, records, END, 7) == {
        "days": 7,
        "hrv_days": 1,
        "rhr_days": 1,
        "sleep_days": 1,
        "sessions": 3,
        "zones": {"power": 1, "hr": 1, "none": 1},
        "rpe": 1,
        "feel": 1,
    }


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------


def _report_and_inputs():
    acts, records, athlete_record = realistic_scenario()
    report = cm.build_coach_report(acts, records, athlete_record, END, 28)
    window = cm.activities_between(acts, days_before(END, 27), END)
    return report, acts, window


def _codes(report, acts, window, **overrides):
    return {flag["code"]: flag for flag in cm.build_flags(report, acts, window, END, 28, cm.CoachConfig(**overrides))}


def test_ftp_eftp_deviation_flag():
    report, acts, window = _report_and_inputs()
    flag = _codes(report, acts, window)["ftp_eftp_dev"]
    assert flag == {"code": "ftp_eftp_dev", "sev": "warning", "val": round((343 / 352 - 1) * 100, 1), "thr": 2.0}
    report["thresholds"]["ftp"] = 350
    assert "ftp_eftp_dev" not in _codes(report, acts, window)
    report["thresholds"]["ftp_indoor"] = 350  # same as outdoor -> not repeated
    assert "ftp_indoor_eftp_dev" not in _codes(report, acts, window)
    report["thresholds"]["ftp_indoor"] = 330
    assert _codes(report, acts, window)["ftp_indoor_eftp_dev"]["val"] == round((330 / 352 - 1) * 100, 1)


def test_sport_inactive_flag():
    report, acts, window = _report_and_inputs()
    assert not any(code.startswith("sport_inactive") for code in _codes(report, acts, window))
    reduced = [a for a in acts if a["type"] != "Swim" and not (a["type"] == "Run" and a["start_date_local"] >= days_before(END, 8).isoformat())]
    codes = _codes(report, reduced, window)
    assert codes["sport_inactive:Schwimmen"]["val"] == ">28"
    assert codes["sport_inactive:Lauf"]["val"] == 11


@pytest.mark.parametrize(
    ("acwr", "code", "severity"),
    [(1.3, None, None), (1.31, "acwr_high", "warning"), (1.35, "acwr_high", "alarm"),
     (0.8, None, None), (0.79, "acwr_low", "warning"), (0.75, "acwr_low", "alarm")],
)
def test_acwr_flag_boundaries(acwr, code, severity):
    report, acts, window = _report_and_inputs()
    report["load"]["acwr"] = acwr
    codes = _codes(report, acts, window)
    if code is None:
        assert "acwr_high" not in codes and "acwr_low" not in codes
    else:
        assert codes[code]["sev"] == severity


@pytest.mark.parametrize(
    ("value", "deload", "severity"),
    [(2.0, False, None), (2.01, False, "warning"), (2.5, False, "alarm"), (2.6, True, "info")],
)
def test_monotony_flag(value, deload, severity):
    report, acts, window = _report_and_inputs()
    report["load"]["effective_monotony"] = value
    report["load"]["deload"] = deload
    flag = _codes(report, acts, window).get("monotony_high")
    assert (flag["sev"] if flag else None) == severity


def test_hrv_flags():
    report, acts, window = _report_and_inputs()
    report["recovery"]["hrv"].update(status="below", days_below=2)
    assert _codes(report, acts, window)["hrv_below"]["sev"] == "warning"
    report["recovery"]["hrv"]["days_below"] = 3
    assert _codes(report, acts, window)["hrv_below"]["sev"] == "alarm"
    report["recovery"]["hrv"] = {"status": "insufficient_data", "n_7d": 2, "n_base": 10}
    assert _codes(report, acts, window)["hrv_insufficient"]["sev"] == "info"


@pytest.mark.parametrize(("days_high", "severity"), [(1, None), (2, "warning"), (3, "alarm")])
def test_rhr_flag(days_high, severity):
    report, acts, window = _report_and_inputs()
    report["recovery"]["rhr"]["days_high"] = days_high
    flag = _codes(report, acts, window).get("rhr_elevated_days")
    assert (flag["sev"] if flag else None) == severity


def test_rhr_flag_with_insufficient_data():
    report, acts, window = _report_and_inputs()
    report["recovery"]["rhr"] = {"status": "insufficient_data", "n_7d": 0, "n_base": 0}
    assert "rhr_elevated_days" not in _codes(report, acts, window)


@pytest.mark.parametrize(("recent", "flagged"), [([6.9, None, 6.5], True), ([6.9, 7.2, 7.5], False), ([None, None, None], False)])
def test_sleep_flag(recent, flagged):
    report, acts, window = _report_and_inputs()
    report["recovery"]["sleep"]["recent_h"] = recent
    assert ("sleep_short" in _codes(report, acts, window)) is flagged


def test_subjective_missing_flag_threshold():
    report, acts, _ = _report_and_inputs()
    window = [activity(END, rpe=5)] + [activity(END) for _ in range(4)]  # 80 % missing -> not above
    assert "subjective_missing" not in _codes(report, acts, window)
    window = [activity(END) for _ in range(5)]
    assert _codes(report, acts, window)["subjective_missing"]["val"] == 1.0
    assert "subjective_missing" not in _codes(report, acts, [])


def test_durability_flags():
    report, acts, window = _report_and_inputs()
    report["capability"]["durability"][cm.RAD]["median"] = 5.5
    report["capability"]["durability"][cm.LAUF].update(median=3.0, high_7d=3)
    codes = _codes(report, acts, window)
    assert codes["durability_high:Rad"]["val"] == 5.5
    assert codes["durability_high_7d:Lauf"]["val"] == 3


def test_tid_depolarization_flag_and_sorting():
    report, acts, window = _report_and_inputs()
    report["intensity"]["drift"].update(drift="acute_depolarization", pi_7d=1.7)
    report["load"]["acwr"] = 1.5
    flags = cm.build_flags(report, acts, window, END, 28)
    assert any(flag["code"] == "tid_depolarization" for flag in flags)
    severities = [flag["sev"] for flag in flags]
    assert severities == sorted(severities, key={"alarm": 0, "warning": 1, "info": 2}.get)
    assert severities[0] == "alarm"


# ---------------------------------------------------------------------------
# Full report
# ---------------------------------------------------------------------------

REPORT_KEYS = [
    "schema_version", "period", "flags", "load", "recovery", "volume",
    "intensity", "capability", "top_sessions", "thresholds", "coverage",
]


def test_report_structure_and_size():
    acts, records, athlete_record = realistic_scenario()
    report = cm.build_coach_report(acts, records, athlete_record, END, 28)
    assert list(report) == REPORT_KEYS
    assert report["schema_version"] == cm.SCHEMA_VERSION
    assert report["period"] == {
        "mode": "actual", "start": "2026-08-31", "end": "2026-09-27", "load_end": "2026-09-27", "days": 28,
        "windows": {"acute": 7, "chronic": 28, "baseline": 60},
    }
    assert len(report["volume"]) == 4
    assert len(report["top_sessions"]) == 5
    payload = json.dumps(report, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    assert len(payload.encode("utf-8")) < 4096


def test_report_without_any_data():
    report = cm.build_coach_report([], [], {}, END, 28)
    json.dumps(report, allow_nan=False)
    assert list(report) == REPORT_KEYS
    assert report["load"]["acwr"] is None
    assert report["load"]["ctl"] is None
    assert report["recovery"]["hrv"]["status"] == "insufficient_data"
    assert report["intensity"]["all"]["cls"] is None
    assert report["top_sessions"] == []
    assert all(week["rest_days"] == 7 for week in report["volume"])
    codes = {flag["code"] for flag in report["flags"]}
    assert "hrv_insufficient" in codes
    assert "sport_inactive:Rad" in codes


def test_report_ignores_activities_after_end_and_bad_input():
    acts = [activity(END + (END - days_before(END, 1)), load=500), "not a dict"]
    report = cm.build_coach_report(acts, None, None, END, 7)
    assert report["load"]["load_7d"] == 0
    with pytest.raises(ValueError):
        cm.build_coach_report([], [], {}, END, 0)


def test_default_load_end():
    assert cm.default_load_end([activity(END)], END) == END
    assert cm.default_load_end([activity(days_before(END, 1))], END) == days_before(END, 1)
    assert cm.default_load_end(None, END) == days_before(END, 1)


def test_load_end_excludes_untrained_today_from_load_but_not_recovery():
    acts = [activity(days_before(END, offset), load=100) for offset in range(1, 40)]
    records = [wellness(days_before(END, offset)) for offset in range(60)]
    records[0] = wellness(END, hrv=50.0, sleep_h=5.0)  # today's morning values
    today_included = cm.build_coach_report(acts, records, {}, END, 28)
    shifted = cm.build_coach_report(acts, records, {}, END, 28, load_end=days_before(END, 1))
    assert today_included["load"]["load_7d"] == 600
    assert shifted["load"]["load_7d"] == 700
    assert shifted["load"]["acwr"] == 1.0
    assert shifted["period"]["load_end"] == days_before(END, 1).isoformat()
    assert shifted["period"]["start"] == days_before(END, 28).isoformat()
    assert shifted["recovery"]["sleep"]["recent_h"][-1] == 5.0
    assert shifted["recovery"] == today_included["recovery"]


def test_load_end_is_capped_at_end():
    report = cm.build_coach_report([], [], {}, END, 7, load_end=END + (END - days_before(END, 3)))
    assert report["period"]["load_end"] == END.isoformat()
