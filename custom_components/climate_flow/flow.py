"""Domain models for saved Climate Flow definitions."""

from dataclasses import dataclass
import re

from .const import (
    CONF_DURATION,
    CONF_FAN_MODE,
    CONF_FLOW_ID,
    CONF_HVAC_MODE,
    CONF_PRESET_MODE,
    CONF_SCHEMA_VERSION,
    CONF_STAGES,
    CONF_SWING_MODE,
    CONF_TARGETS,
    CONF_TEMPERATURE_CELSIUS,
    FLOW_SCHEMA_VERSION,
)

FLOW_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def is_valid_flow_id(flow_id: str) -> bool:
    """Return whether a logical flow ID is lower snake case."""
    return bool(FLOW_ID_PATTERN.fullmatch(flow_id))


@dataclass(frozen=True, slots=True)
class ClimateState:
    """The climate state to apply during a future flow stage."""

    hvac_mode: str
    temperature_celsius: float | None = None
    fan_mode: str | None = None
    swing_mode: str | None = None
    preset_mode: str | None = None

    def as_dict(self) -> dict[str, float | str]:
        """Return a JSON-serializable climate state."""
        data: dict[str, float | str] = {CONF_HVAC_MODE: self.hvac_mode}
        if self.temperature_celsius is not None:
            data[CONF_TEMPERATURE_CELSIUS] = self.temperature_celsius
        if self.fan_mode is not None:
            data[CONF_FAN_MODE] = self.fan_mode
        if self.swing_mode is not None:
            data[CONF_SWING_MODE] = self.swing_mode
        if self.preset_mode is not None:
            data[CONF_PRESET_MODE] = self.preset_mode
        return data


@dataclass(frozen=True, slots=True)
class FlowStage:
    """One ordered stage in a saved flow."""

    climate_state: ClimateState
    duration_seconds: float | None = None

    def as_dict(self) -> dict[str, dict[str, float | str] | float]:
        """Return a JSON-serializable stage."""
        data: dict[str, dict[str, float | str] | float] = {
            "climate_state": self.climate_state.as_dict()
        }
        if self.duration_seconds is not None:
            data[CONF_DURATION] = self.duration_seconds
        return data


@dataclass(frozen=True, slots=True)
class SavedFlow:
    """A Milestone 2 saved two-stage flow definition."""

    flow_id: str
    targets: tuple[str, ...]
    stages: tuple[FlowStage, FlowStage]

    def as_dict(self) -> dict[str, int | list[dict[str, object]] | list[str] | str]:
        """Return a JSON-serializable saved flow definition."""
        return {
            CONF_SCHEMA_VERSION: FLOW_SCHEMA_VERSION,
            CONF_FLOW_ID: self.flow_id,
            CONF_TARGETS: list(self.targets),
            CONF_STAGES: [stage.as_dict() for stage in self.stages],
        }
