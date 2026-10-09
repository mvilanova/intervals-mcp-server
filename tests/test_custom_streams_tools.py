"""
Tool-level tests for the custom field and stream features:
- get_activity_details (custom activity fields, include_all_fields)
- get_activity_streams (stream selection, summary/full/json output, slicing, paging)
- list_activity_streams
- get_activity_intervals (custom interval fields, per-interval stream metrics)
- get_wellness_data (custom wellness field labels)
- the custom item definition cache

API calls are monkeypatched with a small URL router.
"""

import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.server import (  # pylint: disable=wrong-import-position
    delete_custom_item,
    get_activity_details,
    get_activity_intervals,
    get_activity_streams,
    get_wellness_data,
    list_activity_streams,
)
from intervals_mcp_server.tools import custom_items as custom_items_module  # pylint: disable=wrong-import-position
from intervals_mcp_server.tools import gear as gear_module  # pylint: disable=wrong-import-position
from intervals_mcp_server.utils.streams import DEFAULT_STREAM_TYPES  # pylint: disable=wrong-import-position
from tests.sample_data import (  # pylint: disable=wrong-import-position
    ACTIVITY_WITH_CUSTOM_FIELDS,
    CUSTOM_ITEMS_DATA,
    INTERVALS_DATA,
    INTERVALS_WITH_INDICES,
    STREAMS_DATA,
)

PATCH_TARGETS = (
    "intervals_mcp_server.api.client.make_intervals_request",
    "intervals_mcp_server.tools.activities.make_intervals_request",
    "intervals_mcp_server.tools.wellness.make_intervals_request",
    "intervals_mcp_server.tools.gear.make_intervals_request",
    "intervals_mcp_server.tools.custom_items.make_intervals_request",
)


def _install_router(monkeypatch, *, activity=None, streams=None, intervals=None,
                    custom_items=None, wellness=None, calls=None):
    """Patch make_intervals_request everywhere with a router keyed on the URL."""

    async def fake_request(url=None, **kwargs):
        if calls is not None:
            calls.append((url, kwargs.get("params"), kwargs.get("method", "GET")))
        if url and "/custom-item" in url:
            return custom_items if custom_items is not None else []
        if url and "/streams" in url:
            return streams
        if url and "/intervals" in url:
            return intervals
        if url and "/wellness" in url:
            return wellness
        if url and "/gear" in url:
            return []
        return activity

    for target in PATCH_TARGETS:
        monkeypatch.setattr(target, fake_request)
    custom_items_module._CUSTOM_ITEMS_CACHE.clear()  # pylint: disable=protected-access
    gear_module._GEAR_RAW_CACHE.clear()  # pylint: disable=protected-access


def _stream_calls(calls):
    return [call for call in calls if call[0] and "/streams" in call[0]]


# --- get_activity_details -------------------------------------------------


def test_get_activity_details_lists_custom_fields(monkeypatch):
    """
    Custom activity fields are listed with name, code, value, units and select label.
    """
    _install_router(monkeypatch, activity=ACTIVITY_WITH_CUSTOM_FIELDS, custom_items=CUSTOM_ITEMS_DATA)
    result = asyncio.run(get_activity_details("i1"))
    assert "Activity: Sweet Spot" in result
    assert "Custom Activity Fields:" in result
    assert "- Aerobic Effect [AerobicEffect]: 3.5" in result
    assert "- EPOC [EPOC]: 129.58348 ml/kg" in result
    assert "- Training Effect [TrainingEffectSelect]: 2 (Base)" in result
    assert "- Flight Time [FlightTime]: no value" in result
    assert "- Sweat loss [Sweatloss]: 0 ml (0: may be absent in source file)" in result
    assert "Other Fields:" not in result


