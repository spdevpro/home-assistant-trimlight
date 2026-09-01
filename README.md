# Trimlight for Home Assistant

<p align="center">
  <img src="custom_components/trimlight/brand/logo.png" alt="Trimlight" width="256">
</p>

Local Home Assistant integration for Trimlight controllers using the
Trimlight Edge Pro HTTP API.

> [!WARNING]
> This integration and the supported Trimlight firmware are currently in beta.
> It is distributed only as a HACS custom repository and is not listed in the
> HACS default repository.

## Features

- Discovers controllers through `_tlight._tcp.local.` mDNS advertisements.
- Uses the full device DID as the stable Home Assistant identifier.
- Registers the MAC address exposed by `aiotrimlight` with the device registry.
- Creates one config entry, one device, and one LightEntity per controller.
- Supports ON/OFF, brightness, RGB, RGBW, and RGBWW according to the controller
  IC type.
- Polls the local HTTP API every 30 seconds and does not use a cloud service.

## Requirements

- Home Assistant 2026.9.0b0 or newer.
- Python 3.14 or newer for development.
- A controller firmware that exposes the DID-only mDNS identity and the V2
  runtime-state/static-output HTTP API.
- The controller and Home Assistant must be on the same local network with
  mDNS traffic available between them.

## Configuration

Trimlight supports automatic network discovery only. Power on the controller
and connect it to the same network as Home Assistant. It will appear in the
**Discovered** section under **Settings → Devices & services**.

Manual Host configuration and active mDNS scanning are intentionally not
implemented. Rediscovery of the same DID updates only that controller's Host.

## Local development

The development layout keeps this repository next to a Home Assistant Core
checkout:

```text
HA/
├── aiotrimlight/
├── core/
└── home-assistant-trimlight/
```

Link the integration into the Core development configuration:

```shell
cd /path/to/HA/core/config/custom_components
ln -s ../../../home-assistant-trimlight/custom_components/trimlight trimlight
```

Home Assistant loads `config/custom_components/trimlight` before a built-in
integration with the same domain. Restart Home Assistant after creating or
changing the link.

Install the locked development dependencies and run the checks with:

```shell
uv sync --locked --group test
uv run --no-sync pytest --cov=custom_components.trimlight --cov-branch
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy custom_components tests
```

## HACS installation

Use the button below to add this repository to HACS:

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=spdevpro&repository=home-assistant-trimlight&category=integration)

Alternatively, add it manually:

1. Open HACS and select **Custom repositories** from the menu.
2. Add `https://github.com/spdevpro/home-assistant-trimlight` as an
   **Integration**.
3. Open Trimlight in HACS and download version `v0.1.0`.
4. Restart Home Assistant.

## Known limitations

- Effects, zones, schedules, music, DIY editors, and controller configuration
  are not exposed.
- When the controller is running an effect or reports inconsistent zone state,
  Home Assistant can show the authoritative ON/OFF state but brightness and
  color remain unknown.
- Changing the controller IC type requires reloading the config entry.

## Removal

Remove each Trimlight config entry from **Settings → Devices & services**. For
a HACS installation, remove the downloaded repository in HACS and restart Home
Assistant. For local development, remove only the `trimlight` symlink from the
Core configuration directory.

## License

MIT
