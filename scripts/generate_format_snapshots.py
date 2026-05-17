"""Regenerate snapshot fixtures for the formatting test suite.

Run when a formatter's output should intentionally change:

    uv run python scripts/generate_format_snapshots.py

The companion `test_formatter_matches_snapshot` pytest case then asserts that
each formatter's output equals the saved .txt fixture byte-for-byte. Review the
git diff carefully before committing — every change here is observable by
downstream LLM consumers.
"""

from __future__ import annotations

import json
from pathlib import Path

from intervals_mcp_server.utils.formatting import (
    format_activity_summary,
    format_event_details,
    format_intervals,
)

RESOURCES = Path(__file__).resolve().parents[1] / "tests" / "ressources"

SNAPSHOTS: list[tuple[str, object]] = [
    ("activity_summary_full", format_activity_summary),
    ("event_details_workout_race", format_event_details),
    ("intervals_full", format_intervals),
]


def main() -> None:
    for name, fn in SNAPSHOTS:
        payload = json.loads((RESOURCES / f"{name}.json").read_text(encoding="utf-8"))
        output_path = RESOURCES / f"{name}_formatted.txt"
        output_path.write_text(fn(payload), encoding="utf-8")  # type: ignore[operator]
        print(f"wrote {output_path.relative_to(RESOURCES.parents[1])}")


if __name__ == "__main__":
    main()
