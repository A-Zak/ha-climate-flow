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
        """Reject an invalid combination of target states.

        turn_off is exclusive: it cannot combine with anything else. Turning
        on and a temperature may combine, representing "turn on to this
        temperature" for a target that is currently off.
        """
        has_temperature = self.temperature_celsius is not None
        if self.turn_off:
            if self.turn_on or has_temperature:
                raise ValueError(
                    "PendingTransition cannot combine turn_off with turn_on "
                    "or temperature_celsius"
                )
        elif not self.turn_on and not has_temperature:
            raise ValueError(
                "PendingTransition requires turn_off, or turn_on and/or "
                "temperature_celsius"
            )

    def as_dict(self) -> dict[str, str | bool | float]:
        """Return a JSON-serializable summary suitable for a sensor attribute."""
        data: dict[str, str | bool | float] = {"fires_at": self.fires_at.isoformat()}
        if self.turn_off:
            data["turn_off"] = True
            return data
        if self.turn_on:
            data["turn_on"] = True
        if self.temperature_celsius is not None:
            data["temperature_celsius"] = self.temperature_celsius
        return data
