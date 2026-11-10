# AlarmMesh

Vendor-independent smoke alarm linking, monitoring and testing for Home Assistant.

> AlarmMesh is not a certified fire alarm system and must not replace certified standalone smoke detectors.

## Current status: foundation only

The description above is the project direction, not functionality available today.
Version 0.0.1 provides a Home Assistant custom integration skeleton, prepared for
HACS packaging. It creates one empty configuration entry after confirmation.
It does not monitor smoke detectors, link alarms, activate sirens, send
notifications, or perform device tests. No entities or actions are exposed.

## Try the foundation

Use an isolated development Home Assistant instance (baseline: 2026.10.4).
Copy `custom_components/alarmmesh` into its configuration directory under
`custom_components/alarmmesh`, then restart Home Assistant. In **Settings >
Devices & services > Add integration**, select **AlarmMesh** and confirm the
foundation notice. Only one configuration can be added. Remove it from the
integration page to undo the setup.

Do not add `alarmmesh:` to `configuration.yaml`; configuration is UI-only.
HACS metadata is included, but this is not a published or approved HACS release.
There is no need to install it through HACS to develop the project.

## Development and design

- [Development setup and checks](docs/development.md)
- [Architecture and scope](docs/architecture.md)
- [Guidelines and publication readiness](docs/guidelines.md)

The repository includes tests, lint/format configuration, a Linux development
container, and GitHub workflows for tests and hassfest. No hardware access or
Home Assistant credentials are needed for the tests.
