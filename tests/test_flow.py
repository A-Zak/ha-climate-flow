"""Tests for saved Climate Flow definitions."""

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
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climate_flow.config_flow import _duration_seconds
from custom_components.climate_flow.const import (
    CONF_DURATION,
    CONF_FLOW_ID,
    CONF_HVAC_MODE,
    CONF_STAGES,
    CONF_TARGETS,
    CONF_TEMPERATURE,
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
        ATTR_HVAC_MODES: hvac_modes or ["off", "cool", "heat"],
        ATTR_FAN_MODES: fan_modes or ["auto", "high"],
        ATTR_SWING_MODES: swing_modes or ["off", "vertical"],
        ATTR_PRESET_MODES: preset_modes or ["none", "eco"],
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


async def _start_flow(
    hass: HomeAssistant, entry: MockConfigEntry
) -> dict[str, object]:
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
    flow_id: str = "bedroom_night_cooling",
    targets: list[str] | None = None,
) -> None:
    """Create a saved two-stage flow through its UI flow."""
    if targets is None:
        targets = ["climate.bedroom"]
    result = await _start_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": name}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": name, CONF_FLOW_ID: flow_id, CONF_TARGETS: targets},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _stage_input("cool", duration={"minutes": 30})
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _stage_input("off")
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


def test_flow_id_validation() -> None:
    """Test the accepted lowercase snake-case logical IDs."""
    assert is_valid_flow_id("bedroom_night_cooling")
    assert is_valid_flow_id("flow_2")
    assert not is_valid_flow_id("Bedroom_Night")
    assert not is_valid_flow_id("bedroom__night")
    assert not is_valid_flow_id("_bedroom")
    assert not is_valid_flow_id("bedroom_")


def test_saved_flow_serializes_two_stages() -> None:
    """Test saved definitions use canonical temperatures and ordered stages."""
    flow = SavedFlow(
        flow_id="bedroom_night",
        targets=("climate.bedroom",),
        stages=(
            FlowStage(
                ClimateState(hvac_mode="cool", temperature_celsius=22.5), 1800
            ),
            FlowStage(ClimateState(hvac_mode="off")),
        ),
    )

    data = flow.as_dict()

    assert data[CONF_FLOW_ID] == "bedroom_night"
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

    capabilities = shared_capabilities(
        hass, ["climate.bedroom", "climate.office"]
    )

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
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Bedroom Night Cooling"}
    )
    assert result["step_id"] == "details"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Bedroom Night Cooling",
            CONF_FLOW_ID: "bedroom_night_cooling",
            CONF_TARGETS: ["climate.bedroom"],
        },
    )
    assert result["step_id"] == "stage_1"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_HVAC_MODE: "cool",
            CONF_TEMPERATURE: 22,
            CONF_DURATION: {"minutes": 30},
        },
    )
    assert result["step_id"] == "stage_2"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _stage_input("off")
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Bedroom Night Cooling"
    assert subentry.unique_id == "bedroom_night_cooling"
    assert subentry.data[CONF_FLOW_ID] == "bedroom_night_cooling"
    assert len(subentry.data[CONF_STAGES]) == 2
    assert subentry.data[CONF_STAGES][0][CONF_DURATION] == 1800
    assert CONF_DURATION not in subentry.data[CONF_STAGES][1]


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
        result["flow_id"], {"name": "Duplicate"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Duplicate",
            CONF_FLOW_ID: "bedroom_night_cooling",
            CONF_TARGETS: ["climate.bedroom"],
        },
    )
    assert result["errors"][CONF_FLOW_ID] == "duplicate_flow_id"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Duplicate", CONF_FLOW_ID: "duplicate", CONF_TARGETS: []},
    )
    assert result["errors"][CONF_TARGETS] == "no_targets"


async def test_reconfigure_preserves_subentry_identity(hass: HomeAssistant) -> None:
    """Test logical ID changes do not replace the config subentry."""
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
        {
            "name": "Bedroom Evening Cooling",
            CONF_FLOW_ID: "bedroom_evening",
            CONF_TARGETS: ["climate.bedroom"],
        },
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _stage_input("cool", duration={"minutes": 20})
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _stage_input("off")
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    updated = entry.subentries[subentry.subentry_id]
    assert updated.subentry_id == subentry.subentry_id
    assert updated.title == "Bedroom Evening Cooling"
    assert updated.unique_id == "bedroom_evening"
