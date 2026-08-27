"""Tests for the Home Assistant-independent pending-transition engine."""

from datetime import UTC, datetime

from custom_components.climate_flow.transition import PendingTransition
from custom_components.climate_flow.transition_engine import TransitionEngine

FIRES_AT = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


def _transition(target: str = "climate.bedroom") -> PendingTransition:
    """Return a simple turn-off transition for one target."""
    return PendingTransition(target=target, fires_at=FIRES_AT, turn_off=True)


def test_engine_schedules_and_reports_a_pending_transition() -> None:
    """Test scheduling stores the transition and returns a token."""
    engine = TransitionEngine()
    transition = _transition()

    token = engine.schedule(transition)

    assert isinstance(token, int)
    assert engine.pending("climate.bedroom") == transition


def test_engine_reports_no_pending_transition_for_an_unscheduled_target() -> None:
    """Test an untouched target has no pending transition."""
    engine = TransitionEngine()

    assert engine.pending("climate.bedroom") is None


def test_engine_rescheduling_a_target_replaces_and_invalidates_the_old_token() -> None:
    """Test scheduling a second transition for the same target replaces the first."""
    engine = TransitionEngine()
    first_token = engine.schedule(_transition())
    replacement = PendingTransition(
        target="climate.bedroom", fires_at=FIRES_AT, temperature_celsius=22.0
    )

    second_token = engine.schedule(replacement)

    assert engine.pending("climate.bedroom") == replacement
    assert engine.fire("climate.bedroom", first_token) is None
    assert engine.fire("climate.bedroom", second_token) == replacement


def test_engine_fire_clears_the_pending_transition() -> None:
    """Test firing removes the transition so it cannot fire twice."""
    engine = TransitionEngine()
    transition = _transition()
    token = engine.schedule(transition)

    assert engine.fire("climate.bedroom", token) == transition
    assert engine.pending("climate.bedroom") is None
    assert engine.fire("climate.bedroom", token) is None


def test_engine_fire_rejects_a_stale_token() -> None:
    """Test a stale token cannot fire after cancellation and rescheduling."""
    engine = TransitionEngine()
    token = engine.schedule(_transition())
    engine.cancel("climate.bedroom", token)

    assert engine.fire("climate.bedroom", token) is None


def test_engine_cancel_is_idempotent_and_target_scoped() -> None:
    """Test cancellation only clears its own target, once."""
    engine = TransitionEngine()
    token = engine.schedule(_transition("climate.bedroom"))
    other_token = engine.schedule(_transition("climate.lounge"))

    assert engine.cancel("climate.bedroom", token) is True
    assert engine.cancel("climate.bedroom", token) is False
    assert engine.pending("climate.bedroom") is None
    assert engine.pending("climate.lounge") is not None

    assert engine.cancel("climate.lounge", other_token) is True
