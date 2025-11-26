"""
Validation utilities for Intervals.icu MCP Server

This module contains validation functions for input parameters.
"""

import re
from datetime import datetime


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
