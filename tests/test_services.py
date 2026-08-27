"""Tests for the schedule_transition and cancel_transition actions."""

import pytest
import voluptuous as vol
from homeassistant.components.climate.const import ATTR_HVAC_MODES
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climate_flow.const import DOMAIN


async def test_schedule_transition_schedules_a_pending_transition(
    hass: HomeAssistant,
) -> None:
    """Test the service reaches the loaded entry's transition runtime."""
    hass.states.async_set("climate.bedroom", "cool", {ATTR_HVAC_MODES: ["off", "cool"]})
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "schedule_transition",
        {
            ATTR_ENTITY_ID: "climate.bedroom",
            "delay_seconds": 30,
            "turn_off": True,
        },
        blocking=True,
    )

    assert entry.runtime_data.transitions.pending("climate.bedroom") is not None
    await entry.runtime_data.transitions.async_cancel("climate.bedroom")
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_cancel_transition_clears_a_pending_transition(
    hass: HomeAssistant,
) -> None:
    """Test the cancel action removes a previously scheduled transition."""
    hass.states.async_set("climate.bedroom", "cool", {ATTR_HVAC_MODES: ["off", "cool"]})
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN,
        "schedule_transition",
        {ATTR_ENTITY_ID: "climate.bedroom", "delay_seconds": 30, "turn_off": True},
        blocking=True,
    )

    await hass.services.async_call(
        DOMAIN,
        "cancel_transition",
        {ATTR_ENTITY_ID: "climate.bedroom"},
        blocking=True,
    )

    assert entry.runtime_data.transitions.pending("climate.bedroom") is None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_schedule_transition_rejects_a_non_climate_entity(
    hass: HomeAssistant,
) -> None:
    """Test the service schema rejects a target outside the climate domain."""
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "schedule_transition",
            {
                ATTR_ENTITY_ID: "switch.bedroom_night",
                "delay_seconds": 30,
                "turn_off": True,
            },
            blocking=True,
        )
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_schedule_transition_schedules_a_turn_on_transition(
    hass: HomeAssistant,
) -> None:
    """Test the schema and handler accept a turn-on target state."""
    hass.states.async_set("climate.bedroom", "off", {ATTR_HVAC_MODES: ["off", "cool"]})
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "schedule_transition",
        {ATTR_ENTITY_ID: "climate.bedroom", "delay_seconds": 30, "turn_on": True},
        blocking=True,
    )

    assert entry.runtime_data.transitions.pending("climate.bedroom").turn_on is True
    await entry.runtime_data.transitions.async_cancel("climate.bedroom")
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_schedule_transition_schedules_turn_on_combined_with_a_temperature(
    hass: HomeAssistant,
) -> None:
    """Test the schema accepts turning on to a specific temperature.

    This is what the card sends for an AC that is currently off: one
    combined transition, not two independent ones.
    """
    hass.states.async_set("climate.bedroom", "off", {ATTR_HVAC_MODES: ["off", "cool"]})
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "schedule_transition",
        {
            ATTR_ENTITY_ID: "climate.bedroom",
            "delay_seconds": 30,
            "turn_on": True,
            "temperature": 22.0,
        },
        blocking=True,
    )

    pending = entry.runtime_data.transitions.pending("climate.bedroom")
    assert pending.turn_on is True
    assert pending.temperature_celsius == 22.0
    await entry.runtime_data.transitions.async_cancel("climate.bedroom")
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "extra_fields",
    [
        {"turn_off": True, "temperature": 22.0},
        {"turn_off": True, "turn_on": True},
        {},
    ],
)
async def test_schedule_transition_requires_a_valid_target_state(
    hass: HomeAssistant, extra_fields: dict[str, object]
) -> None:
    """Test the schema rejects turn_off combined with anything, or nothing at all."""
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "schedule_transition",
            {ATTR_ENTITY_ID: "climate.bedroom", "delay_seconds": 30, **extra_fields},
            blocking=True,
        )
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_schedule_transition_without_a_loaded_entry_is_translated(
    hass: HomeAssistant,
) -> None:
    """Test calling the action with no loaded Climate Flow entry is clear."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "schedule_transition",
            {
                ATTR_ENTITY_ID: "climate.bedroom",
                "delay_seconds": 30,
                "turn_off": True,
            },
            blocking=True,
        )
