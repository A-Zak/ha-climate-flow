# Climate Flow Development Instructions

## Project identity

This repository contains a Home Assistant custom integration.

User-facing name: `Climate Flow`

Home Assistant domain: `climate_flow`

Integration location:

`custom_components/climate_flow`

## Repository boundaries

- Work only inside this repository.
- Never access, inspect, mount, or modify a live Home Assistant configuration.
- Never request or store Home Assistant credentials, tokens, secrets,
  backups, databases, or `.storage` contents.
- Never deploy automatically to a Home Assistant instance.
- Never hardcode personal entity IDs, IP addresses, credentials, or
  manufacturer-specific configuration.
- Commit completed work with a meaningful, scoped commit message.
- Do not push commits, publish releases, deploy, or run destructive Git
  commands unless explicitly requested.
- Ask before adding a runtime dependency.

## Sources of truth

Before making changes, read:

1. This file.
2. The relevant files under `docs/`.
3. The current task provided by the user.

The files under `docs/` describe the current product and architecture.
They may change over time.

Do not treat old plans, comments, or unimplemented ideas as requirements.

If documentation conflicts with the current task, stop and explain the
conflict before implementing.

## Engineering principles

- Use current Home Assistant custom integration patterns.
- Use config entries and UI configuration rather than YAML configuration.
- Use asynchronous Home Assistant APIs.
- Never block the Home Assistant event loop.
- Keep domain logic separate from Home Assistant-specific adapters where
  practical.
- Use clear type hints.
- Prefer simple, focused modules.
- Avoid premature abstractions.
- Avoid speculative features.
- Do not claim that unimplemented behavior works.

## Quality

- Add or update tests for changed behavior.
- Use pytest for tests.
- Use Ruff for formatting and linting.
- Keep user-facing strings in the proper translation files.
- Keep README and documentation aligned with implemented behavior.
- Run the available checks after making changes.

## Workflow

Small, scoped, reversible changes that directly implement the current task do
not require a separate approval pause. Ask before broad, destructive,
externally visible, or architecturally significant changes.

Before editing:

1. Inspect the repository and relevant documentation.
2. Briefly describe the intended change.
3. Identify assumptions or ambiguities.
4. Make the smallest coherent change.

After editing:

1. Run formatting, linting, and tests.
2. Report the files changed.
3. Report test results.
4. Report unresolved questions or risks.

Do not broaden the task without explicit approval.
