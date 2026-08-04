"""Tests for Home Assistant execution of saved Climate Flow definitions."""

from homeassistant.components.climate.const import (
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODES,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.climate_flow.flow import ClimateState, FlowStage, SavedFlow
from custom_components.climate_flow.runtime import ClimateFlowRuntime, FlowDefinition


def _add_climate(hass: HomeAssistant, entity_id: str) -> None:
    """Add a climate entity supporting every Milestone 3 control."""
    hass.states.async_set(
        entity_id,
        "cool",
        {
            ATTR_HVAC_MODES: ["off", "cool"],
            ATTR_FAN_MODES: ["auto", "high"],
            ATTR_SWING_MODES: ["off", "vertical"],
            ATTR_PRESET_MODES: ["none", "eco"],
            ATTR_MIN_TEMP: 16,
            ATTR_MAX_TEMP: 30,
        },
    )


def _runtime(hass: HomeAssistant, *, duration: float = 30) -> ClimateFlowRuntime:
    """Return a runtime with one saved flow."""
    flow = SavedFlow(
        flow_id="bedroom-night",
        targets=("climate.bedroom",),
        stages=(
            FlowStage(
                ClimateState(
                    hvac_mode="cool",
                    temperature_celsius=22,
                    fan_mode="high",
                    swing_mode="vertical",
                    preset_mode="eco",
                ),
                duration_seconds=duration,
            ),
            FlowStage(ClimateState(hvac_mode="off")),
        ),
    )
    runtime = ClimateFlowRuntime(hass, "entry")
    runtime.load_definitions((FlowDefinition("flow", "Bedroom", flow),))
    return runtime


async def test_runtime_applies_all_stage_controls_and_cancels(
    hass: HomeAssistant,
) -> None:
    """Test Stage 1 applies all saved climate controls in a stable order."""
    _add_climate(hass, "climate.bedroom")
    calls = [
        async_mock_service(hass, "climate", service)
        for service in (
            SERVICE_SET_HVAC_MODE,
            SERVICE_SET_TEMPERATURE,
            SERVICE_SET_PRESET_MODE,
            SERVICE_SET_SWING_MODE,
            SERVICE_SET_FAN_MODE,
        )
    ]
    runtime = _runtime(hass)

    await runtime.async_start_many(("flow",))

    assert runtime.is_active("flow")
    assert calls[0][0].data == {
        ATTR_ENTITY_ID: "climate.bedroom",
        "hvac_mode": "cool",
    }
    assert calls[1][0].data == {
        ATTR_ENTITY_ID: "climate.bedroom",
        ATTR_TEMPERATURE: 22,
    }
    assert len(calls[2]) == len(calls[3]) == len(calls[4]) == 1

    await runtime.async_cancel("flow")

    assert not runtime.is_active("flow")


async def test_runtime_drops_an_unavailable_target(hass: HomeAssistant) -> None:
    """Test an unavailable target ends a one-target flow and releases it."""
    _add_climate(hass, "climate.bedroom")
    for service in (
        SERVICE_SET_HVAC_MODE,
        SERVICE_SET_TEMPERATURE,
        SERVICE_SET_PRESET_MODE,
        SERVICE_SET_SWING_MODE,
        SERVICE_SET_FAN_MODE,
    ):
        async_mock_service(hass, "climate", service)
    runtime = _runtime(hass)
    await runtime.async_start_many(("flow",))

    hass.states.async_set("climate.bedroom", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    assert not runtime.is_active("flow")
    assert runtime.engine.owner_of("climate.bedroom") is None


async def test_runtime_applies_stage_two_and_completes_immediately(
    hass: HomeAssistant,
) -> None:
    """Test Stage 2 applies once and does not schedule another duration."""
    _add_climate(hass, "climate.bedroom")
    hvac_calls = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    for service in (
        SERVICE_SET_TEMPERATURE,
        SERVICE_SET_PRESET_MODE,
        SERVICE_SET_SWING_MODE,
        SERVICE_SET_FAN_MODE,
    ):
        async_mock_service(hass, "climate", service)
    runtime = _runtime(hass)
    await runtime.async_start_many(("flow",))
    run = runtime.engine.active_run("flow")

    await runtime._async_advance_to_stage_two(run, None)

    assert [call.data["hvac_mode"] for call in hvac_calls] == ["cool", "off"]
    assert not runtime.is_active("flow")
