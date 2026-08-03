# Climate Flow

Climate Flow is a Home Assistant custom integration intended to run ordered
climate-control flows.

Milestone 1 provides only the integration scaffold: it can be added through
**Settings > Devices & services** and supports setup, reload, and unload.
Climate control, flow execution, stages, completion conditions, actions,
sensors, persistence, and dashboard UI are not implemented yet.

## Installation

The repository is structured as a HACS custom integration. Until it is
published, add this repository to HACS as a custom integration repository,
then install Climate Flow and restart Home Assistant.

## Configuration

In Home Assistant, open **Settings > Devices & services**, select
**Add integration**, and choose **Climate Flow**. Only one Climate Flow config
entry is supported.

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
