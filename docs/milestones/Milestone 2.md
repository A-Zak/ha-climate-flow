# Milestone 2: Saved Two-Stage Flows

## Goal

Allow users to create, edit, and delete reusable named climate flows through
the Home Assistant integration UI.

Milestone 2 stores configuration only. It does not run flows or control
climate entities.

Milestone 2 requires Home Assistant 2025.3 or newer, which introduced native
config subentries.

## Included

- A `flow` config subentry type owned by the singleton Climate Flow config
  entry
- Native Home Assistant UI flows for creating and reconfiguring flow
  subentries
- Home Assistant's normal config-subentry removal behavior
- An optional first-flow setup step after the main config entry is created
- A human-readable flow name
- A user-editable flow ID
- Selection of one or more climate entities
- Exactly two ordered stages, shown as `Stage 1` and `Stage 2`
- Stage controls for HVAC mode, target temperature, fan mode, swing mode, and
  preset mode
- Duration-based stage configuration
- Translation strings for every form, field, error, and abort reason
- A versioned stored flow schema and typed domain models

## Flow identity

Each saved flow has three distinct identity values:

- `name` is the human-readable name shown to the user.
- `flow_id` is the user-facing logical identifier stored with the flow.
- The Home Assistant config subentry ID is the stable internal identity.

When a flow ID is left blank, the flow name is converted to lowercase snake
case before saving. Users may enter a flow ID explicitly in the same form.

A flow ID must:

- Contain only lowercase letters, numbers, and single underscores.
- Not begin or end with an underscore.
- Not contain consecutive underscores.
- Be unique within the Climate Flow config entry.

If conversion produces an empty or duplicate ID, the form remains open and
asks the user to provide a valid unique value. During reconfiguration, the
existing flow ID is suggested and is not regenerated merely because the name
changed. The user may explicitly change it.

Changing `name` or `flow_id` never changes the config subentry ID. Future
entities and runtime persistence must use the config subentry ID as their
stable identity so that user-facing changes do not break automations.

## Targets and climate controls

A flow must target at least one entity from the `climate` domain. All stages
apply the same configured state to every selected target.

The editor determines the capabilities shared by all selected targets and
only offers common HVAC, fan, swing, and preset values. Temperature input is
limited to the common supported range. Saved data is validated again when the
form is submitted.

Temperatures are stored canonically in Celsius and converted at the Home
Assistant UI boundary. Durations are stored as positive seconds.

## Two-stage model

Milestone 2 always stores exactly two stages. Stages do not have custom names.

`Stage 1` contains:

- Required HVAC mode
- Optional target temperature, fan mode, swing mode, and preset mode
- Required positive duration

`Stage 2` contains:

- Required HVAC mode
- Optional target temperature, fan mode, swing mode, and preset mode

Stage 2 has no duration in Milestone 2. Its intended future meaning is to
apply its climate state and complete immediately. This supports a final state
such as turning the targets off.

The stored representation should use an ordered stage collection even though
this milestone validates its length as exactly two. This avoids a destructive
schema replacement when arbitrary stage counts are introduced later.

## Failure and lifecycle behavior

- Invalid or duplicate flow IDs keep the relevant form open with a translated
  field error.
- Missing targets, unsupported shared controls, invalid temperatures, and
  invalid durations are rejected before saving.
- Reconfiguring a flow updates the existing subentry and does not create a new
  one.
- Removing a flow removes only that subentry.
- Setup and unload remain successful regardless of whether any flows exist.

## Not included

- Climate entity control
- Flow execution or scheduling
- Switch or status entities
- `climate_flow.start` or `climate_flow.cancel`
- Clock-time or temperature-threshold conditions
- More or fewer than two stages
- Custom stage display names
- Runtime state or restart recovery
- YAML configuration
- A custom dashboard card

## Automated tests

- Create a flow subentry through the UI flow.
- Generate a lowercase snake-case flow ID from a display name.
- Allow the generated ID to be edited.
- Reject malformed, empty, and duplicate IDs.
- Preserve an existing ID when only the display name changes.
- Update the same subentry during reconfiguration.
- Add and remove multiple independent flow subentries.
- Require one or more climate targets.
- Verify capability intersections and reject unsupported values.
- Validate canonical temperature conversion and positive duration storage.
- Require exactly two stages and a Stage 1 duration; do not expose a Stage 2
  duration.
- Cover all config-subentry flow results, errors, and translations.

## Manual smoke test

Temporarily enable detailed logging on the test Home Assistant instance:

```yaml
logger:
  default: info
  logs:
    custom_components.climate_flow: debug
    homeassistant.components.config: debug
    homeassistant.config_entries: debug
    homeassistant.loader: debug
    homeassistant.setup: debug
```

1. Install the Milestone 2 build and restart Home Assistant.
2. Open Settings > Devices & services > Climate Flow.
3. Add a flow named `Bedroom Night Cooling` and confirm the suggested ID is
   `bedroom_night_cooling`.
4. Edit the suggested ID before saving and confirm the edited value persists.
5. Select multiple climate targets and configure Stage 1 and Stage 2.
6. Confirm Stage 1 requires a duration and Stage 2 permits no duration.
7. Confirm the saved flow appears as a subentry under Climate Flow.
8. Rename the flow and confirm its flow ID remains unchanged unless edited.
9. Create another flow and confirm duplicate flow IDs are rejected.
10. Reconfigure and remove flows through the native integration UI.
11. Confirm no Climate Flow entities, devices, actions, or climate commands
    are created in this milestone.
12. Inspect the temporary debug logs, then disable the debug logger overrides
    after the smoke test passes.

## Completion criteria

- Users can create, reconfigure, and remove saved two-stage flows entirely
  through the Home Assistant UI.
- Stored flows have separate display names, editable logical IDs, and stable
  internal subentry IDs.
- Invalid configuration cannot be saved.
- No flow-execution behavior is introduced.
- Ruff, pytest, HACS validation, and hassfest pass.
- Documentation and translations match implemented behavior.
