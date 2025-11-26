"""
Validation utilities for Intervals.icu MCP Server

This module contains validation functions for input parameters.
"""

import re
from datetime import datetime

from intervals_mcp_server.utils.dates import parse_date_range


def validate_athlete_id(athlete_id: str) -> None:
    """Validate that an athlete ID is in the correct format.

    Empty strings are allowed (meaning no default athlete ID is set).
    Non-empty athlete IDs must be all digits or start with 'i' followed by digits.

    Args:
        athlete_id: The athlete ID to validate.

    Raises:
        ValueError: If the athlete ID is not in the correct format.
    """
    if athlete_id and not re.fullmatch(r"i?\d+", athlete_id):
        raise ValueError(
            "ATHLETE_ID must be all digits (e.g. 123456) or start with 'i' followed by digits (e.g. i123456)"
        )


def validate_date(date_str: str) -> str:
    """Validate that a date string is in YYYY-MM-DD format.

    Args:
        date_str: The date string to validate.

    Returns:
        The validated date string if valid.

    Raises:
        ValueError: If the date string is not in YYYY-MM-DD format.
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError as exc:
        raise ValueError("Invalid date format. Please use YYYY-MM-DD.") from exc


def resolve_athlete_id(
    athlete_id: str | None, default_athlete_id: str = ""
) -> tuple[str, str | None]:
    """Resolve athlete ID from parameter or default, with error message if missing.

    Args:
        athlete_id: Optional athlete ID parameter.
        default_athlete_id: Default athlete ID to use if athlete_id is None.

    Returns:
        Tuple of (athlete_id_to_use, error_message).
        athlete_id_to_use will be empty string if not found.
        error_message will be None if athlete_id is resolved successfully.
    """
    athlete_id_to_use = athlete_id if athlete_id is not None else default_athlete_id
    if not athlete_id_to_use:
        return (
            "",
            "Error: No athlete ID provided and no default ATHLETE_ID found in environment variables.",
        )
    return athlete_id_to_use, None


def resolve_date_params(
    start_date: str | None,
    end_date: str | None,
    default_start_days_ago: int = 30,
) -> tuple[str, str]:
    """Resolve start and end date parameters with defaults.

    Args:
        start_date: Optional start date in YYYY-MM-DD format.
        end_date: Optional end date in YYYY-MM-DD format.
        default_start_days_ago: Number of days ago for default start date. Defaults to 30.

    Returns:
        Tuple of (start_date, end_date) as strings in YYYY-MM-DD format.
    """
    return parse_date_range(start_date, end_date, default_start_days_ago)
