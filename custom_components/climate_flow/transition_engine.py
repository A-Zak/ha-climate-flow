"""Home Assistant-independent state management for pending transitions."""

from .transition import PendingTransition


class TransitionEngine:
    """Track at most one pending transition per climate target."""

    def __init__(self) -> None:
        """Initialize an engine with no pending transitions."""
        self._pending: dict[str, tuple[int, PendingTransition]] = {}
        self._next_token = 0

    def pending(self, target: str) -> PendingTransition | None:
        """Return the pending transition for a target, if any."""
        entry = self._pending.get(target)
        return entry[1] if entry is not None else None

    def schedule(self, transition: PendingTransition) -> int:
        """Replace any pending transition for this target and return its token."""
        self._next_token += 1
        self._pending[transition.target] = (self._next_token, transition)
        return self._next_token

    def cancel(self, target: str, token: int) -> bool:
        """Clear a pending transition if the token is still current."""
        entry = self._pending.get(target)
        if entry is None or entry[0] != token:
            return False
        del self._pending[target]
        return True

    def fire(self, target: str, token: int) -> PendingTransition | None:
        """Clear and return a pending transition exactly once per token."""
        entry = self._pending.get(target)
        if entry is None or entry[0] != token:
            return None
        del self._pending[target]
        return entry[1]