def test_get_activity_details_include_all_fields(monkeypatch):
    """
    include_all_fields adds the remaining payload fields once, custom fields are not repeated.
    """
    _install_router(monkeypatch, activity=ACTIVITY_WITH_CUSTOM_FIELDS, custom_items=CUSTOM_ITEMS_DATA)
    result = asyncio.run(get_activity_details("i1", include_all_fields=True))
    assert "Other Fields:" in result
    assert '- icu_zone_times: [{"id": "Z1", "secs": 910}, {"id": "Z2", "secs": 1489}]' in result
    assert '- stream_types: ["time", "watts", "heartrate", "secondary_power", "Stamina"]' in result
    assert result.count("AerobicEffect") == 1
    # Fields rendered by the standard summary do not show up again.
    assert "- moving_time:" not in result


def test_get_activity_details_without_custom_fields(monkeypatch):
    """
    include_custom_fields=False keeps the classic output and skips the definitions call.
    """
    calls = []
    _install_router(monkeypatch, activity=ACTIVITY_WITH_CUSTOM_FIELDS, custom_items=CUSTOM_ITEMS_DATA, calls=calls)
    result = asyncio.run(get_activity_details("i1", include_custom_fields=False))
    assert "Custom Activity Fields" not in result
    assert not any("/custom-item" in call[0] for call in calls)


def test_get_activity_details_without_definitions(monkeypatch):
    """
    When the athlete has no custom field definitions the section says so.
    """
    _install_router(monkeypatch, activity=ACTIVITY_WITH_CUSTOM_FIELDS, custom_items={"error": True})
    result = asyncio.run(get_activity_details("i1"))
    assert "no custom activity field definitions found" in result


# --- get_activity_streams -------------------------------------------------


def test_get_activity_streams_default_selection_unchanged(monkeypatch):
    """
    Without stream_types the classic default set is requested and summarised.
    """
    calls = []
    _install_router(monkeypatch, streams=STREAMS_DATA, custom_items=CUSTOM_ITEMS_DATA, calls=calls)
    result = asyncio.run(get_activity_streams("i1"))
    assert _stream_calls(calls)[0][1] == {"types": DEFAULT_STREAM_TYPES}
    assert "Activity Streams for i1:" in result
    assert "Data Points: 12" in result
    assert "Stream: Garmin Stamina (Stamina)" in result
    assert "  Units: point" in result
    assert "  Custom: yes" in result
    assert "  Stats: start 100, end 93, min 93, max 100, mean 97.18, delta -7, samples 11/12" in result
    assert "Stream: Power2 (secondary_power)" in result
    assert "First 5 values: [0, 1, 2, 3, 4]" in result


def test_get_activity_streams_all_sends_no_filter(monkeypatch):
    """
    stream_types="all" fetches every stream of the activity (no types parameter).
    """
    calls = []
    _install_router(monkeypatch, streams=STREAMS_DATA, calls=calls)
    asyncio.run(get_activity_streams("i1", stream_types="all"))
    assert _stream_calls(calls)[0][1] is None


def test_get_activity_streams_full_table(monkeypatch):
    """
    output_format="full" adds the time stream to the request and returns one CSV row per sample.
    """
    calls = []
    _install_router(monkeypatch, streams=STREAMS_DATA, custom_items=CUSTOM_ITEMS_DATA, calls=calls)
    result = asyncio.run(get_activity_streams("i1", stream_types="watts, Stamina", output_format="full"))
    assert _stream_calls(calls)[0][1] == {"types": "time,watts,Stamina"}
    assert "samples 0-11 of 12 (full sample resolution)" in result
    assert "Streams: time (s), watts (W), heartrate (bpm), latlng (deg), hrv (ms), Power2 [secondary_power] (W), Garmin Stamina [Stamina] (point)" in result
    lines = result.splitlines()
    assert "index,time,watts,heartrate,lat,lng,hrv,secondary_power,Stamina" in lines
    assert "3,3,130,,47.13,12.13,[691],128,99" in lines
    assert "6,10,200,140,47.2,12.2,[650],198,97" in lines
    assert "11,15,250,145,47.25,12.25,[600],248," in lines
    assert "Note: output cut" not in result


