"""
Unit tests for intervals_mcp_server.config.

Specifically guards against the wrong-account foot-gun in AGENTS.md:
"the MCP's .env is a foot-gun. ... Keep the .env in sync with
athlete-profile.md, or remove it entirely so there's no fallback
path."
"""
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("API_KEY", "test")
os.environ.setdefault("ATHLETE_ID", "i1")

# pylint: disable=wrong-import-position
from intervals_mcp_server import config as config_module
from intervals_mcp_server.config import Config, get_config


def _reset_config_singleton(monkeypatch):
    """Clear the cached singleton so load_config runs again on the next
    get_config call. Harmless once api_key/athlete_id become env-driven
    properties, but kept so the singleton reset path stays covered.
    """
    monkeypatch.setattr(config_module, "_config_instance", None)


def test_get_config_athlete_id_picks_up_env_change(monkeypatch):
    """get_config().athlete_id must reflect the current os.environ, not a
    value captured at first call.
    """
    _reset_config_singleton(monkeypatch)
    monkeypatch.setenv("ATHLETE_ID", "i1")
    assert get_config().athlete_id == "i1"

    monkeypatch.setenv("ATHLETE_ID", "i2")
    assert get_config().athlete_id == "i2"


def test_get_config_api_key_picks_up_env_change(monkeypatch):
    """get_config().api_key must reflect the current os.environ, not a
    value captured at first call.
    """
    _reset_config_singleton(monkeypatch)
    monkeypatch.setenv("API_KEY", "key-a")
    assert get_config().api_key == "key-a"

    monkeypatch.setenv("API_KEY", "key-b")
    assert get_config().api_key == "key-b"


def test_get_config_holds_only_immutable_fields():
    """api_key and athlete_id are properties — Config only stores
    intervals_api_base_url and user_agent. Keeps the dataclass
    introspection honest and prevents a future regression that
    re-introduces cached env values as constructor args.
    """
    cfg = Config(
        intervals_api_base_url="https://intervals.icu/api/v1",
        user_agent="intervalsicu-mcp-server/1.0",
    )
    fields = {f.name for f in cfg.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    assert fields == {"intervals_api_base_url", "user_agent"}
