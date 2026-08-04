"""Tests for saved-flow switch entities and Climate Flow actions."""

import asyncio

import pytest
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    SERVICE_SET_HVAC_MODE,
)
from homeassistant.components.switch import SERVICE_TURN_ON
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigSubentry,
    SubentryFlowContext,
)
from homeassistant.const import ATTR_ENTITY_ID, EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
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

    reconfigure = await hass.config_entries.subentries.async_init(
        (entry.entry_id, FLOW_SUBENTRY_TYPE),
        context=SubentryFlowContext(
            source=SOURCE_RECONFIGURE, subentry_id="bedroom-flow"
        ),
    )
    assert reconfigure["type"] is FlowResultType.ABORT
    assert reconfigure["reason"] == "flow_active"

    await hass.services.async_call(
        DOMAIN,
        "cancel",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == "off"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_conflicting_flow_start_keeps_switch_idle_and_is_translated(
    hass: HomeAssistant,
) -> None:
    """Test an overlapping flow start reports its target and remains idle."""
    hass.states.async_set(
        "climate.bedroom",
        "cool",
        {
            ATTR_HVAC_MODES: ["cool", "off"],
            ATTR_MIN_TEMP: 16,
            ATTR_MAX_TEMP: 30,
        },
    )
    async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    entry = _entry()
    overlap = ConfigSubentry(
        subentry_id="overlap-flow",
        subentry_type=FLOW_SUBENTRY_TYPE,
        title="Overlapping Flow",
        unique_id="overlapping-flow",
        data=SavedFlow(
            flow_id="overlapping-flow",
            targets=("climate.bedroom",),
            stages=(
                FlowStage(ClimateState(hvac_mode="cool"), duration_seconds=30),
                FlowStage(ClimateState(hvac_mode="off")),
            ),
        ).as_dict(),
    )
    entry.add_to_hass(hass)
    assert hass.config_entries.async_add_subentry(entry, overlap)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "start",
        {ATTR_ENTITY_ID: "switch.bedroom_night"},
        blocking=True,
    )
    state_changes: list[Event] = []
    unsubscribe = hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        lambda event: (
            state_changes.append(event)
            if event.data["entity_id"] == "switch.overlapping_flow"
            else None
        ),
    )
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.overlapping_flow"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert (
        str(error.value)
        == "climate.bedroom is already controlled by another active flow"
    )
    assert hass.states.get("switch.overlapping_flow").state == "off"
    assert not state_changes
    await asyncio.sleep(0.15)
    await hass.async_block_till_done()
    assert state_changes[-1].data["new_state"].state == "off"
    unsubscribe()


async def test_subentry_changes_add_and_remove_switches_without_stopping_runs(
    hass: HomeAssistant,
) -> None:
    """Test an unrelated saved-flow change leaves an active run alone."""
    hass.states.async_set(
        "climate.bedroom",
        "cool",
        {
            ATTR_HVAC_MODES: ["cool", "off"],
            ATTR_MIN_TEMP: 16,
            ATTR_MAX_TEMP: 30,
        },
    )
    hass.states.async_set(
        "climate.office",
        "cool",
        {
            ATTR_HVAC_MODES: ["cool", "off"],
            ATTR_MIN_TEMP: 16,
            ATTR_MAX_TEMP: 30,
        },
    )
    async_mock_service(hass, "climate", SERVICE_SET_HVAC_MODE)
    entry = _entry()
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN,
        "start",
        {ATTR_ENTITY_ID: "switch.bedroom_night"},
        blocking=True,
    )

    office_flow = SavedFlow(
        flow_id="office-night",
        targets=("climate.office",),
        stages=(
            FlowStage(ClimateState(hvac_mode="cool"), duration_seconds=30),
            FlowStage(ClimateState(hvac_mode="off")),
        ),
    )
    office_subentry = ConfigSubentry(
        subentry_id="office-flow",
        subentry_type=FLOW_SUBENTRY_TYPE,
        title="Office Night",
        unique_id="office-night",
        data=office_flow.as_dict(),
    )

    assert hass.config_entries.async_add_subentry(entry, office_subentry)
    await hass.async_block_till_done()

    assert hass.states.get("switch.bedroom_night").state == "on"
    assert hass.states.get("switch.office_night").state == "off"

    assert hass.config_entries.async_remove_subentry(entry, office_subentry.subentry_id)
    await hass.async_block_till_done()

    assert hass.states.get("switch.bedroom_night").state == "on"
    assert hass.states.get("switch.office_night") is None
    assert await hass.config_entries.async_unload(entry.entry_id)