def test_get_activity_streams_slicing_and_downsample(monkeypatch):
    """
    Index bounds, time bounds and downsample select recorded samples only.
    """
    _install_router(monkeypatch, streams=STREAMS_DATA)
    by_index = asyncio.run(
        get_activity_streams("i1", output_format="full", start_index=6, end_index=12, downsample=2)
    )
    rows = [line for line in by_index.splitlines() if line[:1].isdigit()]
    assert [row.split(",")[0] for row in rows] == ["6", "8", "10"]
    assert "samples 6-11 of 12 (every 2. sample)" in by_index

    by_time = asyncio.run(get_activity_streams("i1", output_format="full", start_time=10, end_time=13))
    rows = [line for line in by_time.splitlines() if line[:1].isdigit()]
    assert [row.split(",")[1] for row in rows] == ["10", "11", "12"]

    empty = asyncio.run(get_activity_streams("i1", output_format="full", start_index=20))
    assert "No samples in the selected range." in empty


def test_get_activity_streams_pages_long_selections(monkeypatch):
    """
    More samples than max_points are cut and the response says how to continue.
    """
    _install_router(monkeypatch, streams=STREAMS_DATA)
    result = asyncio.run(get_activity_streams("i1", output_format="full", max_points=5))
    rows = [line for line in result.splitlines() if line[:1].isdigit()]
    assert len(rows) == 5
    assert "samples 0-4 of 12" in result
    assert "Note: output cut to 5 of 12 samples (indices 0-4). Continue with start_index=5" in result


def test_get_activity_streams_json(monkeypatch):
    """
    output_format="json" returns labelled arrays with null for missing samples.
    """
    _install_router(monkeypatch, streams=STREAMS_DATA, custom_items=CUSTOM_ITEMS_DATA)
    result = asyncio.run(get_activity_streams("i1", output_format="json", start_index=6))
    payload = json.loads(result[result.index("{"): result.rindex("}") + 1])
    assert payload["index_start"] == 6
    assert payload["streams"]["time"]["data"] == [10, 11, 12, 13, 14, 15]
    assert payload["streams"]["Stamina"]["units"] == "point"
    assert payload["streams"]["Stamina"]["data"][-1] is None
    assert payload["streams"]["secondary_power"]["name"] == "Power2"


def test_get_activity_streams_rejects_bad_arguments(monkeypatch):
    """
    Unknown output formats and non-positive paging arguments are reported, not guessed.
    """
    _install_router(monkeypatch, streams=STREAMS_DATA)
    assert asyncio.run(get_activity_streams("i1", output_format="xml")).startswith("Error: output_format")
    assert asyncio.run(get_activity_streams("i1", downsample=0)).startswith("Error: downsample")


def test_get_activity_streams_error_and_empty(monkeypatch):
    """
    API errors and empty responses are passed on as messages.
    """
    _install_router(monkeypatch, streams={"error": True, "message": "boom"})
    assert asyncio.run(get_activity_streams("i1")) == "Error fetching activity streams: boom"
    _install_router(monkeypatch, streams=[])
    assert asyncio.run(get_activity_streams("i1")) == "No stream data found for activity i1."


# --- list_activity_streams ------------------------------------------------


def test_list_activity_streams_from_activity_payload(monkeypatch):
    """
    The listing uses the activity's stream_types and the definitions; no stream download.
    """
    calls = []
    _install_router(monkeypatch, activity=ACTIVITY_WITH_CUSTOM_FIELDS, streams=STREAMS_DATA,
                    custom_items=CUSTOM_ITEMS_DATA, calls=calls)
    result = asyncio.run(list_activity_streams("i1"))
    assert "Streams available for activity i1 ('Sweet Spot', start 2026-10-06T17:36:22, elapsed 4967 s):" in result
    assert "Power fields: power, Power2" in result
    assert "Standard streams (4):" in result
    assert "- secondary_power (W)" in result
    assert "Custom streams (1):" in result
    assert "- Garmin Stamina [Stamina] (point): Stamina" in result
    assert not _stream_calls(calls)


