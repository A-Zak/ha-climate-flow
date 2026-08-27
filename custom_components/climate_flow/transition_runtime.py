"""Home Assistant runtime adapter for ephemeral pending climate transitions.

Unlike a saved flow, a pending transition is not a config subentry and has no
switch entity: it is a single future state change for an arbitrary climate
target, persisted only so it survives a Home Assistant restart.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .transition import PendingTransition
from .transition_engine import TransitionEngine

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.pending_transitions"

PendingChangedCallback = Callable[[], None]


class TransitionRuntime:
    """Schedule, persist, and fire one-shot climate transitions."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a runtime with no pending transitions loaded yet."""
        self.hass = hass
        self.engine = TransitionEngine()
        self._store: Store[dict[str, dict[str, object]]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY
        )
        self._timer_unsubs: dict[str, Callable[[], None]] = {}
        self._tokens: dict[str, int] = {}
        self._listeners: set[PendingChangedCallback] = set()

    def pending(self, target: str) -> PendingTransition | None:
        """Return the pending transition for a target, if any."""
        return self.engine.pending(target)

    def pending_summary(self) -> dict[str, dict[str, object]]:
        """Return every pending transition as sensor-ready attribute data."""
        return {
            target: transition.as_dict()
            for target, transition in self._all_pending().items()
        }

    def subscribe(self, listener: PendingChangedCallback) -> Callable[[], None]:
        """Subscribe to pending-transition changes."""
        self._listeners.add(listener)

        @callback
        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    async def async_schedule(
        self,
        target: str,
        *,
        delay_seconds: float,
        turn_off: bool = False,
        turn_on: bool = False,
        temperature_celsius: float | None = None,
    ) -> None:
        """Schedule a transition, replacing any existing one for this target."""
        fires_at = dt_util.utcnow() + timedelta(seconds=delay_seconds)
        transition = PendingTransition(
            target=target,
            fires_at=fires_at,
            turn_off=turn_off,
            turn_on=turn_on,
            temperature_celsius=temperature_celsius,
        )
        await self._async_arm(transition, delay_seconds)

    async def async_cancel(self, target: str) -> None:
        """Cancel a target's pending transition, if any."""
        entry_token = self._token_for(target)
        if entry_token is None or not self.engine.cancel(target, entry_token):
            return
        self._cancel_timer(target)
        self._tokens.pop(target, None)
        await self._async_persist()
        self._notify()

    async def async_stop(self) -> None:
        """Cancel in-memory timers without discarding persisted transitions.

        Used on config-entry unload and reload, so a pending transition
        resumes on the next load exactly as it would after a Home Assistant
        restart, rather than being lost.
        """
        for target in tuple(self._timer_unsubs):
            self._cancel_timer(target)
        self._tokens.clear()

    async def async_load_and_recover(self) -> None:
        """Load persisted transitions and resume or fire each one."""
        data = await self._store.async_load() or {}
        due: list[PendingTransition] = []
        for target, raw in data.items():
            transition = self._parse(target, raw)
            if transition is None:
                continue
            remaining = (transition.fires_at - dt_util.utcnow()).total_seconds()
            if remaining <= 0:
                due.append(transition)
            else:
                await self._async_arm(transition, remaining, persist=False)
        for transition in due:
            await self._async_apply(transition)
        await self._async_persist()

    def _all_pending(self) -> dict[str, PendingTransition]:
        """Return every currently pending transition by target."""
        return {
            target: pending
            for target in self._timer_unsubs
            if (pending := self.engine.pending(target)) is not None
        }

    def _token_for(self, target: str) -> int | None:
        """Return the current token for a target, if one is pending."""
        return self._tokens.get(target)

    async def _async_arm(
        self,
        transition: PendingTransition,
        delay_seconds: float,
        *,
        persist: bool = True,
    ) -> None:
        """Store a transition, (re)start its timer, and notify listeners."""
        self._cancel_timer(transition.target)
        token = self.engine.schedule(transition)
        self._tokens[transition.target] = token

        @callback
        def fire(_: datetime) -> None:
            self.hass.async_create_task(
                self._async_fire(transition.target, token),
                f"Climate Flow transition {transition.target}",
            )

        self._timer_unsubs[transition.target] = async_call_later(
            self.hass, max(delay_seconds, 0), fire
        )
        if persist:
            await self._async_persist()
        self._notify()

    async def _async_fire(self, target: str, token: int) -> None:
        """Apply a transition once its timer elapses."""
        transition = self.engine.fire(target, token)
        if transition is None:
            return
        self._timer_unsubs.pop(target, None)
        self._tokens.pop(target, None)
        await self._async_apply(transition)
        await self._async_persist()
        self._notify()

    async def _async_apply(self, transition: PendingTransition) -> None:
        """Call the Home Assistant climate service(s) for a due transition.

        turn_on and a temperature may both be set ("turn on to this
        temperature", for a target that is currently off), in which case
        both services are called in order.
        """
        try:
            if transition.turn_off:
                await self.hass.services.async_call(
                    "climate",
                    SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: transition.target},
                    blocking=True,
                )
                return
            if transition.turn_on:
                await self.hass.services.async_call(
                    "climate",
                    SERVICE_TURN_ON,
                    {ATTR_ENTITY_ID: transition.target},
                    blocking=True,
                )
            if transition.temperature_celsius is not None:
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        ATTR_ENTITY_ID: transition.target,
                        ATTR_TEMPERATURE: transition.temperature_celsius,
                    },
                    blocking=True,
                )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Climate Flow transition for %s failed: %s", transition.target, err
            )

    def _cancel_timer(self, target: str) -> None:
        """Stop a target's scheduled timer, if any."""
        if (unsubscribe := self._timer_unsubs.pop(target, None)) is not None:
            unsubscribe()

    async def _async_persist(self) -> None:
        """Write every currently pending transition to storage."""
        await self._store.async_save(
            {
                target: transition.as_dict()
                for target, transition in self._all_pending().items()
            }
        )

    @staticmethod
    def _parse(target: str, raw: object) -> PendingTransition | None:
        """Parse one persisted record, discarding it if it is invalid."""
        if not isinstance(raw, dict):
            return None
        fires_at_raw = raw.get("fires_at")
        if not isinstance(fires_at_raw, str):
            return None
        fires_at = dt_util.parse_datetime(fires_at_raw)
        if fires_at is None:
            return None
        try:
            return PendingTransition(
                target=target,
                fires_at=fires_at,
                turn_off=bool(raw.get("turn_off", False)),
                turn_on=bool(raw.get("turn_on", False)),
                temperature_celsius=raw.get("temperature_celsius"),
            )
        except ValueError, TypeError:
            _LOGGER.warning("Discarding invalid persisted transition for %s", target)
            return None

    def _notify(self) -> None:
        """Notify subscribers that pending transitions changed."""
        for listener in tuple(self._listeners):
            listener()
