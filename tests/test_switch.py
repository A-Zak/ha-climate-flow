"""Tests for saved-flow switch entities and Climate Flow actions."""

from homeassistant.components.climate.const import (
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    SERVICE_SET_HVAC_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.climate_flow.const import DOMAIN, FLOW_SUBENTRY_TYPE
from custom_components.climate_flow.flow import ClimateState, FlowStage, SavedFlow


def _entry() -> MockConfigEntry:
    """Return an entry with one executable saved-flow subentry."""
    flow = SavedFlow(
        flow_id="bedroom-night",
        targets=("climate.bedroom",),
        stages=(
            FlowStage(ClimateState(hvac_mode="cool"), duration_seconds=30),
            FlowStage(ClimateState(hvac_mode="off")),
        ),
    )
    return MockConfigEntry(
        domain=DOMAIN,
        title="Climate Flow",
        subentries_data=(
            {
                "subentry_id": "bedroom-flow",
                "subentry_type": FLOW_SUBENTRY_TYPE,
                "title": "Bedroom Night",
                "unique_id": "bedroom-night",
                "data": flow.as_dict(),
            },
        ),
    )


async def test_switch_and_actions_start_and_cancel_saved_flow(
    hass: HomeAssistant,
) -> None:
    """Test the stable switch backs both standard and Climate Flow actions."""
    hass.states.async_set(
        "climate.bedroom",
        "cool",
        {
            ATTR_HVAC_MODES: ["cool", "off"],
            ATTR_MIN_TEMP: 16,
            ATTR_MAX_TEMP: 30,
        },
    )
    climate_calls = async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    entry = _entry()
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    entity_id = "switch.bedroom_night"
    assert hass.states.get(entity_id).state == "off"
    assert hass.states.get(entity_id).attributes["flow_id"] == "bedroom-night"

    await hass.services.async_call(
        DOMAIN,
        "start",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == "on"
    assert climate_calls[0].data[ATTR_ENTITY_ID] == "climate.bedroom"
    assert hass.states.get(entity_id).attributes["current_stage"] == 1

    await hass.services.async_call(
        DOMAIN,
        "cancel",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == "off"
    assert await hass.config_entries.async_unload(entry.entry_id)
