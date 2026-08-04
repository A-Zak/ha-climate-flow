# Milestone 4: Generalized Stages and Conditions

## Goal

Expand saved flows from two fixed stages into user-managed ordered stage lists
and add clock-time and temperature-based completion conditions.

## Included

- Two or more ordered stages per saved flow
- Optional human-readable stage display names
- UI operations to add, edit, remove, and reorder stages
- Migration of every Milestone 2 and Milestone 3 two-stage flow
- Duration, local clock-time, and temperature-threshold conditions
- Temperature aggregation across flow targets using `any` or `all`
- Optional safety timeouts for temperature stages
- Richer runtime status attributes
- Active-flow edit protection for the generalized editor
- Idempotent handling of competing completion signals

## Stage model and migration

The fixed two-stage editor is replaced by an ordered collection containing at
least two stages. There is no fixed maximum unless Home Assistant imposes a
practical form limit that must be documented.

Each stage may have an optional display name. An unnamed stage is shown as
`Stage N`, using its current one-based position.

Existing two-stage flows are migrated without changing their order, climate
state, durations, display name, logical flow ID, config subentry ID, or switch
entity identity. Their stages remain unnamed and therefore display as
`Stage 1` and `Stage 2` until edited.

Reordering changes only stage position. Runtime persistence introduced later
must identify execution position explicitly rather than treating a stage name
as an identifier.

## Completion conditions

Every non-final stage must have one completion condition. The final stage may
omit its condition to apply its state and complete immediately.

Supported conditions are:

- `duration`: wait for a positive relative duration.
- `clock_time`: wait until the next occurrence of a local wall-clock time in
  Home Assistant's configured timezone.
- `temperature`: wait until current temperature is at or above, or at or
  below, a configured threshold.

Temperature conditions use the `current_temperature` attribute of the
remaining target climate entities. The user chooses one aggregation rule:

- `any`: advance when at least one remaining target satisfies the threshold.
- `all`: advance only when every remaining target satisfies the threshold.

The condition is evaluated immediately when its stage begins and after
relevant state changes. Exact floating-point equality is not required beyond
the inclusive at-or-above or at-or-below comparison.

An unknown or temporarily missing temperature does not satisfy the condition.
A target that becomes unavailable is removed under the partial-failure rules
from Milestone 3, after which `any` or `all` applies only to remaining targets.

A temperature stage may define a positive safety timeout. If the threshold is
not satisfied before that timeout, the entire flow fails; it never advances
silently.

## Runtime status and lifecycle

In addition to Milestone 3 attributes, the flow switch reports:

- Current stage display name or positional fallback
- Completion-condition type and summary
- Clock or safety-timeout deadline when applicable
- Last terminal result: completed, cancelled, or failed
- Last translated or user-readable error

Only one completion path may win for a stage. Duration deadlines,
clock-time deadlines, temperature events, safety timeouts, cancellation, and
target loss must use an idempotent advancement guard and clean up all losing
callbacks.

An active flow cannot be renamed, reconfigured, or reordered. The UI flow
aborts with a translated instruction to cancel it first. Removing an active
flow cancels it before removal.

## Failure behavior

- Invalid stage counts, conditions, time values, thresholds, and timeouts are
  rejected during configuration.
- A temperature stage is rejected if its selected climate targets do not
  expose usable current-temperature capability at configuration or start.
- Target and command failures retain Milestone 3 partial-continuation
  behavior.
- If no targets remain, the flow fails regardless of condition type.
- A safety timeout fails the complete flow and leaves climate state unchanged.
- External manual changes do not cancel a flow or trigger continuous state
  reapplication.

## Not included

- Restart persistence or recovery
- Separate temperature sensors as measurement sources
- Per-target climate states within one stage
- Boolean condition trees or arbitrary Home Assistant conditions
- Automatic conflict replacement or queuing
- Restoring pre-flow climate state
- A custom dashboard card

## Automated tests

- Create, edit, remove, and reorder generalized stages.
- Enforce a minimum of two stages and condition requirements by position.
- Store and display optional stage names with positional fallbacks.
- Migrate fixed two-stage flows without changing behavior or identity.
- Execute duration, next-local-clock-time, and temperature stages.
- Cover timezone and daylight-saving transitions for clock-time deadlines.
- Evaluate already-satisfied temperature conditions immediately.
- Verify inclusive at-or-above and at-or-below comparisons.
- Cover `any` and `all` as targets satisfy, become unavailable, or report
  invalid temperatures.
- Fail temperature stages at optional safety deadlines.
- Prevent duplicate advancement across every competing callback combination.
- Reject edits while active and preserve stable flow switch identity.
- Validate richer status attributes, terminal results, errors, and cleanup.

## Manual smoke test

1. Install the Milestone 4 build and restart Home Assistant.
2. Confirm existing two-stage flows migrate unchanged.
3. Add, name, remove, and reorder stages through the integration UI.
4. Run a flow with more than two duration stages and verify their order.
5. Run a clock-time stage and verify it advances at the configured local time.
6. Run temperature stages using both `any` and `all` across multiple targets.
7. Confirm an already-satisfied temperature stage advances immediately.
8. Confirm a temperature safety timeout fails rather than advances the flow.
9. Attempt to edit an active flow and verify the UI instructs cancellation
   first.
10. Confirm switch status attributes and logs describe stage transitions and
    the terminal result.
11. Inspect the temporary debug logs, then disable the debug logger overrides
    after the smoke test passes.

## Completion criteria

- Existing two-stage flows migrate without behavioral or identity changes.
- Users can manage two or more ordered, optionally named stages in the UI.
- Duration, clock-time, and temperature completion conditions behave as
  documented.
- Safety timeouts and competing callbacks fail or advance exactly once.
- Ruff, pytest, HACS validation, and hassfest pass.
- Documentation and translations match implemented behavior.
