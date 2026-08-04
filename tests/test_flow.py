"""Tests for saved Climate Flow definitions."""

import pytest
from homeassistant.components.climate.const import (
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODES,
)
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    SubentryFlowContext,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climate_flow.config_flow import _duration_seconds
from custom_components.climate_flow.const import (
    CONF_DURATION,
    CONF_FLOW_ID,
    CONF_HVAC_MODE,
    CONF_STAGES,
    CONF_TARGETS,
    CONF_TEMPERATURE_CELSIUS,
    DOMAIN,
    FLOW_SUBENTRY_TYPE,
)
from custom_components.climate_flow.flow import (
    ClimateState,
    FlowStage,
    SavedFlow,
    is_valid_flow_id,
)
from custom_components.climate_flow.flow_capabilities import shared_capabilities


def _climate_attributes(
    *,
    hvac_modes: list[str] | None = None,
    fan_modes: list[str] | None = None,
    swing_modes: list[str] | None = None,
    preset_modes: list[str] | None = None,
) -> dict[str, object]:
    """Return a representative climate entity capability set."""
    return {
        ATTR_HVAC_MODES: hvac_modes
        if hvac_modes is not None
        else ["off", "cool", "heat"],
        ATTR_FAN_MODES: fan_modes if fan_modes is not None else ["auto", "high"],
        ATTR_SWING_MODES: swing_modes
        if swing_modes is not None
        else ["off", "vertical"],
        ATTR_PRESET_MODES: preset_modes
        if preset_modes is not None
        else ["none", "eco"],
        ATTR_MIN_TEMP: 16,
        ATTR_MAX_TEMP: 30,
    }


def _add_climate(hass: HomeAssistant, entity_id: str, **kwargs: object) -> None:
    """Add a climate state with configurable capabilities."""
    hass.states.async_set(entity_id, "cool", _climate_attributes(**kwargs))


def _stage_input(
    hvac_mode: str, *, duration: dict[str, float] | None = None
) -> dict[str, object]:
    """Return a minimal stage form submission."""
    data: dict[str, object] = {CONF_HVAC_MODE: hvac_mode}
    if duration is not None:
        data[CONF_DURATION] = duration
    return data


def _flow_input(
    name: str,
    flow_id: str,
    targets: list[str],
    *,
    stage_1_duration: dict[str, float] | None = None,
) -> dict[str, object]:
    """Return a complete submission for the sectioned saved-flow form."""
    return {
        "flow": {"name": name, CONF_FLOW_ID: flow_id, CONF_TARGETS: targets},
        "stage_1": _stage_input(
            "cool",
            duration={"minutes": 30} if stage_1_duration is None else stage_1_duration,
        ),
        "stage_2": _stage_input("off"),
    }


async def _start_flow(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, object]:
    """Start a saved-flow subentry creation flow."""
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, FLOW_SUBENTRY_TYPE),
        context=SubentryFlowContext(source=SOURCE_USER),
    )


async def _create_two_stage_flow(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    name: str = "Bedroom Night Cooling",
    flow_id: str = "bedroom-night-cooling",
    targets: list[str] | None = None,
) -> None:
    """Create a saved two-stage flow through its UI flow."""
    if targets is None:
        targets = ["climate.bedroom"]
    result = await _start_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _flow_input(name, flow_id, targets)
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


def test_flow_id_validation() -> None:
    """Test the accepted lowercase kebab-case logical IDs."""
    assert is_valid_flow_id("bedroom-night-cooling")
    assert is_valid_flow_id("flow-2")
    assert not is_valid_flow_id("Bedroom-Night")
    assert not is_valid_flow_id("bedroom_night")
    assert not is_valid_flow_id("bedroom--night")
    assert not is_valid_flow_id("-bedroom")
    assert not is_valid_flow_id("bedroom-")


def test_saved_flow_serializes_two_stages() -> None:
    """Test saved definitions use canonical temperatures and ordered stages."""
    flow = SavedFlow(
        flow_id="bedroom-night",
        targets=("climate.bedroom",),
        stages=(
            FlowStage(ClimateState(hvac_mode="cool", temperature_celsius=22.5), 1800),
            FlowStage(ClimateState(hvac_mode="off")),
        ),
    )

    data = flow.as_dict()

    assert data[CONF_FLOW_ID] == "bedroom-night"
    assert data[CONF_TARGETS] == ["climate.bedroom"]
    assert data[CONF_STAGES][0]["climate_state"][CONF_TEMPERATURE_CELSIUS] == 22.5
    assert data[CONF_STAGES][0][CONF_DURATION] == 1800
    assert CONF_DURATION not in data[CONF_STAGES][1]


def test_duration_requires_a_positive_value() -> None:
    """Test zero-duration data cannot reach saved flow storage."""
    assert _duration_seconds({"minutes": 1}) == 60

    try:
        _duration_seconds({"seconds": 0})
    except ValueError:
        pass
    else:
        msg = "Expected a zero duration to be rejected"
        raise AssertionError(msg)


