"""Tests for the pending-transitions sensor entity."""

from homeassistant.components.climate.const import ATTR_HVAC_MODES
from homeassistant.const import SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.climate_flow.const import DOMAIN


async def test_sensor_reports_pending_transitions_and_updates_live(
    hass: HomeAssistant,
) -> None:
    """Test the sensor's state and attributes track scheduled transitions."""
    hass.states.async_set("climate.bedroom", "cool", {ATTR_HVAC_MODES: ["off", "cool"]})
    async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    entity_id = "sensor.pending_transitions"
    assert hass.states.get(entity_id).state == "0"
    assert "climate.bedroom" not in hass.states.get(entity_id).attributes

    await entry.runtime_data.transitions.async_schedule(
        "climate.bedroom", delay_seconds=30, turn_off=True
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "1"
    assert state.attributes["climate.bedroom"]["turn_off"] is True

    await entry.runtime_data.transitions.async_cancel("climate.bedroom")
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "0"
    assert await hass.config_entries.async_unload(entry.entry_id)
