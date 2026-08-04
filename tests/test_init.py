"""Tests for Climate Flow setup and unloading."""

import json
from pathlib import Path

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climate_flow import CONFIG_SCHEMA
from custom_components.climate_flow.const import DOMAIN


def test_config_entry_only_schema_accepts_empty_configuration() -> None:
    """Test Climate Flow declares its config-entry-only setup contract."""
    assert CONFIG_SCHEMA({}) == {}


def test_flow_subentry_translation_uses_current_schema() -> None:
    """Test the flow subentry defines its type without a deprecated title."""
    translations_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / DOMAIN
        / "translations"
        / "en.json"
    )
    translations = json.loads(translations_path.read_text())
    flow = translations["config_subentries"]["flow"]

    assert flow["entry_type"] == "Climate flow"
    assert "title" not in flow


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """Test setting up and unloading a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
