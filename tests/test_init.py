"""Tests for Climate Flow setup and unloading."""

import json
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from homeassistant.components.climate.const import ATTR_HVAC_MODES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.climate_flow import CONFIG_SCHEMA
from custom_components.climate_flow.const import DOMAIN
from custom_components.climate_flow.transition_runtime import (
    STORAGE_KEY,
    STORAGE_VERSION,
)


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
    assert "_normalizeSwingMode" in card
    assert "border-color: currentColor" in card
    assert "_lastActiveSwingMode" not in card
    assert "self_cleaning" in card
    assert "preset_mode" in card
    assert "attributes.swing_modes" in card
    assert "button:active:not(:disabled)" in card
    assert "work-indicator" in card
    assert "@keyframes rotate-work-indicator" in card
    assert "await this._hass.callService" in card
    assert 'type="range"' in card
    assert "toggle-temperature-slider" in card
    assert "temperature-slider" in card
    assert "temperature-section" in card
    assert "bottom: calc(100% + 4px)" in card
    assert "sensor.pending_transitions" in card
    assert '"schedule_transition"' in card
    assert '"cancel_transition"' in card
    assert "toggle-transition-panel" in card
    assert "transition-panel" in card
    assert 'data-target="off"' in card
    assert 'data-target="on"' in card
    assert 'data-target="temp"' in card
    assert "delay_seconds" in card
    assert "_formatCountdown" in card
    assert "_transitionTickInterval" in card
    assert "disconnectedCallback" in card


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_ac_card_asset_is_syntactically_valid_javascript() -> None:
    """Test the distributed AC card parses without a syntax error.

    A string-content assertion cannot catch a broken script (for example,
    mixing `??` and `||` in one expression, which V8 rejects). Browsers load
    this asset as a module and fail the whole card silently, so verify it
    parses wherever Node happens to be available.
    """
    card_path = (
        Path(__file__).parents[1]
        / "custom_components"
        / DOMAIN
        / "www"
        / "climate-flow-ac-card.js"
    )

    result = subprocess.run(
        ["node", "--check", str(card_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


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


async def test_setup_recovers_a_pending_transition_from_storage(
    hass: HomeAssistant,
) -> None:
    """Test a persisted transition resumes when the config entry loads."""
    hass.states.async_set("climate.bedroom", "cool", {ATTR_HVAC_MODES: ["off", "cool"]})
    async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    future = (dt_util.utcnow() + timedelta(seconds=30)).isoformat()
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    await store.async_save({"climate.bedroom": {"fires_at": future, "turn_off": True}})
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.transitions.pending("climate.bedroom") is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_unload_keeps_a_pending_transition_for_the_next_load(
    hass: HomeAssistant,
) -> None:
    """Test unloading the entry does not lose an unfired pending transition."""
    hass.states.async_set("climate.bedroom", "cool", {ATTR_HVAC_MODES: ["off", "cool"]})
    async_mock_service(hass, "climate", SERVICE_TURN_OFF)
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await entry.runtime_data.transitions.async_schedule(
        "climate.bedroom", delay_seconds=30, turn_off=True
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    assert "climate.bedroom" in await store.async_load()
    await store.async_save({})