async def test_shared_capabilities_intersect_selected_targets(
    hass: HomeAssistant,
) -> None:
    """Test selectors only use controls shared by every target."""
    _add_climate(hass, "climate.bedroom", hvac_modes=["off", "cool", "heat"])
    _add_climate(hass, "climate.office", hvac_modes=["off", "cool"])

    capabilities = shared_capabilities(hass, ["climate.bedroom", "climate.office"])

    assert capabilities.hvac_modes == ("cool", "off")
    assert capabilities.minimum_temperature == 16
    assert capabilities.maximum_temperature == 30


async def test_create_saved_two_stage_flow(hass: HomeAssistant) -> None:
    """Test the native subentry flow saves exactly two configured stages."""
    _add_climate(hass, "climate.bedroom")
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)

    result = await _start_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "details"

    with pytest.raises(InvalidData, match="duration"):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            _flow_input(
                "Bedroom Night Cooling",
                "bedroom-cooling",
                ["climate.bedroom"],
                stage_1_duration={},
            ),
        )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _flow_input("Bedroom Night Cooling", "bedroom-cooling", ["climate.bedroom"]),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Bedroom Night Cooling"
    assert subentry.unique_id == "bedroom-cooling"
    assert subentry.data[CONF_FLOW_ID] == "bedroom-cooling"
    assert len(subentry.data[CONF_STAGES]) == 2
    assert subentry.data[CONF_STAGES][0][CONF_DURATION] == 1800
    assert CONF_DURATION not in subentry.data[CONF_STAGES][1]


async def test_flow_uses_name_derived_id_when_it_is_not_edited(
    hass: HomeAssistant,
) -> None:
    """Test saving the generated logical ID without explicitly editing it."""
    _add_climate(hass, "climate.bedroom")
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)

    result = await _start_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _flow_input("Bedroom Night Cooling", "", ["climate.bedroom"]),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    subentry = next(iter(entry.subentries.values()))
    assert subentry.unique_id == "bedroom-night-cooling"


async def test_saved_flow_rejects_duplicate_id_and_empty_targets(
    hass: HomeAssistant,
) -> None:
    """Test flow identity and target validation before stage configuration."""
    _add_climate(hass, "climate.bedroom")
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    await _create_two_stage_flow(hass, entry)

    result = await _start_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _flow_input("Duplicate", "bedroom-night-cooling", ["climate.bedroom"]),
    )
    assert result["errors"][CONF_FLOW_ID] == "duplicate_flow_id"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _flow_input("Duplicate", "duplicate", []),
    )
    assert result["errors"][CONF_TARGETS] == "no_targets"


async def test_saved_flow_rejects_targets_without_a_shared_hvac_mode(
    hass: HomeAssistant,
) -> None:
    """Test incompatible target capabilities cannot reach a stage form."""
    _add_climate(hass, "climate.bedroom", hvac_modes=["cool"])
    _add_climate(hass, "climate.office", hvac_modes=["heat"])
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)

    result = await _start_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _flow_input(
            "Incompatible", "incompatible", ["climate.bedroom", "climate.office"]
        ),
    )

    assert result["step_id"] == "details"
    assert result["errors"]["base"] == "unsupported_targets"


async def test_saved_flows_are_independent_subentries_and_can_be_removed(
    hass: HomeAssistant,
) -> None:
    """Test native subentry removal affects only the selected saved flow."""
    _add_climate(hass, "climate.bedroom")
    _add_climate(hass, "climate.office")
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)

    await _create_two_stage_flow(
        hass,
        entry,
        name="Bedroom Night Cooling",
        flow_id="bedroom-night-cooling",
        targets=["climate.bedroom"],
    )
    await _create_two_stage_flow(
        hass,
        entry,
        name="Office Night Cooling",
        flow_id="office-night-cooling",
        targets=["climate.office"],
    )

    assert len(entry.subentries) == 2
    bedroom = next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.unique_id == "bedroom-night-cooling"
    )
    assert hass.config_entries.async_remove_subentry(entry, bedroom.subentry_id)
    assert len(entry.subentries) == 1
    assert next(iter(entry.subentries.values())).unique_id == "office-night-cooling"


async def test_reconfigure_name_preserves_subentry_identity_and_flow_id(
    hass: HomeAssistant,
) -> None:
    """Test renaming does not replace a subentry or regenerate its flow ID."""
    _add_climate(hass, "climate.bedroom")
    entry = MockConfigEntry(domain=DOMAIN, title="Climate Flow", data={})
    entry.add_to_hass(hass)
    await _create_two_stage_flow(hass, entry)
    subentry = next(iter(entry.subentries.values()))

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, FLOW_SUBENTRY_TYPE),
        context=SubentryFlowContext(
            source=SOURCE_RECONFIGURE, subentry_id=subentry.subentry_id
        ),
    )
    assert result["step_id"] == "details"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        _flow_input(
            "Bedroom Evening Cooling",
            "bedroom-night-cooling",
            ["climate.bedroom"],
            stage_1_duration={"minutes": 20},
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    updated = entry.subentries[subentry.subentry_id]
    assert updated.subentry_id == subentry.subentry_id
    assert updated.title == "Bedroom Evening Cooling"
    assert updated.unique_id == "bedroom-night-cooling"
