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

## License

Climate Flow is available under the [MIT License](LICENSE).
