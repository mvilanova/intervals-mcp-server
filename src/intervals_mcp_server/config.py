"""
Configuration management for Intervals.icu MCP Server.

This module handles loading and validation of configuration from environment variables.
"""

import os
from dataclasses import dataclass

from intervals_mcp_server.utils.validation import validate_athlete_id

# Try to load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv

    _ = load_dotenv()
except ImportError:
    # python-dotenv not installed, proceed without it
    pass


@dataclass
class Config:
    """Configuration settings for the Intervals.icu MCP Server.

    Note: ``api_key`` and ``athlete_id`` are exposed as @property below so
    that ``os.environ`` changes (e.g. ``.env`` edits after the server has
    started) take effect on the next read. The AGENTS.md hard rule
    "always pass ``athlete_id`` AND ``api_key`` explicitly" exists because
    of stale fallback drift; this design keeps the fallback in sync with
    the environment without forcing callers to restart.
    """

    intervals_api_base_url: str
    user_agent: str

    @property
    def api_key(self) -> str:
        return os.getenv("API_KEY", "")

    @property
    def athlete_id(self) -> str:
        return os.getenv("ATHLETE_ID", "")


_config_instance: Config | None = None  # pylint: disable=invalid-name


def load_config() -> Config:
    """
    Load configuration from environment variables.

    Returns:
        Config: Configuration instance. The ``api_key`` and ``athlete_id``
        fields are read from ``os.environ`` on every access, so updates to
        the environment after this function returns take effect on the
        next read.

    Raises:
        ValueError: If ``athlete_id`` is invalid at load time (when non-empty).
    """
    intervals_api_base_url = os.getenv("INTERVALS_API_BASE_URL", "https://intervals.icu/api/v1")
    user_agent = "intervalsicu-mcp-server/1.0"

    # Validate athlete_id at load time only. api_key/athlete_id are
    # env-backed properties, so updates after load are surfaced as
    # whatever the API eventually returns — a best-effort fallback, not
    # a primary path (the AGENTS.md hard rule is to pass both explicitly).
    athlete_id = os.getenv("ATHLETE_ID", "")
    if athlete_id:
        validate_athlete_id(athlete_id)

    return Config(
        intervals_api_base_url=intervals_api_base_url,
        user_agent=user_agent,
    )


def get_config() -> Config:
    """
    Get the configuration instance (singleton pattern).

    Returns:
        Config: The configuration instance. ``api_key`` and ``athlete_id``
        are read from the environment on every access.
    """
    global _config_instance  # pylint: disable=global-statement  # noqa: PLW0603 - singleton pattern
    if _config_instance is None:
        _config_instance = load_config()
    return _config_instance
