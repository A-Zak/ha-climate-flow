"""Switch entities for saved Climate Flow definitions."""

from datetime import datetime

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .runtime import ClimateFlowRuntime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[ClimateFlowRuntime],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one switch for every saved flow definition."""
    runtime = entry.runtime_data
    entities: dict[str, ClimateFlowSwitch] = {}

    async def async_add(flow_key: str) -> None:
        """Add a dynamically created saved-flow switch."""
        if flow_key in entities:
            return
        entity = ClimateFlowSwitch(runtime, flow_key)
        entities[flow_key] = entity
        async_add_entities([entity], config_subentry_id=flow_key)

    async def async_remove(flow_key: str) -> None:
        """Remove a deleted saved-flow switch."""
        if (entity := entities.pop(flow_key, None)) is not None:
            await entity.async_remove(force_remove=True)

    runtime.set_switch_platform_callbacks(async_add, async_remove)
    for flow_key in runtime.flow_keys():
        await async_add(flow_key)


class ClimateFlowSwitch(SwitchEntity):
    """Represent one saved flow's active execution state."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:hvac"
    _attr_should_poll = False
    _attr_force_update = True

    def __init__(self, runtime: ClimateFlowRuntime, flow_key: str) -> None:
        """Initialize a stable switch for one config subentry."""
        self._runtime = runtime
        self._flow_key = flow_key
        self._attr_unique_id = flow_key

    @property
    def name(self) -> str:
        """Return the saved flow's user-visible title."""
        return self._runtime.definition(self._flow_key).title

    @property
    def runtime(self) -> ClimateFlowRuntime:
        """Return the runtime manager owning this switch."""
        return self._runtime

    @property
    def flow_key(self) -> str:
        """Return the stable config-subentry identity for this flow."""
        return self._flow_key

    @property
    def is_on(self) -> bool:
        """Return whether this saved flow is executing."""
        return self._runtime.is_active(self._flow_key)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return current execution details."""
        return self._runtime.switch_attributes(self._flow_key)

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime state changes."""
        self.async_on_remove(
            self._runtime.subscribe(self._flow_key, self._async_runtime_updated)
        )

    def _async_runtime_updated(self, _: str) -> None:
        """Publish a runtime-driven state update."""
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: object) -> None:
        """Start this saved flow."""
        try:
            await self._runtime.async_start_many((self._flow_key,), self._context)
        except HomeAssistantError:

            @callback
            def publish_idle_state(_: datetime) -> None:
                """Publish the rejected toggle after its service response."""
                self.async_write_ha_state()

            async_call_later(self.hass, 0.1, publish_idle_state)
            raise

    async def async_turn_off(self, **kwargs: object) -> None:
        """Cancel this saved flow."""
        await self._runtime.async_cancel(self._flow_key)
