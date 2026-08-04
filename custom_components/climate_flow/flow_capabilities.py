"""Home Assistant adapters for validating saved flow climate targets."""

from collections.abc import Iterable
from dataclasses import dataclass

from homeassistant.components.climate.const import (
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODES,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, State
from homeassistant.util.unit_conversion import TemperatureConverter


@dataclass(frozen=True, slots=True)
class SharedClimateCapabilities:
    """The climate controls shared by all selected target entities."""

    hvac_modes: tuple[str, ...]
    fan_modes: tuple[str, ...]
    swing_modes: tuple[str, ...]
    preset_modes: tuple[str, ...]
    minimum_temperature: float
    maximum_temperature: float


class InvalidClimateTargetsError(ValueError):
    """Raised when selected targets cannot support a saved flow."""


def _common_values(states: Iterable[State], attribute: str) -> tuple[str, ...]:
    """Return values supported by every selected climate target."""
    values: set[str] | None = None
    for state in states:
        supported = state.attributes.get(attribute)
        if not isinstance(supported, list) or not all(
            isinstance(value, str) for value in supported
        ):
            return ()
        supported_set = set(supported)
        values = supported_set if values is None else values & supported_set
    return tuple(sorted(values or ()))


def _number_attribute(state: State, attribute: str) -> float:
    """Return a numeric climate capability attribute."""
    value = state.attributes.get(attribute)
    if not isinstance(value, int | float):
        raise InvalidClimateTargetsError
    return float(value)


def shared_capabilities(
    hass: HomeAssistant, targets: Iterable[str]
) -> SharedClimateCapabilities:
    """Return the common controls for the selected climate target entities."""
    states: list[State] = []
    for target in targets:
        state = hass.states.get(target)
        if state is None or state.domain != "climate":
            raise InvalidClimateTargetsError
        states.append(state)

    if not states:
        raise InvalidClimateTargetsError

    minimum_temperature = max(
        _number_attribute(state, ATTR_MIN_TEMP) for state in states
    )
    maximum_temperature = min(
        _number_attribute(state, ATTR_MAX_TEMP) for state in states
    )

    if minimum_temperature > maximum_temperature:
        raise InvalidClimateTargetsError

    return SharedClimateCapabilities(
        hvac_modes=_common_values(states, ATTR_HVAC_MODES),
        fan_modes=_common_values(states, ATTR_FAN_MODES),
        swing_modes=_common_values(states, ATTR_SWING_MODES),
        preset_modes=_common_values(states, ATTR_PRESET_MODES),
        minimum_temperature=minimum_temperature,
        maximum_temperature=maximum_temperature,
    )


def temperature_to_celsius(hass: HomeAssistant, temperature: float) -> float:
    """Convert a Home Assistant UI temperature to canonical Celsius."""
    return TemperatureConverter.convert(
        temperature,
        hass.config.units.temperature_unit,
        UnitOfTemperature.CELSIUS,
    )


def temperature_from_celsius(hass: HomeAssistant, temperature: float) -> float:
    """Convert canonical Celsius for the Home Assistant UI."""
    return TemperatureConverter.convert(
        temperature,
        UnitOfTemperature.CELSIUS,
        hass.config.units.temperature_unit,
    )


def selector_options(values: Iterable[str]) -> list[dict[str, str]]:
    """Return readable select-selector options for climate mode strings."""
    return [
        {"value": value, "label": value.replace("_", " ").title()} for value in values
    ]
