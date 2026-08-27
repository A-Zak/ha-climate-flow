"""Domain model for a pending ephemeral climate transition."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class PendingTransition:
    """A one-shot future climate state change for a single target."""

    target: str
    fires_at: datetime
    turn_off: bool = False
    turn_on: bool = False
    temperature_celsius: float | None = None

    def __post_init__(self) -> None:
        """Reject anything but exactly one target state."""
        target_states = (
            self.turn_off,
            self.turn_on,
            self.temperature_celsius is not None,
        )
        if sum(target_states) != 1:
            raise ValueError(
                "PendingTransition requires exactly one of turn_off, turn_on, "
                "or temperature_celsius"
            )

    def as_dict(self) -> dict[str, str | bool | float]:
        """Return a JSON-serializable summary suitable for a sensor attribute."""
        data: dict[str, str | bool | float] = {"fires_at": self.fires_at.isoformat()}
        if self.turn_off:
            data["turn_off"] = True
        elif self.turn_on:
            data["turn_on"] = True
        else:
            data["temperature_celsius"] = self.temperature_celsius
        return data
