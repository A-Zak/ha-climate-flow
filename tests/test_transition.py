"""Tests for the Home Assistant-independent pending-transition model."""

from datetime import UTC, datetime

import pytest

from custom_components.climate_flow.transition import PendingTransition

FIRES_AT = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def test_transition_accepts_turn_off() -> None:
    """Test a turn-off transition stores no other target state."""
    transition = PendingTransition(
        target="climate.bedroom", fires_at=FIRES_AT, turn_off=True
    )

    assert transition.turn_off is True
    assert transition.turn_on is False
    assert transition.temperature_celsius is None


def test_transition_accepts_turn_on() -> None:
    """Test a bare turn-on transition stores no temperature."""
    transition = PendingTransition(
        target="climate.bedroom", fires_at=FIRES_AT, turn_on=True
    )

    assert transition.turn_on is True
    assert transition.turn_off is False
    assert transition.temperature_celsius is None


def test_transition_accepts_a_temperature() -> None:
    """Test a temperature-only transition stores no on/off flag."""
    transition = PendingTransition(
        target="climate.bedroom", fires_at=FIRES_AT, temperature_celsius=22.0
    )

    assert transition.turn_off is False
    assert transition.turn_on is False
    assert transition.temperature_celsius == 22.0


def test_transition_accepts_turn_on_combined_with_a_temperature() -> None:
    """Test turning on to a specific temperature in one transition.

    This is "turn on and set temp" for an AC that is currently off: a
    single transition that both powers it on and sets its target.
    """
    transition = PendingTransition(
        target="climate.bedroom",
        fires_at=FIRES_AT,
        turn_on=True,
        temperature_celsius=22.0,
    )

    assert transition.turn_on is True
    assert transition.temperature_celsius == 22.0
    assert transition.turn_off is False


def test_transition_rejects_no_target_state_set() -> None:
    """Test a transition must set turn_off, turn_on, or a temperature."""
    with pytest.raises(ValueError, match="turn_off, or turn_on and/or"):
        PendingTransition(target="climate.bedroom", fires_at=FIRES_AT)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"turn_off": True, "temperature_celsius": 22.0},
        {"turn_off": True, "turn_on": True},
        {"turn_off": True, "turn_on": True, "temperature_celsius": 22.0},
    ],
)
def test_transition_rejects_turn_off_combined_with_anything_else(
    kwargs: dict[str, object],
) -> None:
    """Test turn-off cannot combine with turn-on or a temperature."""
    with pytest.raises(ValueError, match="turn_off"):
        PendingTransition(target="climate.bedroom", fires_at=FIRES_AT, **kwargs)


def test_transition_as_dict_reports_the_target_state() -> None:
    """Test the serialized form is suitable for a sensor attribute map."""
    off = PendingTransition(target="climate.bedroom", fires_at=FIRES_AT, turn_off=True)
    on = PendingTransition(target="climate.bedroom", fires_at=FIRES_AT, turn_on=True)
    temperature = PendingTransition(
        target="climate.bedroom", fires_at=FIRES_AT, temperature_celsius=22.0
    )
    on_to_temperature = PendingTransition(
        target="climate.bedroom",
        fires_at=FIRES_AT,
        turn_on=True,
        temperature_celsius=22.0,
    )

    assert off.as_dict() == {"fires_at": FIRES_AT.isoformat(), "turn_off": True}
    assert on.as_dict() == {"fires_at": FIRES_AT.isoformat(), "turn_on": True}
    assert temperature.as_dict() == {
        "fires_at": FIRES_AT.isoformat(),
        "temperature_celsius": 22.0,
    }
    assert on_to_temperature.as_dict() == {
        "fires_at": FIRES_AT.isoformat(),
        "turn_on": True,
        "temperature_celsius": 22.0,
    }
