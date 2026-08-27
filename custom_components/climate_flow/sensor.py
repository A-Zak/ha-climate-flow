"""A single diagnostic sensor exposing every pending ephemeral transition."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .runtime import ClimateFlowRuntime
from .transition_runtime import TransitionRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[ClimateFlowRuntime],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the one pending-transitions sensor for this config entry."""
    async_add_entities(
        [ClimateFlowTransitionsSensor(entry.runtime_data.transitions, entry.entry_id)]
    )


class ClimateFlowTransitionsSensor(SensorEntity):
    """Report every currently pending one-shot climate transition."""

    _attr_has_entity_name = True
    _attr_name = "Pending transitions"
    _attr_icon = "mdi:timer-outline"
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, transitions: TransitionRuntime, entry_id: str) -> None:
        """Initialize the sensor for one config entry's transition runtime."""
        self._transitions = transitions
        self._attr_unique_id = f"{entry_id}_pending_transitions"

    @property
    def native_value(self) -> int:
        """Return how many transitions are currently pending."""
        return len(self._transitions.pending_summary())

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return every pending transition, keyed by climate target."""
        return self._transitions.pending_summary()

    async def async_added_to_hass(self) -> None:
        """Subscribe to pending-transition changes."""
        self.async_on_remove(self._transitions.subscribe(self._async_updated))

    @callback
    def _async_updated(self) -> None:
        """Publish a runtime-driven state update."""
        self.async_write_ha_state()
