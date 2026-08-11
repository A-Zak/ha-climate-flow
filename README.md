# Climate Flow

Climate Flow is a Home Assistant custom integration intended to run ordered
climate-control flows.

Milestone 3 runs saved two-stage flows. Each saved flow is a native child entry
of Climate Flow and has a switch entity. Starting it applies Stage 1 for its
configured duration, applies Stage 2, then completes. Flows can select multiple
climate targets and configure HVAC mode plus supported temperature, fan, swing,
and preset controls.

Milestone 4 also adds a generic AC dashboard card for standard `climate`
entities. It shows the AC name, provides power and target-temperature controls,
and maps top, middle, and bottom swing buttons to `fixed 1`, `fixed 3`, and
`fixed 5` respectively.

## Installation

Climate Flow Milestone 3 requires Home Assistant 2025.3 or newer because it
uses native config subentries for saved flows.

The repository is structured as a HACS custom integration. Until it is
published, add this repository to HACS as a custom integration repository,
then install Climate Flow and restart Home Assistant.

## Configuration

In Home Assistant, open **Settings > Devices & services**, select
**Add integration**, and choose **Climate Flow**. Only one Climate Flow config
entry is supported. After creating it, add a saved flow from the Climate Flow
integration page. A flow name produces an internal lowercase kebab-case ID,
while Home Assistant keeps a separate stable config-subentry identity.

Each saved flow has one switch. Turn it on to execute the flow and off to
cancel it without restoring climate state. Automations may use
`climate_flow.start` and `climate_flow.cancel`, targeting one or more Climate
Flow switch entities. Flows with disjoint climate targets may run together;
overlapping flows are rejected.

## AC dashboard card

Register `/api/climate_flow/card/climate-flow-ac-card.js` in **Settings >
Dashboards > Resources** as a **JavaScript module**, then add this card:

```yaml
type: custom:climate-flow-ac-card
entity: climate.example_ac
```

The card treats `off` and `cleaning` as visually off by default. For an AC
that uses a different state during its shutdown-drying cycle, configure it:

```yaml
type: custom:climate-flow-ac-card
entity: climate.example_ac
off_states:
  - off
  - drying
cleaning_states:
  - drying
```

It displays the entity's `current_temperature` whenever available. The power
button is green while active, red while off or unavailable, and blue with a
dashed outline during a configured cleaning state. It also displays the current
HVAC action or mode and highlights a mapped swing position; another swing mode
is shown by name beside the direction controls. The three-dots button opens
Home Assistant's standard full climate-control dialog.

When a card control sends a climate command, that control shows a short
glowing rotating indicator until Home Assistant accepts or rejects the action.
Click the target temperature to reveal a slider using the entity's supported
temperature range and step; releasing it sends the selected target temperature.

An active `self_cleaning` attribute or a `preset_mode` of `cleaning` is also
treated as cleaning, even if the entity's main state remains `cool` or `off`.

## Development

Development uses Python 3.14, pytest, and Ruff. Install the test dependencies
and run:

```sh
python -m ruff format --check .
python -m ruff check .
python -m pytest -v --cov=custom_components.climate_flow --cov-report=term-missing
```

## Manual Home Assistant smoke test

The tracked [`.manual-ha`](.manual-ha) fixture starts a disposable local Home
Assistant UI on `http://127.0.0.1:8124`. It never accesses a live Home
Assistant instance on port 8123. Its `custom_components/climate_flow` symlink
points to this repository's integration source, so restart the local server
after changing integration code.

After creating the development environment, install the browser-UI-only
requirements and start the fixture:

```sh
.venv/bin/pip install -r .manual-ha/requirements.txt
.venv/bin/hass -c .manual-ha
```

On first use, create a throwaway local account at
`http://127.0.0.1:8124`. The fixture provides `climate.test_climate`, a local
generic thermostats backed by helper entities: `climate.test_climate`,
`climate.test_climate_office`, and `climate.test_climate_lounge`. Use them to
create, execute, edit, and remove Climate Flow definitions without controlling
a real device.

Home Assistant writes its database, auth data, logs, and other runtime state
under `.manual-ha`; those files are intentionally ignored. To restart manual
onboarding from scratch, stop the local server and remove only
`.manual-ha/.storage`, `.manual-ha/home-assistant.log`, and
`.manual-ha/.HA_VERSION`.

## License

Climate Flow is available under the [MIT License](LICENSE).
