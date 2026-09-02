# Trimlight for Home Assistant

<p align="center">
  <img src="custom_components/trimlight/brand/logo.png" alt="Trimlight" width="256">
</p>

Trimlight for Home Assistant adds local control of compatible Trimlight controllers to Home Assistant.

The integration automatically discovers supported Trimlight controllers and communicates with them directly over your local network.

> [!WARNING]
> This integration is currently in beta.
>
> It is distributed as a HACS custom repository and is not currently available in the HACS default repository or included with Home Assistant.

## Supported devices

Currently supported:

- Trimlight Edge Pro

Additional Trimlight devices may be supported in future releases.

## Features

- Automatic device discovery
- Local network control
- Power on/off
- Brightness control
- RGB color control
- RGBW color control on supported installations
- RGBWW color control on supported installations
- Automatic recovery when a controller temporarily goes offline

Available color controls depend on the lighting configuration connected to your controller.

## Requirements

Before installing, make sure:

- You are running Home Assistant 2026.9.0b0 or newer.
- Your Trimlight controller is running compatible firmware.
- Your Trimlight controller and Home Assistant are connected to the same local network.
- Local device discovery is available between the controller and Home Assistant.

## Installation

### Install with HACS

Use the button below to add this repository to HACS:

[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=spdevpro&repository=home-assistant-trimlight&category=integration)

Or add the repository manually:

1. Open **HACS** in Home Assistant.
2. Open the menu and select **Custom repositories**.
3. Add:

   `https://github.com/spdevpro/home-assistant-trimlight`

4. Select **Integration** as the repository type.
5. Open **Trimlight** in HACS and select **Download**.
6. Restart Home Assistant.

## Add your Trimlight controller

Trimlight controllers are discovered automatically.

1. Power on your Trimlight controller.
2. Make sure it is connected to the same local network as Home Assistant.
3. In Home Assistant, go to **Settings → Devices & services**.
4. Look for your Trimlight controller under **Discovered**.
5. Select **Configure** and confirm the device.

Your Trimlight lights will then be available in Home Assistant.

Manual IP address configuration is not currently supported.

## Using the integration

Once configured, your Trimlight controller appears as a device in Home Assistant with a light entity.

Depending on your lighting configuration, you can control:

- On/off
- Brightness
- Color
- White channels

You can use the light in Home Assistant dashboards, scenes, scripts, and automations just like other Home Assistant lights.

## Notes

The integration currently exposes each supported Trimlight controller as a single light in Home Assistant.

Trimlight controllers can also be controlled through the Trimlight app. Changes made in the app are automatically detected by Home Assistant.

Some Trimlight app features, such as effects or lighting that uses different settings across multiple zones, cannot be represented as a single Home Assistant light state. While these modes are active, Home Assistant will continue to show the correct on/off state, but brightness and color may be unavailable until the controller returns to a uniform static color.

Changing the color or brightness from Home Assistant will switch the controller back to a static lighting state that Home Assistant can represent.

If the lighting type configured on the controller is changed, reload the Trimlight integration in Home Assistant.

## Troubleshooting

### My controller is not discovered

Check that:

- The controller is powered on.
- Home Assistant and the controller are on the same local network.
- Your network allows local device discovery between them.
- You are using a supported controller and compatible firmware.

You can also restart the controller and Home Assistant and wait briefly for discovery to occur again.

### My light shows as unavailable

If the controller loses power or network connectivity, Home Assistant may temporarily show the light as unavailable.

The integration will automatically try to reconnect. Once the controller is reachable again, the light should recover without needing to be added again.

### The integration does not appear after installing it

Restart Home Assistant after installing or updating the integration through HACS.

If necessary, refresh your browser after Home Assistant has restarted.

## Updating

When a new Trimlight integration version is available, HACS will show an available update.

Install the update through HACS and restart Home Assistant when requested.

## Removal

To remove a Trimlight controller from Home Assistant:

1. Go to **Settings → Devices & services**.
2. Open the **Trimlight** integration.
3. Remove the configured Trimlight entry.

To completely uninstall the custom integration:

1. Remove all Trimlight entries from **Settings → Devices & services**.
2. Open **HACS** and remove the Trimlight integration.
3. Restart Home Assistant.

## Support

If you encounter a problem, please report it through the GitHub issue tracker:

https://github.com/spdevpro/home-assistant-trimlight/issues

When reporting an issue, include:

- Your Home Assistant version
- Your Trimlight controller model
- Your Trimlight firmware version
- A description of the problem
- Relevant Home Assistant logs, if available

## License

MIT
