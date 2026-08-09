# Milestone 4: Generic AC Control Card

## Goal

Provide a compact, installable Home Assistant custom dashboard card for
controlling a standard `climate` entity.

The card is independent of saved Climate Flow definitions. It can therefore be
used with every compatible AC entity, whether or not the user has configured a
Climate Flow.

## Included

- A JavaScript Lovelace card served by this integration
- Card-picker registration and `climate`-entity suggestion
- Climate entity name and current target temperature
- A power button
- Target-temperature decrement and increment buttons
- Three vertical swing-direction buttons
- Configurable states that should be displayed as power-off
- Installation and configuration documentation

## Power state

Some AC integrations report an internal shutdown-cleaning or drying cycle as a
non-`off` climate state even though the user has turned the unit off. The card
treats the configured `off_states` list as visually off. Its default is:

```yaml
off_states:
  - off
  - cleaning
```

When the entity state is one of these values, the power button is shown off and
pressing it calls `climate.turn_on`. Otherwise the button calls
`climate.turn_off`. This affects only the card display and button behavior; it
does not alter the climate integration's underlying state.

## Swing directions

The card maps its three direction buttons to these raw `swing_mode` values:

| Button | Raw swing mode |
| --- | --- |
| Top | `fixed 1` |
| Middle | `fixed 3` |
| Bottom | `fixed 5` |

The selected button reflects the climate entity's current `swing_mode`. The
card deliberately does not send an automatic or continuous swing value.

## Card configuration

After registering the JavaScript module as a dashboard resource, use:

```yaml
type: custom:climate-flow-ac-card
entity: climate.example_ac
```

Optional configuration:

```yaml
type: custom:climate-flow-ac-card
entity: climate.example_ac
name: Bedroom AC
off_states:
  - off
  - cleaning
```

Temperature buttons call `climate.set_temperature` using the entity's current
target temperature and its `target_temp_step`. They are disabled while the
card displays the AC as off and at the entity's advertised minimum or maximum.

## Not included

- A replacement for Home Assistant's built-in climate card
- HVAC-mode, fan-mode, preset-mode, or horizontal-swing controls
- A custom Climate Flow entity type or a dependency on saved flows
- Per-device hardcoded entity IDs or manufacturer-specific commands
- Automatic discovery of non-standard cleaning state names

## Automated tests

- Verify the integration distributes the card asset.
- Verify the card declares climate power, temperature, and swing actions.
- Verify the three documented `fixed 1`, `fixed 3`, and `fixed 5` mappings.

Browser-level interaction testing is deferred until the repository has a
frontend test harness.

## Manual smoke test

1. Install the Milestone 4 build and restart Home Assistant.
2. Register `/api/climate_flow/card/climate-flow-ac-card.js` as a dashboard
   resource of type **JavaScript module**.
3. Add the card for a test `climate` entity and confirm its name appears.
4. Test power, temperature, and the top/middle/bottom swing buttons.
5. While the AC reports `cleaning`, confirm the card presents it as off.
6. Set a different `off_states` list if the climate integration uses another
   name for its shutdown-cleaning state.

## Completion criteria

- The card operates a standard `climate` entity without a saved flow.
- Cleaning is configurable as a visual-off state and defaults to `cleaning`.
- Direction buttons map to `fixed 1`, `fixed 3`, and `fixed 5`.
- Documentation describes resource registration and configuration.
- Ruff and pytest pass.