def test_list_activity_streams_with_stats(monkeypatch):
    """
    include_stats downloads the streams and appends statistics per stream.
    """
    calls = []
    _install_router(monkeypatch, activity=ACTIVITY_WITH_CUSTOM_FIELDS, streams=STREAMS_DATA,
                    custom_items=CUSTOM_ITEMS_DATA, calls=calls)
    result = asyncio.run(list_activity_streams("i1", include_stats=True))
    assert _stream_calls(calls)[0][1] is None
    assert "- Garmin Stamina [Stamina] (point): Stamina | start 100, end 93, min 93, max 100, mean 97.18, delta -7, samples 11/12" in result
    assert "- Power2 [secondary_power] (W) | start 98" in result
    assert "Standard streams (6):" in result


def test_list_activity_streams_falls_back_to_stream_download(monkeypatch):
    """
    Without stream_types on the activity the streams are fetched to build the list.
    """
    activity = {k: v for k, v in ACTIVITY_WITH_CUSTOM_FIELDS.items() if k != "stream_types"}
    _install_router(monkeypatch, activity=activity, streams=STREAMS_DATA, custom_items=CUSTOM_ITEMS_DATA)
    result = asyncio.run(list_activity_streams("i1"))
    assert "Custom streams (1):" in result
    _install_router(monkeypatch, activity=activity, streams=[], custom_items=CUSTOM_ITEMS_DATA)
    assert asyncio.run(list_activity_streams("i1")) == "No stream data found for activity i1."


# --- get_activity_intervals -----------------------------------------------


def test_get_activity_intervals_classic_output_unchanged(monkeypatch):
    """
    Without stream_types no streams are fetched and no stream metrics are shown.
    """
    calls = []
    _install_router(monkeypatch, intervals=INTERVALS_DATA, custom_items=CUSTOM_ITEMS_DATA, calls=calls)
    result = asyncio.run(get_activity_intervals("i1"))
    assert "Intervals Analysis:" in result
    assert "Rep 1" in result
    assert "Stream Metrics" not in result
    assert "Custom Interval Fields" not in result
    assert not _stream_calls(calls)


def test_get_activity_intervals_custom_fields_and_stream_metrics(monkeypatch):
    """
    Custom interval fields and per-interval/group statistics of the requested streams are listed.
    """
    calls = []
    _install_router(monkeypatch, intervals=INTERVALS_WITH_INDICES, streams=STREAMS_DATA,
                    custom_items=CUSTOM_ITEMS_DATA, calls=calls)
    result = asyncio.run(get_activity_intervals("i1", stream_types="Stamina"))
    assert _stream_calls(calls)[0][1] == {"types": "time,Stamina"}
    assert "Custom Interval Fields:\n  Elapsed Time [ElapsedTime]: 10" in result
    assert "Stream Metrics (samples 0-5):" in result
    assert "  Garmin Stamina [Stamina] (point): start 100, end 98, min 98, max 100, mean 99, delta -2, samples 6/6" in result
    assert "Stream Metrics (samples 6-11):" in result
    assert "  Garmin Stamina [Stamina] (point): start 97, end 93, min 93, max 97, mean 95, delta -4, samples 5/6" in result
    # Group g1 spans both member intervals.
    assert "Stream Metrics (samples 0-5, 6-11):" in result
    assert "  Garmin Stamina [Stamina] (point): start 100, end 93, min 93, max 100, mean 97.18, delta -7, samples 11/12" in result
    assert "  time" not in result
    assert "latlng" not in result


