# Milestone 3: Two-Stage Duration Execution

## Goal

Run saved two-stage flows against their configured climate targets and expose
native Home Assistant controls for starting, cancelling, and observing a run.

## Included

- A Home Assistant-independent execution engine for two-stage duration flows
- A singleton runtime manager stored in the Climate Flow config entry's
  runtime data
- One switch entity for each saved flow subentry
- `climate_flow.start` and `climate_flow.cancel` actions
- Duration scheduling for Stage 1 and immediate completion after Stage 2
- Applying all climate controls introduced in Milestone 2
- Concurrent execution of flows with disjoint target sets
- Target ownership and overlap protection
- Partial continuation when individual climate targets fail
- Complete listener and timer cleanup
- User-facing action descriptions, translations, and documentation

## Public interface

Each saved flow exposes a switch entity whose unique ID is derived from the
stable config subentry ID.

- Turning the switch on starts the saved flow.
- Turning the switch off cancels its active run.
- The switch is on only while that flow is running.
- Renaming the flow or changing its logical flow ID does not replace the
  entity or break entity-based automations.

The `climate_flow.start` and `climate_flow.cancel` actions target one or more
Climate Flow switch entities. They provide explicit equivalents to
`switch.turn_on` and `switch.turn_off`.

Starting an already active flow and cancelling an idle flow are idempotent.
When a single `climate_flow.start` request targets multiple flows, the manager
validates all target ownership before starting any of them.

## Execution behavior

When a flow starts:

1. Load and validate a snapshot of its saved definition.
2. Reject the start if any climate target is owned by another active flow.
3. Reserve all targets for the new run.
4. Apply Stage 1 to each target.
5. Wait for the Stage 1 duration.
6. Apply Stage 2 to each remaining target.
7. Complete the run and release all remaining targets.

Climate state application supports HVAC mode, target temperature, fan mode,
swing mode, and preset mode. Values are validated against current target
capabilities before use.

Different flows may execute concurrently when their target sets do not
overlap. Overlapping starts fail with a clear Home Assistant action error and
do not disturb existing runs.

## Failure and lifecycle behavior

- If a target is unavailable or a climate command for it fails, permanently
  remove that target from the current run and continue with the others.
- If all targets are removed, fail the run and turn its switch off.
- Do not roll back climate commands that were already applied successfully.
- Cancelling removes pending callbacks and releases targets but leaves every
  climate entity in its last applied state.
- A stage may advance no more than once, including when cancellation races a
  duration callback.
- Reconfiguring an active flow is rejected with a translated instruction to
  cancel it first.
- Removing an active flow cancels it before its switch entity is removed.
- A normal integration unload cancels all active runs and cleans up runtime
  resources.
- Restart recovery is not implemented; flows return idle after a restart.

## Status

The flow switch exposes basic attributes while running:

- Logical flow ID
- Current stage number
- Total stage count
- Remaining active targets
- Run start time
- Stage start time
- Current duration deadline, when applicable

Completion, cancellation, dropped targets, and failures are logged without
logging unrelated entity state or sensitive configuration.

## Not included

- More or fewer than two stages
- Custom stage display names
- Local clock-time conditions
- Temperature-threshold conditions
- Temperature safety timeouts
- Restart persistence or recovery
- Restoring pre-flow climate state
- Automatic replacement or queuing of conflicting flows
- Continuous reapplication after external manual climate changes
- A custom dashboard card

## Automated tests

- Create stable switch entities from saved flow subentries.
- Start and cancel flows through both switch and Climate Flow actions.
- Apply both stages in order and complete immediately after Stage 2.
- Verify all supported climate controls and unit conversion.
- Complete immediately after applying an undelayed Stage 2.
- Run disjoint flows concurrently.
- Reject overlaps without cancelling or partially starting other flows.
- Treat repeated start and cancellation requests idempotently.
- Drop one failed target and continue remaining targets.
- Fail and clean up when every target is lost.
- Prevent duplicate advancement during timer and cancellation races.
- Reject active-flow reconfiguration and cancel on removal.
- Unload with no remaining timers, listeners, ownership, or entities.
- Validate action schemas, errors, translations, and switch attributes.

## Manual smoke test

1. Install the Milestone 3 build and restart Home Assistant.
2. Confirm each saved flow has one switch entity and no Climate Flow device.
3. Start a flow from its switch and confirm Stage 1 is applied to all targets.
4. Wait for Stage 1 to expire and confirm Stage 2 is applied.
5. Confirm the switch turns off when the flow completes.
6. Start and cancel the flow with `climate_flow.start` and
   `climate_flow.cancel` from Developer Tools > Actions.
7. Confirm cancellation leaves the climate entities in their current states.
8. Run disjoint flows concurrently and confirm an overlapping flow is
   rejected without interrupting them.
9. Make one target unavailable and confirm the remaining targets continue.
10. Reload Climate Flow and confirm all runs and callbacks are cleaned up.
11. Inspect the temporary debug logs, then disable the debug logger overrides
    after the smoke test passes.

## Completion criteria

- Saved two-stage flows execute reliably through switch and Climate Flow
  actions.
- Disjoint concurrency, overlap rejection, partial target failure, and
  cancellation behave as documented.
- Runtime resources are cleaned up on completion, cancellation, removal, and
  unload.
- Ruff, pytest, HACS validation, and hassfest pass.
- Documentation and translations match implemented behavior.
