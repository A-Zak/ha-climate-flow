"""Home Assistant runtime adapter for executing saved Climate Flow definitions."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import DOMAIN, FLOW_SUBENTRY_TYPE
from .execution_engine import ActiveFlowRun, FlowConflictError, FlowExecutionEngine
from .flow import ClimateState, SavedFlow
from .flow_capabilities import temperature_from_celsius
from .transition_runtime import TransitionRuntime

_LOGGER = logging.getLogger(__name__)

SwitchUpdateCallback = Callable[[str], None]
SwitchAddCallback = Callable[[str], Awaitable[None]]
SwitchRemoveCallback = Callable[[str], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class FlowDefinition:
    """A saved flow paired with its stable config-subentry identity."""

    subentry_id: str
    title: str
    flow: SavedFlow


class ClimateFlowRuntime:
    """Manage active flow executions for one Climate Flow config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize an empty runtime manager."""
        self.hass = hass
        self.entry_id = entry_id
        self.engine = FlowExecutionEngine()
        self.transitions = TransitionRuntime(hass)
        self._definitions: dict[str, FlowDefinition] = {}
        self._timer_unsubs: dict[str, Callable[[], None]] = {}
        self._target_unsubs: dict[str, Callable[[], None]] = {}
        self._stage_tasks: dict[str, asyncio.Task[None]] = {}
        self._switch_callbacks: dict[str, set[SwitchUpdateCallback]] = {}
        self._switch_add: SwitchAddCallback | None = None
        self._switch_remove: SwitchRemoveCallback | None = None

    def load_definitions(self, definitions: Iterable[FlowDefinition]) -> None:
        """Load definitions during initial config-entry setup."""
        self._definitions = {
            definition.subentry_id: definition for definition in definitions
        }

    def definition(self, flow_key: str) -> FlowDefinition:
        """Return a saved flow definition."""
        return self._definitions[flow_key]

    def flow_keys(self) -> tuple[str, ...]:
        """Return saved flow keys in stable creation order."""
        return tuple(self._definitions)

    def is_active(self, flow_key: str) -> bool:
        """Return whether the saved flow is running."""
        return self.engine.is_active(flow_key)

    def subscribe(
        self, flow_key: str, listener: SwitchUpdateCallback
    ) -> Callable[[], None]:
        """Subscribe a switch entity to runtime changes for one flow."""
        callbacks = self._switch_callbacks.setdefault(flow_key, set())
        callbacks.add(listener)

        @callback
        def unsubscribe() -> None:
            callbacks.discard(listener)

        return unsubscribe

    def set_switch_platform_callbacks(
        self, add: SwitchAddCallback, remove: SwitchRemoveCallback
    ) -> None:
        """Register dynamic switch lifecycle callbacks from the switch platform."""
        self._switch_add = add
        self._switch_remove = remove

    def switch_attributes(self, flow_key: str) -> dict[str, Any]:
        """Return current runtime attributes for a flow switch."""
        definition = self.definition(flow_key)
        attributes: dict[str, Any] = {"flow_id": definition.flow.flow_id}
        if not self.engine.is_active(flow_key):
            return attributes
        run = self.engine.active_run(flow_key)
        attributes.update(
            {
                "current_stage": run.current_stage + 1,
                "total_stages": len(run.flow.stages),
                "active_targets": list(run.targets),
                "run_started_at": run.started_at.isoformat(),
                "stage_started_at": run.stage_started_at.isoformat(),
            }
        )
        if run.current_stage == 0:
            attributes["deadline"] = (
                run.stage_started_at
                + timedelta(seconds=run.flow.stages[0].duration_seconds or 0)
            ).isoformat()
        return attributes

    async def async_start_many(
        self, flow_keys: Iterable[str], context: Context | None = None
    ) -> None:
        """Atomically reserve and begin one or more saved flows."""
        keys = tuple(dict.fromkeys(flow_keys))
        if not keys:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_flow_targets"
            )
        try:
            flows = {flow_key: self.definition(flow_key).flow for flow_key in keys}
        except KeyError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unknown_flow"
            ) from err
        try:
            started = self.engine.start_many(flows, dt_util.utcnow())
        except FlowConflictError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="target_owned",
                translation_placeholders={"target": str(err)},
            ) from err
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_flow"
            ) from err
        for run in started:
            self._notify(run.flow_key)
            self._target_unsubs[run.flow_key] = async_track_state_change_event(
                self.hass, run.targets, self._async_target_state_changed
            )
        await asyncio.gather(
            *(self._async_apply_stage_one(run, context) for run in started)
        )
        if any(not self.engine.is_active(run.flow_key) for run in started):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="all_targets_failed"
            )

    async def async_cancel(self, flow_key: str) -> None:
        """Cancel one flow if it is active."""
        if not self.engine.is_active(flow_key):
            return
        run = self.engine.active_run(flow_key)
        if self.engine.cancel(flow_key, run.token):
            self._cleanup_run(flow_key)
            self._notify(flow_key)

    async def async_cancel_all(self) -> None:
        """Cancel every active flow during unload."""
        for flow_key in tuple(self._definitions):
            await self.async_cancel(flow_key)

    async def async_sync_definitions(
        self, definitions: Iterable[FlowDefinition]
    ) -> None:
        """Synchronize definitions after config-subentry changes."""
        updated = {definition.subentry_id: definition for definition in definitions}
        removed = set(self._definitions) - set(updated)
        added = set(updated) - set(self._definitions)
        for flow_key in removed:
            await self.async_cancel(flow_key)
            if self._switch_remove is not None:
                await self._switch_remove(flow_key)
        self._definitions = updated
        for flow_key in set(updated) & set(self._switch_callbacks):
            self._notify(flow_key)
        if self._switch_add is not None:
            for flow_key in added:
                await self._switch_add(flow_key)

    async def _async_apply_stage_one(
        self, run: ActiveFlowRun, context: Context | None
    ) -> None:
        """Apply Stage 1 and schedule its completion when targets remain."""
        await self._async_apply_stage(run, 0, context)
        if not self._is_current(run):
            return

        @callback
        def stage_one_complete(_: datetime) -> None:
            """Advance the flow from Home Assistant's event loop."""
            self._schedule_stage_two(run, context)

        self._timer_unsubs[run.flow_key] = async_call_later(
            self.hass,
            run.flow.stages[0].duration_seconds or 0,
            stage_one_complete,
        )
        self._notify(run.flow_key)

    @callback
    def _schedule_stage_two(self, run: ActiveFlowRun, context: Context | None) -> None:
        """Schedule the asynchronous Stage 2 callback."""
        self._timer_unsubs.pop(run.flow_key, None)
        self._stage_tasks[run.flow_key] = self.hass.async_create_task(
            self._async_advance_to_stage_two(run, context),
            f"Climate Flow Stage 2 {run.flow_key}",
        )

    async def _async_advance_to_stage_two(
        self, run: ActiveFlowRun, context: Context | None
    ) -> None:
        """Advance a current Stage 1 run, apply Stage 2, and complete it."""
        advanced = self.engine.advance(run.flow_key, run.token, dt_util.utcnow())
        if advanced is None:
            return
        self._notify(advanced.flow_key)
        await self._async_apply_stage(advanced, 1, context)
        if self._is_current(advanced) and self.engine.complete(
            advanced.flow_key, advanced.token
        ):
            self._cleanup_run(advanced.flow_key)
            self._notify(advanced.flow_key)

    async def _async_apply_stage(
        self, run: ActiveFlowRun, stage_index: int, context: Context | None
    ) -> None:
        """Apply a stage independently to every remaining target."""
        state = run.flow.stages[stage_index].climate_state
        await asyncio.gather(
            *(
                self._async_apply_target(run, target, state, context)
                for target in run.targets
            )
        )

    async def _async_apply_target(
        self,
        run: ActiveFlowRun,
        target: str,
        state: ClimateState,
        context: Context | None,
    ) -> None:
        """Validate and apply one state, dropping the target on any failure."""
        try:
            self._validate_target_state(target, state)
            for service, data in self._service_calls(target, state):
                if not self._is_current(run):
                    return
                await self.hass.services.async_call(
                    "climate", service, data, blocking=True, context=context
                )
        except (HomeAssistantError, ValueError, TypeError) as err:
            _LOGGER.warning("Dropping Climate Flow target %s: %s", target, err)
            await self._async_drop_target(run, target)

    def _validate_target_state(self, target: str, state: ClimateState) -> None:
        """Validate one target's live capabilities before sending services."""
        target_state = self.hass.states.get(target)
        if (
            target_state is None
            or target_state.domain != "climate"
            or target_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            raise ValueError("Target is unavailable")
        attributes = target_state.attributes
        hvac_modes = attributes.get(ATTR_HVAC_MODES)
        if not isinstance(hvac_modes, list) or state.hvac_mode not in hvac_modes:
            raise ValueError("Unsupported HVAC mode")
        self._validate_optional_mode(attributes, ATTR_FAN_MODES, state.fan_mode)
        self._validate_optional_mode(attributes, ATTR_SWING_MODES, state.swing_mode)
        self._validate_optional_mode(attributes, ATTR_PRESET_MODES, state.preset_mode)
        if state.temperature_celsius is not None:
            minimum = attributes.get(ATTR_MIN_TEMP)
            maximum = attributes.get(ATTR_MAX_TEMP)
            temperature = temperature_from_celsius(self.hass, state.temperature_celsius)
            if (
                not isinstance(minimum, int | float)
                or not isinstance(maximum, int | float)
                or not minimum <= temperature <= maximum
            ):
                raise ValueError("Unsupported temperature")

    @staticmethod
    def _validate_optional_mode(
        attributes: dict[str, Any], attribute: str, value: str | None
    ) -> None:
        """Validate an optional state value against a target capability list."""
        if value is None:
            return
        values = attributes.get(attribute)
        if not isinstance(values, list) or value not in values:
            raise ValueError(f"Unsupported {attribute}")

    def _service_calls(
        self, target: str, state: ClimateState
    ) -> tuple[tuple[str, dict[str, Any]], ...]:
        """Return ordered Home Assistant climate service calls for one state."""
        calls: list[tuple[str, dict[str, Any]]] = [
            (
                SERVICE_SET_HVAC_MODE,
                {ATTR_ENTITY_ID: target, ATTR_HVAC_MODE: state.hvac_mode},
            )
        ]
        if state.temperature_celsius is not None:
            calls.append(
                (
                    SERVICE_SET_TEMPERATURE,
                    {
                        ATTR_ENTITY_ID: target,
                        ATTR_TEMPERATURE: temperature_from_celsius(
                            self.hass, state.temperature_celsius
                        ),
                    },
                )
            )
        for service, attribute, value in (
            (SERVICE_SET_PRESET_MODE, ATTR_PRESET_MODE, state.preset_mode),
            (SERVICE_SET_SWING_MODE, ATTR_SWING_MODE, state.swing_mode),
            (SERVICE_SET_FAN_MODE, ATTR_FAN_MODE, state.fan_mode),
        ):
            if value is not None:
                calls.append((service, {ATTR_ENTITY_ID: target, attribute: value}))
        return tuple(calls)

    @callback
    def _async_target_state_changed(self, event: Event) -> None:
        """Drop targets which become unavailable during a flow."""
        new_state = event.data.get("new_state")
        target = event.data["entity_id"]
        if new_state is not None and new_state.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            return
        flow_key = self.engine.owner_of(target)
        if flow_key is None:
            return
        run = self.engine.active_run(flow_key)
        self.hass.async_create_task(
            self._async_drop_target(run, target), f"Drop Climate Flow target {target}"
        )

    async def _async_drop_target(self, run: ActiveFlowRun, target: str) -> None:
        """Drop a target and clean up if it was the final one."""
        if self.engine.drop_target(run.flow_key, run.token, target):
            _LOGGER.warning(
                "Climate Flow %s failed because no targets remain", run.flow_key
            )
            self._cleanup_run(run.flow_key)
        self._notify(run.flow_key)

    def _is_current(self, run: ActiveFlowRun) -> bool:
        """Return whether a run token remains current after awaited work."""
        return self.engine.is_active(run.flow_key) and (
            self.engine.active_run(run.flow_key).token == run.token
        )

    def _cleanup_run(self, flow_key: str) -> None:
        """Cancel runtime resources tied to a terminal run."""
        if (unsubscribe := self._timer_unsubs.pop(flow_key, None)) is not None:
            unsubscribe()
        if (unsubscribe := self._target_unsubs.pop(flow_key, None)) is not None:
            unsubscribe()
        task = self._stage_tasks.pop(flow_key, None)
        current_task = asyncio.current_task()
        if task is not None and task is not current_task:
            task.cancel()

    def _notify(self, flow_key: str) -> None:
        """Notify switch entities of an execution or definition update."""
        for callback_ in tuple(self._switch_callbacks.get(flow_key, ())):
            callback_(flow_key)


def definitions_from_entry(entry: Any) -> tuple[FlowDefinition, ...]:
    """Load executable flow definitions from a config entry's subentries."""
    definitions: list[FlowDefinition] = []
    for subentry in entry.get_subentries_of_type(FLOW_SUBENTRY_TYPE):
        try:
            flow = SavedFlow.from_dict(subentry.data)
        except ValueError:
            _LOGGER.error(
                "Ignoring invalid saved Climate Flow %s", subentry.subentry_id
            )
            continue
        definitions.append(FlowDefinition(subentry.subentry_id, subentry.title, flow))
    return tuple(definitions)
