# Climate Flow Architecture

## Status

This document records the current architectural direction for Climate Flow.

It is not a permanent specification.

Architectural decisions may change as the project develops, requirements
become clearer, and implementation experience reveals better approaches.

Implemented behavior is the final source of truth.

## Project structure

Climate Flow is a Home Assistant custom integration.

User-facing name:

`Climate Flow`

Home Assistant domain:

`climate_flow`

Integration code location:

`custom_components/climate_flow`

The project is intended to be distributed as a HACS-compatible custom
integration.

## High-level concept

Climate Flow runs ordered climate-control flows.

A flow is made of stages.

A stage generally represents:

1. A climate state to apply.
2. A rule that determines when the stage is complete.

Example:

1. Cool at 20°C until the measured room temperature reaches 26°C.
2. Cool at 26°C until 07:00.
3. Turn the climate device off.

Milestone 3 stores saved flow definitions as Home Assistant config subentries
and executes them through one switch per definition. Each definition has a
user-facing name, an internal logical flow ID, and a stable config subentry ID.
It contains exactly two stages: Stage 1 has a required duration and Stage 2
applies immediately before completion.

## Architectural layers

The integration should be divided conceptually into two main layers.

### Flow Engine

The Flow Engine contains the core execution logic.

Its responsibilities may include:

- Representing flows and stages.
- Tracking active flow execution.
- Advancing between stages.
- Handling cancellation.
- Preventing duplicate stage advancement.
- Handling completion conditions.
- Reporting execution state.

The Flow Engine should remain independent from Home Assistant APIs where this
can be achieved without unnecessary abstraction.

The engine does not directly decide how a Home Assistant climate entity is
controlled.

### Home Assistant adapter

The Home Assistant adapter connects the Flow Engine to Home Assistant.

Its responsibilities may include:

- Integration setup and unloading.
- Config entries.
- Registering Home Assistant actions.
- Calling climate services.
- Reading entity states and attributes.
- Subscribing to state changes.
- Scheduling callbacks.
- Using Home Assistant's configured timezone.
- Exposing integration state through entities or events.
- Restoring execution after a Home Assistant restart.

Home Assistant-specific code should not leak into the core engine unless doing
so clearly simplifies the design.

## Initial domain concepts

The following concepts describe the current direction.

They are not yet fixed public interfaces.

### Flow

A Flow is an ordered collection of stages.

Possible properties may include:

- Identifier.
- Display name.
- Ordered stages.
- Target climate entities.
- Replacement or cancellation behavior.

In Milestone 3, a flow definition targets one or more climate entities and
contains exactly two ordered stages. The internal logical flow ID is generated
as lowercase kebab case. The config subentry ID is the stable runtime and
switch identity.

### Stage

A Stage applies some climate configuration and may wait for a completion
condition.

Possible properties may include:

- Climate state.
- Completion condition.
- Optional safety timeout.
- Optional display name or description.

Milestone 2 stages have no custom display names and are shown as `Stage 1` and
`Stage 2`. Stage 1 has a required duration; Stage 2 completes immediately
after applying its state.

### Climate state

A climate state describes the values that should be applied when a stage
starts.

Initial values may include:

- HVAC mode.
- Target temperature.

Future values may include:

- Fan mode.
- Swing mode.
- Preset mode.

Only supported values should be sent to a climate entity.

### Completion condition

A completion condition decides when the current stage should advance.

Currently considered condition types include:

- Duration.
- Local clock time.
- Temperature threshold.

Future condition types may be added without changing the basic flow model.

The exact condition interface has not yet been chosen.

## Execution model

The intended execution sequence is:

1. Start a flow.
2. Validate the flow and its target.
3. Apply the current stage's climate state.
4. Begin observing its completion condition.
5. Advance when the condition is satisfied.
6. Clean up listeners and callbacks from the completed stage.
7. Apply the next stage.
8. Complete when there are no remaining stages.

Only one active flow should control a particular climate target unless a later
design explicitly supports otherwise.

Starting a new flow for an already-controlled target will likely require an
explicit replacement policy.

## Completion conditions

### Duration

A duration condition completes after a relative amount of time.

Example:

`Run this stage for 10 minutes.`

### Clock time

A clock-time condition completes at the next occurrence of a local time.

Example:

`Run this stage until 07:00.`

Clock calculations should use Home Assistant's configured timezone.

### Temperature threshold

A temperature condition completes when a measured temperature crosses a
directional threshold.

Examples:

- At or below 26°C.
- At or above 22°C.

The measured value may come from:

- The target climate entity's current temperature.
- A separate temperature sensor.

Exact floating-point equality should not be required.

## Safety and reliability

The execution system should be designed to handle:

- Unknown or unavailable entities.
- Invalid temperature values.
- Removed entities.
- Home Assistant restarts.
- Simultaneous timeout and condition completion.
- Repeated state-change events.
- Cancellation during stage execution.
- Integration unloading.
- Unsupported climate capabilities.

Listeners, timers, and callbacks must be cleaned up when they are no longer
needed.

A stage must advance no more than once.

## Persistence

Restart recovery is a desired capability, but the persistence design has not
yet been selected.

Possible persisted information may include:

- Flow definition or flow identifier.
- Target entities.
- Current stage index.
- Stage start time.
- Calculated deadline.
- Completion-condition configuration.

The initial project scaffold should not introduce a custom database.

## Home Assistant interface

Climate Flow should feel like a native Home Assistant integration.

Likely public actions include:

- `climate_flow.start`
- `climate_flow.cancel`

The final action schema has not yet been decided.

Future Home Assistant entities may expose:

- Whether a flow is active.
- Current stage.
- Remaining duration.
- Next stage.
- Flow status.
- Last error.

A custom dashboard card is not required for the initial implementation.

## Configuration

The integration should be configured using Home Assistant config entries and
UI flows.

YAML configuration should not be required.

Personal climate entity IDs, credentials, IP addresses, and manufacturer
settings must not be hardcoded into the repository.

## Extensibility

The first version is climate-specific.

The architecture should avoid unnecessary assumptions that would make future
extension impossible, but the project should not implement speculative
support for unrelated Home Assistant domains.

Possible future extensions include:

- Additional climate attributes.
- More completion-condition types.
- Reusable named flows.
- Multiple targets.
- Manual stage advancement.
- Conditional branching.
- Nested flows.

These are possibilities, not current requirements.

## Current open questions

The following decisions remain open:

- Whether targets belong to a Flow or are supplied when starting it.
- Whether a missing completion condition means immediate completion or an
  indefinite final stage.
- How flows are created and stored.
- Whether the first release accepts inline flow definitions, saved flows, or
  both.
- How replacement of an active flow should behave.
- How safety timeouts should behave.
- What entities Climate Flow should expose.
- How restart recovery should be implemented.
- Whether stage state and completion condition should be separate objects or
  part of one stage definition.

These questions should be resolved through focused milestones rather than
assumed prematurely.
