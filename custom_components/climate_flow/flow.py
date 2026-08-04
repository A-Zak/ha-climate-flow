"""Domain models for saved Climate Flow definitions."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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

FLOW_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LEGACY_FLOW_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def is_valid_flow_id(flow_id: str) -> bool:
    """Return whether a logical flow ID is lower kebab case."""
    return bool(FLOW_ID_PATTERN.fullmatch(flow_id))


def is_legacy_flow_id(flow_id: str) -> bool:
    """Return whether a pre-kebab-case flow ID uses the legacy format."""
    return bool(LEGACY_FLOW_ID_PATTERN.fullmatch(flow_id))


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

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SavedFlow:
        """Load a validated saved two-stage flow from config-subentry data."""
        flow_id = data.get(CONF_FLOW_ID)
        targets = data.get(CONF_TARGETS)
        stages = data.get(CONF_STAGES)
        if (
            not isinstance(flow_id, str)
            or not isinstance(targets, list)
            or not all(isinstance(target, str) for target in targets)
            or not isinstance(stages, list)
            or len(stages) != 2
        ):
            raise ValueError("Invalid saved flow")
        parsed_stages: list[FlowStage] = []
        for raw_stage in stages:
            if not isinstance(raw_stage, Mapping):
                raise ValueError("Invalid saved flow stage")
            raw_state = raw_stage.get("climate_state")
            if not isinstance(raw_state, Mapping):
                raise ValueError("Invalid saved climate state")
            hvac_mode = raw_state.get(CONF_HVAC_MODE)
            if not isinstance(hvac_mode, str):
                raise ValueError("Invalid HVAC mode")
            temperature = raw_state.get(CONF_TEMPERATURE_CELSIUS)
            duration = raw_stage.get(CONF_DURATION)
            optional_modes = (
                raw_state.get(CONF_FAN_MODE),
                raw_state.get(CONF_SWING_MODE),
                raw_state.get(CONF_PRESET_MODE),
            )
            if (
                (temperature is not None and not isinstance(temperature, int | float))
                or (duration is not None and not isinstance(duration, int | float))
                or not all(
                    mode is None or isinstance(mode, str) for mode in optional_modes
                )
            ):
                raise ValueError("Invalid saved climate state")
            parsed_stages.append(
                FlowStage(
                    climate_state=ClimateState(
                        hvac_mode=hvac_mode,
                        temperature_celsius=(
                            float(temperature) if temperature is not None else None
                        ),
                        fan_mode=optional_modes[0],
                        swing_mode=optional_modes[1],
                        preset_mode=optional_modes[2],
                    ),
                    duration_seconds=float(duration) if duration is not None else None,
                )
            )
        return cls(flow_id=flow_id, targets=tuple(targets), stages=tuple(parsed_stages))
