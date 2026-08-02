"""
Unit tests for event helpers in intervals_mcp_server.tools.events.

Covers:
- format_strength_description: bullet-point formatting for WeightTraining
- _prepare_event_data: description_override behaviour
"""

import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

from intervals_mcp_server.tools.events import format_strength_description, _prepare_event_data


BLOCKS_A = [
    {
        "name": "Blok A — Core/onderrug",
        "exercises": [
            "Dead bug 3x10/kant — rug plat, been en arm tegelijk uitstrekken",
            "Bird dog 3x10/kant — op handen en knieën, heupen stabiel",
        ],
    }
]

BLOCKS_AB = [
    {
        "name": "Blok A — Core/onderrug",
        "exercises": ["Dead bug 3x10/kant", "Bird dog 3x10/kant"],
    },
    {
        "name": "Blok B — Upper body",
        "exercises": ["Dumbbell row 3x10/kant", "Shoulder press 3x10"],
    },
]


# ---------------------------------------------------------------------------
# format_strength_description
# ---------------------------------------------------------------------------

class TestFormatStrengthDescription:
    def test_title_is_first_line(self):
        result = format_strength_description("Core en onderrug. ~25 min.", BLOCKS_A)
        assert result.split("\n")[0] == "Core en onderrug. ~25 min."

    def test_block_name_present(self):
        result = format_strength_description("Title", BLOCKS_A)
        assert "Blok A — Core/onderrug" in result

    def test_exercises_prefixed_with_dash(self):
        result = format_strength_description("Title", BLOCKS_A)
        assert "- Dead bug 3x10/kant — rug plat, been en arm tegelijk uitstrekken" in result
        assert "- Bird dog 3x10/kant — op handen en knieën, heupen stabiel" in result

    def test_no_trailing_newline(self):
        result = format_strength_description("Title", BLOCKS_A)
        assert not result.endswith("\n")

    def test_multiple_blocks_all_present(self):
        result = format_strength_description("Title", BLOCKS_AB)
        assert "Blok A — Core/onderrug" in result
        assert "Blok B — Upper body" in result
        assert "- Dead bug 3x10/kant" in result
        assert "- Dumbbell row 3x10/kant" in result

    def test_blank_line_between_title_and_first_block(self):
        result = format_strength_description("Title", BLOCKS_A)
        lines = result.split("\n")
        assert lines[1] == ""  # blank separator after title

    def test_empty_blocks_returns_title_only(self):
        result = format_strength_description("Title", [])
        assert result == "Title"

    def test_output_matches_expected_format(self):
        result = format_strength_description("Core en onderrug. ~25 min.", BLOCKS_A)
        expected = (
            "Core en onderrug. ~25 min.\n"
            "\n"
            "Blok A — Core/onderrug\n"
            "- Dead bug 3x10/kant — rug plat, been en arm tegelijk uitstrekken\n"
            "- Bird dog 3x10/kant — op handen en knieën, heupen stabiel"
        )
        assert result == expected


# ---------------------------------------------------------------------------
# _prepare_event_data — description_override
# ---------------------------------------------------------------------------

class TestPrepareEventDataDescriptionOverride:
    def test_override_is_used_when_provided(self):
        data = _prepare_event_data(
            name="Core sessie",
            workout_type="WeightTraining",
            start_date="2026-06-29",
            workout_doc=None,
            moving_time=None,
            distance=None,
            description_override="Custom description",
        )
        assert data["description"] == "Custom description"

    def test_no_override_and_no_workout_doc_gives_none(self):
        data = _prepare_event_data(
            name="Core sessie",
            workout_type="WeightTraining",
            start_date="2026-06-29",
            workout_doc=None,
            moving_time=None,
            distance=None,
        )
        assert data["description"] is None

    def test_ride_without_override_unchanged(self):
        data = _prepare_event_data(
            name="Easy Ride",
            workout_type="Ride",
            start_date="2026-06-29",
            workout_doc=None,
            moving_time=3600,
            distance=None,
        )
        assert data["description"] is None
        assert data["moving_time"] == 3600

    def test_override_takes_precedence_over_workout_doc(self):
        from intervals_mcp_server.utils.types import WorkoutDoc
        doc = WorkoutDoc(description="doc desc", steps=[])
        data = _prepare_event_data(
            name="Sessie",
            workout_type="WeightTraining",
            start_date="2026-06-29",
            workout_doc=doc,
            moving_time=None,
            distance=None,
            description_override="override wins",
        )
        assert data["description"] == "override wins"
