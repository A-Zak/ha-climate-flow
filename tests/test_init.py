"""Tests for Climate Flow setup and unloading."""

import json
from pathlib import Path

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climate_flow import CONFIG_SCHEMA
from custom_components.climate_flow.const import DOMAIN


def test_ac_card_asset_declares_the_supported_controls() -> None:
    """Test the distributed AC card exposes its documented interface."""
    card_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / DOMAIN
        / "www"
        / "climate-flow-ac-card.js"
    )

    card = card_path.read_text()

    assert 'customElements.define("climate-flow-ac-card"' in card
    assert '"set_temperature"' in card
    assert '"set_swing_mode"' in card
    assert '"turn_on"' in card
    assert '"turn_off"' in card
    assert '"fixed 1"' in card
    assert '"fixed 3"' in card
    assert '"fixed 5"' in card
    assert 'class="swing-icon"' in card
    assert "rotate(${index * 22.5}" in card
    assert "current_temperature" in card
    assert "power-cleaning" in card
    assert "power-on" in card
    assert "power-off" in card
    assert "swing-state" in card
    assert "mode-state" in card
    assert "border: 3px" in card
    assert '"hass-action"' in card
    assert 'action: "more-info"' in card


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
    assert flow["initiate_flow"]["user"] == "Add climate flow"
    assert "title" not in flow


def test_manifest_declares_the_http_dependency_for_the_card_asset() -> None:
    """Test the card's static route declares its Home Assistant dependency."""
    manifest_path = (
        Path(__file__).parents[1] / "custom_components" / DOMAIN / "manifest.json"
    )

    manifest = json.loads(manifest_path.read_text())

    assert "http" in manifest["dependencies"]


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
