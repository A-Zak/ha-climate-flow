"""The Climate Flow integration."""

import logging
from collections import defaultdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .runtime import ClimateFlowRuntime, definitions_from_entry

type ClimateFlowConfigEntry = ConfigEntry[ClimateFlowRuntime]

PLATFORMS = (Platform.SWITCH,)
SERVICE_START = "start"
SERVICE_CANCEL = "cancel"
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register Climate Flow actions before any config entry is loaded."""
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
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ClimateFlowConfigEntry) -> bool:
    """Set up Climate Flow from a config entry."""
    _LOGGER.debug("Setting up Climate Flow config entry %s", entry.entry_id)
    runtime = ClimateFlowRuntime(hass, entry.entry_id)
    runtime.load_definitions(definitions_from_entry(entry))
    entry.runtime_data = runtime
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ClimateFlowConfigEntry
) -> bool:
    """Unload a Climate Flow config entry."""
    _LOGGER.debug("Unloading Climate Flow config entry %s", entry.entry_id)
    await entry.runtime_data.async_cancel_all()
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
