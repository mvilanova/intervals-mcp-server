"""
Regression tests for the generic dataclass helpers in
``intervals_mcp_server.utils.types``.

The helpers (`_coerce`, `_serialize`) are module-private but cover the
JSON ↔ dataclass round-trip for every dataclass in this module. The cases
below pin down three failure modes that were not exercised by the
original suite:

* ``_coerce(None, list[Foo] | None)`` must return ``None`` rather than
  crashing on the list comprehension (Optional list fields receiving
  explicit ``null`` from the API).
* ``_coerce`` must recognise PEP 604 unions (``X | None``) the same way
  it recognises ``typing.Union[X, None]``. Every field in ``types.py``
  is declared with the PEP 604 syntax, so this is the path that
  actually runs in production.
* ``_serialize`` must recurse into dict values so enums and dataclasses
  nested inside ``WorkoutDoc.sport_settings`` survive ``json.dumps``.
"""

from __future__ import annotations

from intervals_mcp_server.utils.types import (
    Intensity,
    Step,
    Value,
    ValueUnits,
    _coerce,
    _serialize,
)


# --- _coerce ----------------------------------------------------------------


def test_coerce_none_returns_none_for_optional_list():
    """``None`` should pass through, even when the hint is a list union."""
    hint = list[Step] | None
    assert _coerce(None, hint) is None


def test_coerce_pep604_union_dispatches_to_enum():
    """`X | None` must trigger the same Optional-recursion as `Union[X, None]`.

    Before the fix, ``get_origin(Intensity | None)`` returned
    ``types.UnionType`` and the legacy ``origin is Union`` check missed
    it, so the raw string fell through unchanged.
    """
    step = Step.from_dict({"intensity": "active"})
    assert step.intensity is Intensity.ACTIVE


def test_coerce_pep604_union_dispatches_to_nested_list():
    """``list[Step] | None`` must coerce the inner elements via Step.from_dict."""
    step = Step.from_dict(
        {
            "steps": [
                {"intensity": "warmup", "duration": 600},
                {"intensity": "interval", "duration": 60},
            ],
        }
    )
    assert step.steps is not None
    assert all(isinstance(s, Step) for s in step.steps)
    assert step.steps[0].intensity is Intensity.WARMUP
    assert step.steps[1].duration == 60


# --- _serialize -------------------------------------------------------------


def test_serialize_recurses_into_dict_values():
    """Enums and lists nested inside dict values must be serialised, not leaked.

    ``WorkoutDoc.sport_settings`` is typed ``dict[str, Any]``; this is the
    only field that can carry enum / dataclass values inside a dict.
    """
    serialized = _serialize(
        {
            "units": ValueUnits.WATTS,
            "intensities": [Intensity.ACTIVE, Intensity.RECOVERY],
        }
    )
    assert serialized == {
        "units": "w",
        "intensities": ["active", "recovery"],
    }


def test_serialize_recurses_into_nested_dataclass_in_dict():
    """A dataclass tucked inside a dict value should serialise via its to_dict."""
    serialized = _serialize({"target": Value(value=95.0, units=ValueUnits.PERCENT_FTP)})
    assert serialized == {"target": {"value": 95.0, "units": "%ftp"}}


# --- numeric coercion ------------------------------------------------------


def test_coerce_int_to_float_for_float_hint():
    """
    Ensure integers from JSON are converted to the expected numeric representation for fields annotated as float.
    
    This test verifies that constructing a Value from JSON with an integer `value` yields a Python float (e.g., `95` -> `95.0`) so downstream float-only helpers operate correctly.
    """
    value = Value.from_dict({"value": 95, "units": "%ftp"})
    assert value.value == 95.0
    assert isinstance(value.value, float)


def test_coerce_float_passthrough_for_float_hint():
    """Floats stay floats — the int branch must not over-cast."""
    value = Value.from_dict({"value": 95.5, "units": "%ftp"})
    assert value.value == 95.5
    assert isinstance(value.value, float)