def test_get_activity_intervals_custom_selector(monkeypatch):
    """
    stream_types="custom" fetches every stream and keeps custom ones plus secondary_power.
    """
    calls = []
    _install_router(monkeypatch, intervals=INTERVALS_WITH_INDICES, streams=STREAMS_DATA,
                    custom_items=CUSTOM_ITEMS_DATA, calls=calls)
    result = asyncio.run(get_activity_intervals("i1", stream_types="custom"))
    assert _stream_calls(calls)[0][1] is None
    assert "  Garmin Stamina [Stamina] (point):" in result
    assert "  Power2 [secondary_power] (W): start 98, end 148" in result
    assert "  watts (W)" not in result


def test_get_activity_intervals_without_indices_or_streams(monkeypatch):
    """
    Intervals without sample indices say so; a failed stream fetch is reported as a note.
    """
    _install_router(monkeypatch, intervals=INTERVALS_DATA, streams=STREAMS_DATA, custom_items=CUSTOM_ITEMS_DATA)
    result = asyncio.run(get_activity_intervals("i1", stream_types="Stamina"))
    assert "Stream Metrics: not available (interval has no sample indices)" in result

    _install_router(monkeypatch, intervals=INTERVALS_WITH_INDICES,
                    streams={"error": True, "message": "boom"}, custom_items=CUSTOM_ITEMS_DATA)
    result = asyncio.run(get_activity_intervals("i1", stream_types="Stamina"))
    assert "Note: stream metrics unavailable. Error fetching activity streams: boom" in result
    assert "Elapsed Time [ElapsedTime]: 10" in result


# --- get_wellness_data ----------------------------------------------------


def test_get_wellness_data_labels_custom_fields(monkeypatch):
    """
    include_all_fields annotates custom wellness fields with name and units.
    """
    wellness = {"2026-10-01": {"id": "2026-10-01", "ctl": 50, "GarminSleepDeepMinutes": 85, "other": 1}}
    _install_router(monkeypatch, wellness=wellness, custom_items=CUSTOM_ITEMS_DATA)
    result = asyncio.run(get_wellness_data(athlete_id="i1", include_all_fields=True))
    assert "- GarminSleepDeepMinutes: 85 (Garmin Deep Sleep, min)" in result
    assert "- other: 1" in result

    calls = []
    _install_router(monkeypatch, wellness=wellness, custom_items=CUSTOM_ITEMS_DATA, calls=calls)
    result = asyncio.run(get_wellness_data(athlete_id="i1"))
    assert "GarminSleepDeepMinutes" not in result
    assert not any("/custom-item" in call[0] for call in calls)


# --- definitions cache ----------------------------------------------------


def test_custom_item_index_is_cached_and_invalidated(monkeypatch):
    """
    Definitions are fetched once per athlete, refreshed on demand and dropped after changes.
    """
    calls = []
    _install_router(monkeypatch, custom_items=CUSTOM_ITEMS_DATA, calls=calls)

    def definition_calls():
        return [call for call in calls if "/custom-item" in call[0] and call[2] == "GET"]

    index = asyncio.run(custom_items_module.get_custom_item_index("i1"))
    assert "Stamina" in index["ACTIVITY_STREAM"]
    asyncio.run(custom_items_module.get_custom_item_index("i1"))
    assert len(definition_calls()) == 1

    asyncio.run(custom_items_module.get_custom_item_index("i1", refresh=True))
    assert len(definition_calls()) == 2

    asyncio.run(delete_custom_item(7, athlete_id="i1"))
    asyncio.run(custom_items_module.get_custom_item_index("i1"))
    assert len(definition_calls()) == 3


def test_custom_item_index_does_not_cache_errors(monkeypatch):
    """
    A failed definitions fetch yields an empty index and is retried on the next call.
    """
    calls = []
    _install_router(monkeypatch, custom_items={"error": True, "message": "boom"}, calls=calls)
    assert asyncio.run(custom_items_module.get_custom_item_index("i1")) == {}
    assert asyncio.run(custom_items_module.get_custom_item_index("i1")) == {}
    assert len([call for call in calls if "/custom-item" in call[0]]) == 2
