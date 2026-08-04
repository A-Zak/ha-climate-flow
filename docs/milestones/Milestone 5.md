# Milestone 5: Restart Recovery and Hardening

## Goal

Persist active Climate Flow executions and restore them accurately after a
Home Assistant restart while hardening lifecycle, migration, and failure
handling.

## Included

- Versioned active-run persistence using Home Assistant's storage helper
- Continuous persistence at every meaningful execution transition
- Accurate duration and clock-time recovery
- Temperature-condition re-evaluation after recovery
- Recovery of remaining target ownership
- Safe handling of missing, stale, corrupt, or incompatible recovery data
- Clear shutdown, reload, disable, removal, and unload semantics
- Final lifecycle and migration hardening
- End-to-end restart tests and manual smoke procedures

## Persisted execution state

Saved flow definitions remain in config subentries. Active-run storage holds
only the minimum information needed to resume execution, including:

- Storage schema version
- Stable flow config subentry ID
- Current stage position
- Remaining climate targets
- Run and stage start timestamps
- Absolute duration, clock-time, or safety-timeout deadlines when applicable
- Current terminal or recovery status needed for validation

Definitions and active-run records are not stored in a custom database.
Logical flow IDs, display names, and stage names are not used as stable
recovery keys.

Storage is updated after:

- A successful start
- A stage transition
- A target removal
- Cancellation
- Completion
- Failure

Cancelled, completed, and failed runs are removed from active-run storage
after their terminal status has been published to the switch entity.

## Recovery behavior

On Home Assistant startup, Climate Flow validates every persisted run against
the current config entry and saved flow definition before reserving targets.

For duration and clock-time stages:

- Downtime counts toward absolute deadlines.
- If the current deadline is still in the future, reapply the current stage
  and schedule its remaining wait.
- If one or more timed stages elapsed while Home Assistant was offline, skip
  obsolete intermediate states without applying them briefly.
- Continue calculating from the persisted absolute timeline until reaching
  the currently effective stage.
- If an elapsed transition reaches an immediate final stage, apply that final
  climate state once and complete.

For temperature stages:

- Reapply the active stage to remaining targets.
- Read current temperatures after Home Assistant state restoration is ready.
- Advance immediately if the configured `any` or `all` condition is currently
  satisfied.
- Otherwise restore listeners and any remaining safety-timeout deadline.
- Do not assume that an unobserved threshold crossing occurred during
  downtime.

Recovered runs retain the partial-target policy. Invalid or unavailable
targets are removed, and the run fails if none remain.

## Lifecycle behavior

- Home Assistant shutdown preserves the latest active-run records for the
  next startup.
- A normal integration reload cancels active runs and clears their recovery
  records before setting the entry up again.
- Disabling or removing the config entry cancels all runs and clears their
  recovery records.
- Removing a saved flow clears any recovery record belonging to it.
- Cleanup remains idempotent if shutdown, unload, cancellation, and a
  completion callback occur close together.

The integration must distinguish Home Assistant shutdown from other unload
paths rather than treating every unload as recoverable.

## Invalid recovery data

Missing storage means there is nothing to resume and is not an error.

An individual stale, malformed, unknown-version, missing-flow, invalid-stage,
or conflicting-target record is discarded safely. Other valid records still
resume. The affected flow remains idle and the reason is logged without
preventing Climate Flow setup.

Recovery must never apply climate commands until the record, saved flow,
targets, and ownership have passed validation.

## Not included

- Restoring climate state from before a flow started
- A custom database
- Historical run reporting or analytics
- Cross-instance or remote synchronization
- Automatic retries that re-add targets dropped from a run
- Automatic conflict replacement or queuing
- A custom dashboard card

## Automated tests

- Persist every start, transition, target removal, and terminal cleanup.
- Resume a timed stage before its deadline with the correct remaining delay.
- Recover exactly at and after a deadline.
- Skip multiple elapsed stages without applying obsolete climate states.
- Apply an elapsed immediate final stage and complete.
- Recover clock-time stages across timezone and daylight-saving boundaries.
- Re-evaluate `any` and `all` temperature conditions from current state.
- Restore or expire a temperature safety timeout correctly.
- Recover with some targets unavailable and fail when none remain.
- Resolve ownership conflicts deterministically without partial commands.
- Ignore missing storage and isolate corrupt, stale, and incompatible records.
- Preserve records during Home Assistant shutdown.
- Clear records during reload, disable, entry removal, flow removal, and
  explicit cancellation.
- Prevent duplicate cleanup during shutdown and callback races.
- Verify setup succeeds even when one recovery record is rejected.

## Manual smoke test

1. Install the Milestone 5 build and restart Home Assistant.
2. Start a duration flow, restart before its deadline, and confirm it resumes
   with the correct remaining time.
3. Restart while enough time elapses to pass multiple stages and confirm only
   the currently effective state is applied.
4. Restart during a clock-time stage before and after its deadline.
5. Restart during a temperature stage and confirm current temperatures are
   re-evaluated.
6. Confirm a persisted safety timeout retains its original absolute deadline.
7. Reload Climate Flow without restarting Home Assistant and confirm active
   runs are cancelled instead of resumed.
8. Disable and re-enable the config entry and confirm stale runs do not return.
9. Remove an active saved flow and confirm its recovery record is cleared.
10. Inspect logs for recovery validation, resumed runs, discarded records, or
    lifecycle errors.
11. Once the integration is running correctly, remove all temporary debug
    logger overrides and restart Home Assistant.

## Completion criteria

- Active flows resume accurately after Home Assistant restart.
- Downtime is accounted for without transiently applying obsolete stages.
- Temperature conditions and safety timeouts recover predictably.
- Reload, disable, removal, cancellation, and shutdown have distinct tested
  behavior.
- Invalid persisted state cannot prevent integration setup or unsafe climate
  commands.
- Ruff, pytest, HACS validation, and hassfest pass.
- Documentation and translations match implemented behavior.
