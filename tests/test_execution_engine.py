"""Tests for the Home Assistant-independent flow execution engine."""

from datetime import UTC, datetime

import pytest

from custom_components.climate_flow.execution_engine import (
    FlowConflictError,
    FlowExecutionEngine,
)
from custom_components.climate_flow.flow import ClimateState, FlowStage, SavedFlow

NOW = datetime(2026, 8, 4, tzinfo=UTC)


def _flow(*targets: str) -> SavedFlow:
    """Return a valid saved two-stage flow."""
    return SavedFlow(
        flow_id="test-flow",
        targets=targets,
        stages=(
            FlowStage(ClimateState(hvac_mode="cool"), duration_seconds=60),
            FlowStage(ClimateState(hvac_mode="off")),
        ),
    )


def test_engine_starts_disjoint_flows_and_reserves_targets() -> None:
    """Test disjoint flows become independently active."""
    engine = FlowExecutionEngine()

    started = engine.start_many(
        {"first": _flow("climate.first"), "second": _flow("climate.second")}, NOW
    )

    assert {run.flow_key for run in started} == {"first", "second"}
    assert engine.owner_of("climate.first") == "first"
    assert engine.owner_of("climate.second") == "second"
    assert engine.is_active("first")
    assert engine.is_active("second")


def test_engine_rejects_an_atomic_batch_with_overlapping_targets() -> None:
    """Test a conflict leaves every new flow idle."""
    engine = FlowExecutionEngine()

    with pytest.raises(FlowConflictError):
        engine.start_many(
            {"first": _flow("climate.shared"), "second": _flow("climate.shared")},
            NOW,
        )

    assert not engine.is_active("first")
    assert not engine.is_active("second")
    assert engine.owner_of("climate.shared") is None


def test_engine_start_is_idempotent_and_rejects_an_existing_owner() -> None:
    """Test an active flow is a no-op but another owner is rejected."""
    engine = FlowExecutionEngine()
    first = _flow("climate.shared")
    engine.start_many({"first": first}, NOW)

    assert engine.start_many({"first": first}, NOW) == ()
    with pytest.raises(FlowConflictError):
        engine.start_many({"second": _flow("climate.shared")}, NOW)


def test_engine_advances_once_and_releases_on_completion() -> None:
    """Test a stale stage callback cannot advance a flow twice."""
    engine = FlowExecutionEngine()
    run = engine.start_many({"first": _flow("climate.first")}, NOW)[0]

    advanced = engine.advance("first", run.token, NOW)

    assert advanced is not None
    assert advanced.current_stage == 1
    assert engine.advance("first", run.token, NOW) is None
    assert engine.complete("first", run.token)
    assert not engine.is_active("first")
    assert engine.owner_of("climate.first") is None


def test_engine_drops_targets_and_finishes_when_none_remain() -> None:
    """Test target loss releases ownership after the final target is dropped."""
    engine = FlowExecutionEngine()
    run = engine.start_many({"first": _flow("climate.one", "climate.two")}, NOW)[0]

    assert engine.drop_target("first", run.token, "climate.one") is False
    assert engine.active_run("first").targets == ("climate.two",)
    assert engine.drop_target("first", run.token, "climate.two") is True
    assert not engine.is_active("first")
    assert engine.owner_of("climate.one") is None
    assert engine.owner_of("climate.two") is None


def test_engine_cancel_is_idempotent() -> None:
    """Test cancellation releases all owned targets only once."""
    engine = FlowExecutionEngine()
    run = engine.start_many({"first": _flow("climate.first")}, NOW)[0]

    assert engine.cancel("first", run.token)
    assert not engine.cancel("first", run.token)
    assert engine.owner_of("climate.first") is None
