"""Tests for the Home Assistant adapter running pending transitions."""

import asyncio
from datetime import timedelta

from homeassistant.components.climate.const import (
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.climate_flow.transition_runtime import (
    STORAGE_KEY,
    STORAGE_VERSION,
    TransitionRuntime,
)


def _add_climate(hass: HomeAssistant, entity_id: str = "climate.bedroom") -> None:
    """Add a climate entity supporting off and a wide temperature range."""
    hass.states.async_set(
        entity_id,
        "cool",
        {ATTR_HVAC_MODES: ["off", "cool"], ATTR_MIN_TEMP: 16, ATTR_MAX_TEMP: 30},
    )


async def test_schedule_fires_turn_off_after_the_delay(hass: HomeAssistant) -> None:
    """Test a turn-off transition calls the climate service once it fires."""
    _add_climate(hass)
    calls = async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    runtime = TransitionRuntime(hass)

    await runtime.async_schedule("climate.bedroom", delay_seconds=0.01, turn_off=True)
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()

    assert calls[0].data == {ATTR_ENTITY_ID: "climate.bedroom"}
    assert runtime.pending("climate.bedroom") is None


async def test_schedule_fires_turn_on_after_the_delay(hass: HomeAssistant) -> None:
    """Test a turn-on transition calls the climate service once it fires."""
    _add_climate(hass)
    calls = async_mock_service(hass, "climate", SERVICE_TURN_ON)
    runtime = TransitionRuntime(hass)

    await runtime.async_schedule("climate.bedroom", delay_seconds=0.01, turn_on=True)
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()

    assert calls[0].data == {ATTR_ENTITY_ID: "climate.bedroom"}
    assert runtime.pending("climate.bedroom") is None


async def test_schedule_fires_set_temperature_after_the_delay(
    hass: HomeAssistant,
) -> None:
    """Test a temperature transition calls set_temperature once it fires."""
    _add_climate(hass)
    calls = async_mock_service(hass, "climate", SERVICE_SET_TEMPERATURE)
    runtime = TransitionRuntime(hass)

    await runtime.async_schedule(
        "climate.bedroom", delay_seconds=0.01, temperature_celsius=22.0
    )
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()

    assert calls[0].data == {ATTR_ENTITY_ID: "climate.bedroom", ATTR_TEMPERATURE: 22.0}


async def test_schedule_fires_turn_on_then_set_temperature_when_combined(
    hass: HomeAssistant,
) -> None:
    """Test "turn on to this temperature" powers on before setting the target.

    This is the transition an off AC schedules: a single combined action,
    not two independent ones.
    """
    _add_climate(hass)
    hass.states.async_set(
        "climate.bedroom",
        "off",
        {ATTR_HVAC_MODES: ["off", "cool"], ATTR_MIN_TEMP: 16, ATTR_MAX_TEMP: 30},
    )
    on_calls = async_mock_service(hass, "climate", SERVICE_TURN_ON)
    temperature_calls = async_mock_service(hass, "climate", SERVICE_SET_TEMPERATURE)
    runtime = TransitionRuntime(hass)

    await runtime.async_schedule(
        "climate.bedroom", delay_seconds=0.01, turn_on=True, temperature_celsius=22.0
    )
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()

    assert on_calls[0].data == {ATTR_ENTITY_ID: "climate.bedroom"}
    assert temperature_calls[0].data == {
        ATTR_ENTITY_ID: "climate.bedroom",
        ATTR_TEMPERATURE: 22.0,
    }


async def test_cancel_prevents_the_scheduled_service_call(hass: HomeAssistant) -> None:
    """Test cancelling before the delay elapses suppresses the service call."""
    _add_climate(hass)
    calls = async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    runtime = TransitionRuntime(hass)
    await runtime.async_schedule("climate.bedroom", delay_seconds=0.01, turn_off=True)

    await runtime.async_cancel("climate.bedroom")
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()

    assert calls == []
    assert runtime.pending("climate.bedroom") is None


async def test_rescheduling_a_target_replaces_the_pending_transition(
    hass: HomeAssistant,
) -> None:
    """Test scheduling again for the same target cancels the earlier timer."""
    _add_climate(hass)
    off_calls = async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    temperature_calls = async_mock_service(hass, "climate", SERVICE_SET_TEMPERATURE)
    runtime = TransitionRuntime(hass)
    await runtime.async_schedule("climate.bedroom", delay_seconds=0.01, turn_off=True)

    await runtime.async_schedule(
        "climate.bedroom", delay_seconds=0.05, temperature_celsius=22.0
    )
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()

    assert off_calls == []
    assert len(temperature_calls) == 1


async def test_pending_summary_reports_active_transitions(hass: HomeAssistant) -> None:
    """Test the summary used by the sensor reflects scheduled transitions."""
    _add_climate(hass)
    async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    runtime = TransitionRuntime(hass)

    await runtime.async_schedule("climate.bedroom", delay_seconds=30, turn_off=True)

    summary = runtime.pending_summary()
    assert set(summary) == {"climate.bedroom"}
    assert summary["climate.bedroom"]["turn_off"] is True
    assert "fires_at" in summary["climate.bedroom"]

    await runtime.async_cancel("climate.bedroom")


async def test_schedule_persists_to_storage(hass: HomeAssistant) -> None:
    """Test scheduling writes the pending transition to disk."""
    _add_climate(hass)
    async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    runtime = TransitionRuntime(hass)

    await runtime.async_schedule("climate.bedroom", delay_seconds=30, turn_off=True)

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    data = await store.async_load()
    assert "climate.bedroom" in data
    assert data["climate.bedroom"]["turn_off"] is True

    await runtime.async_cancel("climate.bedroom")


async def test_cancel_removes_the_target_from_storage(hass: HomeAssistant) -> None:
    """Test cancelling clears the persisted record."""
    _add_climate(hass)
    async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    runtime = TransitionRuntime(hass)
    await runtime.async_schedule("climate.bedroom", delay_seconds=30, turn_off=True)

    await runtime.async_cancel("climate.bedroom")

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    assert await store.async_load() == {}


async def test_recovery_reschedules_a_still_future_transition(
    hass: HomeAssistant,
) -> None:
    """Test a fresh runtime resumes a persisted, not-yet-due transition.

    The persisted record is written directly to storage, rather than via a
    live TransitionRuntime, because a real restart destroys the old
    in-process timer along with the rest of the process -- keeping the old
    runtime alive here would double-fire the same target.
    """
    _add_climate(hass)
    calls = async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    future = (dt_util.utcnow() + timedelta(seconds=0.05)).isoformat()
    await store.async_save({"climate.bedroom": {"fires_at": future, "turn_off": True}})

    recovered = TransitionRuntime(hass)
    await recovered.async_load_and_recover()

    assert recovered.pending("climate.bedroom") is not None
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_recovery_fires_immediately_for_an_elapsed_transition(
    hass: HomeAssistant,
) -> None:
    """Test a transition due while Home Assistant was offline fires right away."""
    _add_climate(hass)
    calls = async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    past = dt_util.utcnow() - timedelta(minutes=5)
    await store.async_save(
        {"climate.bedroom": {"fires_at": past.isoformat(), "turn_off": True}}
    )

    runtime = TransitionRuntime(hass)
    await runtime.async_load_and_recover()
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert runtime.pending("climate.bedroom") is None
    assert await store.async_load() == {}


async def test_recovery_skips_a_malformed_record(hass: HomeAssistant) -> None:
    """Test one invalid persisted record does not block recovering the rest."""
    _add_climate(hass, "climate.bedroom")
    _add_climate(hass, "climate.lounge")
    calls = async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    future = (dt_util.utcnow() + timedelta(seconds=30)).isoformat()
    await store.async_save(
        {
            "climate.bedroom": {"turn_off": True, "temperature_celsius": 22.0},
            "climate.lounge": {"fires_at": future, "turn_off": True},
        }
    )

    runtime = TransitionRuntime(hass)
    await runtime.async_load_and_recover()

    assert runtime.pending("climate.bedroom") is None
    assert runtime.pending("climate.lounge") is not None
    assert calls == []

    await runtime.async_cancel("climate.lounge")


async def test_stop_cancels_timers_but_keeps_storage_for_the_next_load(
    hass: HomeAssistant,
) -> None:
    """Test stopping (config-entry unload/reload) never loses a transition.

    Unlike async_cancel, async_stop must not erase the persisted record: a
    reload should resume exactly like a Home Assistant restart would.
    """
    _add_climate(hass)
    calls = async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    runtime = TransitionRuntime(hass)
    await runtime.async_schedule("climate.bedroom", delay_seconds=0.02, turn_off=True)

    await runtime.async_stop()
    await asyncio.sleep(0.05)
    await hass.async_block_till_done()

    assert calls == []
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    assert "climate.bedroom" in await store.async_load()

    resumed = TransitionRuntime(hass)
    await resumed.async_load_and_recover()
    assert len(calls) == 1
