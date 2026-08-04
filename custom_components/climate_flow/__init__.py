"""The Climate Flow integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Climate Flow from a config entry."""
    _LOGGER.debug("Setting up Climate Flow config entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Climate Flow config entry."""
    _LOGGER.debug("Unloading Climate Flow config entry %s", entry.entry_id)
    return True
