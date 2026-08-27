"""The Climate Flow integration."""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.typing import ConfigType

from .const import CARD_URL, DOMAIN
from .runtime import ClimateFlowRuntime, definitions_from_entry

type ClimateFlowConfigEntry = ConfigEntry[ClimateFlowRuntime]

PLATFORMS = (Platform.SWITCH, Platform.SENSOR)
SERVICE_START = "start"
SERVICE_CANCEL = "cancel"
SERVICE_SCHEDULE_TRANSITION = "schedule_transition"
SERVICE_CANCEL_TRANSITION = "cancel_transition"
ATTR_DELAY_SECONDS = "delay_seconds"
ATTR_TURN_OFF = "turn_off"
ATTR_TURN_ON = "turn_on"
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _require_a_valid_target_state(value: dict[str, Any]) -> dict[str, Any]:
    """Reject a schedule_transition call with an invalid target state.

    turn_off is exclusive. Otherwise, turn_on and temperature may combine
    ("turn on to this temperature"), but at least one of them is required.
    """
    turn_off = value[ATTR_TURN_OFF]
    turn_on = value[ATTR_TURN_ON]
    has_temperature = value.get(ATTR_TEMPERATURE) is not None
    if turn_off and (turn_on or has_temperature):
        raise vol.Invalid("turn_off cannot be combined with turn_on or temperature")
    if not turn_off and not turn_on and not has_temperature:
        raise vol.Invalid("Specify turn_off, or turn_on and/or temperature")
    return value


SCHEDULE_TRANSITION_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_ENTITY_ID): cv.entity_domain("climate"),
            vol.Required(ATTR_DELAY_SECONDS): vol.All(
                vol.Coerce(float), vol.Range(min=1)
            ),
            vol.Optional(ATTR_TURN_OFF, default=False): cv.boolean,
            vol.Optional(ATTR_TURN_ON, default=False): cv.boolean,
            vol.Optional(ATTR_TEMPERATURE): vol.Coerce(float),
        }
    ),
    _require_a_valid_target_state,
)

CANCEL_TRANSITION_SCHEMA = vol.Schema(
    {vol.Required(ATTR_ENTITY_ID): cv.entity_domain("climate")}
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register Climate Flow actions before any config entry is loaded."""
    if hass.http is not None:
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    CARD_URL,
                    str(Path(__file__).parent / "www"),
                    cache_headers=False,
                )
            ]
        )
    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START,
        entity_domain=Platform.SWITCH,
        schema=None,
        func=_async_start_switches,
    )
    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CANCEL,
        entity_domain=Platform.SWITCH,
        schema=None,
        func=_async_cancel_switches,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SCHEDULE_TRANSITION,
        _async_schedule_transition,
        schema=SCHEDULE_TRANSITION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_TRANSITION,
        _async_cancel_transition,
        schema=CANCEL_TRANSITION_SCHEMA,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ClimateFlowConfigEntry) -> bool:
    """Set up Climate Flow from a config entry."""
    _LOGGER.debug("Setting up Climate Flow config entry %s", entry.entry_id)
    runtime = ClimateFlowRuntime(hass, entry.entry_id)
    runtime.load_definitions(definitions_from_entry(entry))
    entry.runtime_data = runtime
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await runtime.transitions.async_load_and_recover()
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ClimateFlowConfigEntry
) -> bool:
    """Unload a Climate Flow config entry."""
    _LOGGER.debug("Unloading Climate Flow config entry %s", entry.entry_id)
    await entry.runtime_data.async_cancel_all()
    await entry.runtime_data.transitions.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_entry_updated(
    hass: HomeAssistant, entry: ClimateFlowConfigEntry
) -> None:
    """Synchronize switch entities when a saved-flow subentry changes."""
    await entry.runtime_data.async_sync_definitions(definitions_from_entry(entry))


async def _async_start_switches(entities: list[Any], call: ServiceCall) -> None:
    """Start selected flow switches as atomic batches per config entry."""
    grouped: dict[ClimateFlowRuntime, list[str]] = defaultdict(list)
    for entity in entities:
        grouped[entity.runtime].append(entity.flow_key)
    for runtime, flow_keys in grouped.items():
        await runtime.async_start_many(flow_keys, call.context)


async def _async_cancel_switches(entities: list[Any], call: ServiceCall) -> None:
    """Cancel each selected flow switch."""
    for entity in entities:
        await entity.runtime.async_cancel(entity.flow_key)


async def _async_schedule_transition(call: ServiceCall) -> None:
    """Schedule a pending transition on the loaded entry's runtime."""
    runtime = _loaded_runtime(call.hass)
    await runtime.transitions.async_schedule(
        call.data[ATTR_ENTITY_ID],
        delay_seconds=call.data[ATTR_DELAY_SECONDS],
        turn_off=call.data[ATTR_TURN_OFF],
        turn_on=call.data[ATTR_TURN_ON],
        temperature_celsius=call.data.get(ATTR_TEMPERATURE),
    )


async def _async_cancel_transition(call: ServiceCall) -> None:
    """Cancel a pending transition on the loaded entry's runtime."""
    runtime = _loaded_runtime(call.hass)
    await runtime.transitions.async_cancel(call.data[ATTR_ENTITY_ID])


def _loaded_runtime(hass: HomeAssistant) -> ClimateFlowRuntime:
    """Return the single loaded Climate Flow entry's runtime."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="no_config_entry"
    )
