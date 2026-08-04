"""Home Assistant-independent state management for active Climate Flow runs."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from .flow import SavedFlow


class FlowConflictError(ValueError):
    """Raised when a flow start would take a target owned by another flow."""


@dataclass(frozen=True, slots=True)
class ActiveFlowRun:
    """An immutable view of an active saved-flow execution."""

    flow_key: str
    flow: SavedFlow
    targets: tuple[str, ...]
    current_stage: int
    started_at: datetime
    stage_started_at: datetime
    token: int


class FlowExecutionEngine:
    """Track active runs, stage advancement, and climate-target ownership."""

    def __init__(self) -> None:
        """Initialize an idle flow engine."""
        self._runs: dict[str, ActiveFlowRun] = {}
        self._owners: dict[str, str] = {}
        self._next_token = 0

    def is_active(self, flow_key: str) -> bool:
        """Return whether a flow currently owns a run."""
        return flow_key in self._runs

    def active_run(self, flow_key: str) -> ActiveFlowRun:
        """Return an active run by flow key."""
        return self._runs[flow_key]

    def owner_of(self, target: str) -> str | None:
        """Return the active flow owning a climate target, if any."""
        return self._owners.get(target)

    def start_many(
        self, flows: Mapping[str, SavedFlow], now: datetime
    ) -> tuple[ActiveFlowRun, ...]:
        """Atomically reserve and start all inactive, non-conflicting flows."""
        new_flows = {key: flow for key, flow in flows.items() if key not in self._runs}
        requested_owners: dict[str, str] = {}
        for flow_key, flow in new_flows.items():
            self._validate_flow(flow)
            for target in flow.targets:
                owner = self._owners.get(target)
                if owner is not None and owner != flow_key:
                    raise FlowConflictError(target)
                if (
                    requested_owner := requested_owners.get(target)
                ) is not None and requested_owner != flow_key:
                    raise FlowConflictError(target)
                requested_owners[target] = flow_key

        started: list[ActiveFlowRun] = []
        for flow_key, flow in new_flows.items():
            self._next_token += 1
            run = ActiveFlowRun(
                flow_key=flow_key,
                flow=flow,
                targets=flow.targets,
                current_stage=0,
                started_at=now,
                stage_started_at=now,
                token=self._next_token,
            )
            self._runs[flow_key] = run
            for target in flow.targets:
                self._owners[target] = flow_key
            started.append(run)
        return tuple(started)

    def advance(self, flow_key: str, token: int, now: datetime) -> ActiveFlowRun | None:
        """Advance a run exactly once from Stage 1 to Stage 2."""
        run = self._runs.get(flow_key)
        if run is None or run.token != token or run.current_stage != 0:
            return None
        advanced = ActiveFlowRun(
            flow_key=run.flow_key,
            flow=run.flow,
            targets=run.targets,
            current_stage=1,
            started_at=run.started_at,
            stage_started_at=now,
            token=run.token,
        )
        self._runs[flow_key] = advanced
        return advanced

    def drop_target(self, flow_key: str, token: int, target: str) -> bool:
        """Drop one target and return whether doing so ended the run."""
        run = self._runs.get(flow_key)
        if run is None or run.token != token or target not in run.targets:
            return False
        targets = tuple(existing for existing in run.targets if existing != target)
        self._owners.pop(target, None)
        if not targets:
            self._runs.pop(flow_key)
            return True
        self._runs[flow_key] = ActiveFlowRun(
            flow_key=run.flow_key,
            flow=run.flow,
            targets=targets,
            current_stage=run.current_stage,
            started_at=run.started_at,
            stage_started_at=run.stage_started_at,
            token=run.token,
        )
        return False

    def complete(self, flow_key: str, token: int) -> bool:
        """Complete a run and release all its targets."""
        return self._end(flow_key, token)

    def cancel(self, flow_key: str, token: int) -> bool:
        """Cancel a run and release all its targets."""
        return self._end(flow_key, token)

    def _end(self, flow_key: str, token: int) -> bool:
        run = self._runs.get(flow_key)
        if run is None or run.token != token:
            return False
        self._runs.pop(flow_key)
        for target in run.targets:
            self._owners.pop(target, None)
        return True

    @staticmethod
    def _validate_flow(flow: SavedFlow) -> None:
        """Reject definitions that cannot execute in Milestone 3."""
        if len(flow.stages) != 2 or flow.stages[0].duration_seconds is None:
            raise ValueError("A two-stage flow requires a Stage 1 duration")
        if flow.stages[0].duration_seconds <= 0 or flow.stages[1].duration_seconds:
            raise ValueError("Invalid two-stage duration configuration")
