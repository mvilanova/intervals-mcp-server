"""
Unit tests for intervals_mcp_server.utils.streams.

These cover stream labelling, range statistics, index/time range resolution and the
CSV/JSON rendering of sample-aligned streams.
"""

import json

from intervals_mcp_server.utils.custom_fields import ACTIVITY_STREAM, index_custom_items
from intervals_mcp_server.utils.streams import (
    describe_stream,
    find_stream,
    format_range_metrics,
    format_stats,
    range_stats,
    render_streams_json,
    render_streams_table,
    resolve_sample_range,
    stream_label,
    stream_length,
)
from tests.sample_data import CUSTOM_ITEMS_DATA, STREAMS_DATA

STREAM_DEFS = index_custom_items(CUSTOM_ITEMS_DATA)[ACTIVITY_STREAM]


def test_describe_stream_standard_named_and_custom():
    """
    Standard streams get known units, named streams keep their name, custom streams
    are labelled from the athlete's definitions.
    """
    watts = describe_stream(find_stream(STREAMS_DATA, "watts"), STREAM_DEFS)
    assert stream_label(watts) == "watts (W)"
    assert watts["custom"] is False

    power2 = describe_stream(find_stream(STREAMS_DATA, "secondary_power"), STREAM_DEFS)
    assert stream_label(power2) == "Power2 [secondary_power] (W)"

    stamina = describe_stream(find_stream(STREAMS_DATA, "Stamina"), STREAM_DEFS)
    assert stream_label(stamina) == "Garmin Stamina [Stamina] (point)"
    assert stamina["custom"] is True
    assert stamina["description"] == "Stamina"

    unknown = describe_stream({"type": "SomethingElse"}, {})
    assert stream_label(unknown) == "SomethingElse"
    assert unknown["units"] is None

    long_text = "First line.\n\nSecond   paragraph " + "x" * 200
    verbose = describe_stream(
        {"type": "Verbose"}, {"Verbose": {"name": "Verbose", "description": long_text}}
    )
    assert "\n" not in verbose["description"]
    assert verbose["description"].startswith("First line. Second paragraph xxx")
    assert verbose["description"].endswith("…")
    assert len(verbose["description"]) == 160


def test_range_stats_ignores_null_nan_and_arrays():
    """
    Statistics use the numeric samples only and report how many there were.
    """
    heartrate = find_stream(STREAMS_DATA, "heartrate")["data"]
    stats = range_stats(heartrate, [(0, 6)])
    assert stats == {
        "samples": 6, "non_null": 5, "first": 120, "last": 125, "min": 120, "max": 125,
        "mean": 122.4, "delta": 5,
    }
    stamina = find_stream(STREAMS_DATA, "Stamina")["data"]
    assert range_stats(stamina, [(6, 12)])["non_null"] == 5
    hrv_stats = range_stats(find_stream(STREAMS_DATA, "hrv")["data"], [(0, 12)])
    assert hrv_stats == {"samples": 12, "non_null": 0, "arrays": 12}
    assert format_stats(hrv_stats) == (
        "array values, no scalar statistics (12/12 samples; see full output)"
    )
    assert format_stats({"samples": 3, "non_null": 0}) == "no numeric samples (3 samples in range)"
    # String "NaN" (as serialised by the API) is not a sample value either.
    assert range_stats([1, "NaN", None, 3], [(0, 4)])["non_null"] == 2


def test_range_stats_over_multiple_ranges():
    """
    Group statistics span all member ranges: first of the first, last of the last.
    """
    stamina = find_stream(STREAMS_DATA, "Stamina")["data"]
    stats = range_stats(stamina, [(0, 6), (6, 12)])
    assert stats["first"] == 100
    assert stats["last"] == 93
    assert stats["min"] == 93
    assert stats["delta"] == -7
    assert stats["samples"] == 12
    assert stats["non_null"] == 11
    assert format_stats(stats) == (
        "start 100, end 93, min 93, max 100, mean 97.18, delta -7, samples 11/12"
    )


