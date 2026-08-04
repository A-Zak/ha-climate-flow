# Climate Flow

Climate Flow is a Home Assistant custom integration intended to run ordered
climate-control flows.

Milestone 2 adds saved flow configuration. Flows are created as native child
entries of Climate Flow and contain exactly two ordered climate stages. They
can select multiple climate targets and configure HVAC mode plus supported
temperature, fan, swing, and preset controls. Climate control, flow execution,
actions, entities, scheduling, completion conditions, persistence, and
dashboard UI are not implemented yet.

## Installation

Climate Flow Milestone 2 requires Home Assistant 2025.3 or newer because it
uses native config subentries for saved flows.

The repository is structured as a HACS custom integration. Until it is
published, add this repository to HACS as a custom integration repository,
then install Climate Flow and restart Home Assistant.

## Configuration

In Home Assistant, open **Settings > Devices & services**, select
**Add integration**, and choose **Climate Flow**. Only one Climate Flow config
entry is supported. After creating it, add a saved flow from the Climate Flow
integration page. A flow name produces an editable lowercase snake-case flow
ID, while Home Assistant keeps a separate stable internal identity.

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
generic thermostat backed by helper entities. Use it to create, edit, and
remove Climate Flow definitions without controlling a real device.

Home Assistant writes its database, auth data, logs, and other runtime state
under `.manual-ha`; those files are intentionally ignored. To restart manual
onboarding from scratch, stop the local server and remove only
`.manual-ha/.storage`, `.manual-ha/home-assistant.log`, and
`.manual-ha/.HA_VERSION`.

## License

Climate Flow is available under the [MIT License](LICENSE).
