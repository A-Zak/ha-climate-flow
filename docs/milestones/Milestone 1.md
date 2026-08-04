# Milestone 1: Integration Scaffold

## Goal

Create a valid, loadable, HACS-compatible Home Assistant custom integration.

## Included

- Repository structure
- Integration manifest
- Minimal config flow
- Setup and unload lifecycle
- Translation files
- HACS metadata
- Development tooling
- Basic tests
- GitHub validation workflows

## Not included

- Climate control
- Flow execution
- Stage scheduling
- Completion conditions
- Persistence
- Sensors
- Dashboard cards
- Service actions

## Completion criteria

- Ruff passes
- Tests pass
- HACS validation passes
- Hassfest validation passes
- The integration can be added through Settings > Devices & services and its
  config entry appears on the Integrations tab, not the Helpers tab

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

Then:

1. Install the corrected Climate Flow version through HACS and restart Home
   Assistant.
2. Add Climate Flow from Settings > Devices & services.
3. Confirm exactly one Climate Flow entry appears on the Integrations tab and
   none appears on the Helpers tab.
4. Confirm the entry loads, reloads, and loads again after a restart.
5. Confirm adding a second entry is rejected.
6. Confirm Climate Flow creates no devices or entities in Milestone 1. The
   HACS repository/update device is HACS-owned and is unrelated.
7. Inspect the logs for setup, config-entry, loader, or Climate Flow errors.
8. Once the integration is running correctly, remove the temporary logger
   overrides above and restart Home Assistant.