def test_format_range_metrics_skips_time_and_latlng():
    """
    Metric lines are produced for every stream except the time and position streams.
    """
    lines = format_range_metrics(STREAMS_DATA, STREAM_DEFS, [(0, 6)])
    assert lines[0] == "  watts (W): start 100, end 150, min 100, max 150, mean 125, delta 50, samples 6/6"
    assert any(line.startswith("  Garmin Stamina [Stamina] (point): start 100, end 98") for line in lines)
    assert not any(line.startswith("  time") for line in lines)
    assert not any("latlng" in line for line in lines)


def test_resolve_sample_range_by_index_and_time():
    """
    Index bounds are clamped, time bounds follow the interval convention (end exclusive).
    """
    time_data = find_stream(STREAMS_DATA, "time")["data"]
    length = stream_length(STREAMS_DATA)
    assert length == 12
    assert resolve_sample_range(length, time_data) == (0, 12)
    assert resolve_sample_range(length, time_data, start_index=6, end_index=100) == (6, 12)
    assert resolve_sample_range(length, time_data, start_time=10, end_time=13) == (6, 9)
    # The recording pause (time 5 -> 10) is respected: time 7 maps to the first sample >= 7.
    assert resolve_sample_range(length, time_data, start_time=7) == (6, 12)
    # Index and time bounds combine to the narrower range; inverted ranges collapse.
    assert resolve_sample_range(length, time_data, start_index=8, end_time=13) == (8, 9)
    assert resolve_sample_range(length, time_data, start_index=10, end_index=2) == (10, 10)
    # Time bounds are ignored without a usable time stream.
    assert resolve_sample_range(length, None, start_time=10) == (0, 12)


def test_render_streams_table_rows_and_cells():
    """
    The CSV has an index column, time first, lat/lng split, JSON for arrays and
    empty cells for null/NaN.
    """
    table = render_streams_table(STREAMS_DATA[::-1], 0, 12)
    lines = table.splitlines()
    assert lines[0] == "index,time,Stamina,secondary_power,hrv,lat,lng,heartrate,watts"
    assert len(lines) == 13
    assert lines[1] == "0,0,100,98,[736],47.1,12.1,120,100"
    assert lines[3] == '2,2,99,118,"[712, 680]",47.12,12.12,122,120'
    assert lines[4] == "3,3,99,128,[691],47.13,12.13,,130"
    assert lines[12] == "11,15,,248,[600],47.25,12.25,145,250"


def test_render_streams_table_slice_and_downsample():
    """
    Slicing and downsampling keep recorded samples only (no averaging).
    """
    lines = render_streams_table(STREAMS_DATA, 6, 12, 2).splitlines()
    assert [line.split(",")[0] for line in lines[1:]] == ["6", "8", "10"]
    assert lines[1].startswith("6,10,200,")


def test_render_streams_json_metadata_and_nulls():
    """
    JSON output carries labels, units, custom flag, data2 for latlng and null for NaN/None.
    """
    payload = render_streams_json(STREAMS_DATA, STREAM_DEFS, 6, 12)
    text = json.dumps(payload)
    assert "NaN" not in text
    data = json.loads(text)
    assert data["index_start"] == 6
    assert data["index_end"] == 12
    assert list(data["streams"])[0] == "time"
    assert data["streams"]["Stamina"] == {
        "name": "Garmin Stamina", "units": "point", "custom": True,
        "data": [97, 96, 95, 94, 93, None],
    }
    assert data["streams"]["latlng"]["data2"] == [12.2, 12.21, 12.22, 12.23, 12.24, 12.25]
    assert data["streams"]["heartrate"]["data"] == [140, 141, 142, 143, 144, 145]
    assert json.loads(json.dumps(render_streams_json(STREAMS_DATA, {}, 0, 6)))["streams"]["heartrate"]["data"][3] is None
