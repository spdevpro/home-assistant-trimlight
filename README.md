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
- Saved scene selection through the light's effect list
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
- Saved scenes (effects)

You can use the light in Home Assistant dashboards, scenes, scripts, and automations just like other Home Assistant lights.

### Selecting a saved scene

Open the light's controls and choose an effect. Options use the controller's saved scene name followed by its ID, for example `Ocean [ID 1]`. Duplicate names remain separate; unnamed scenes appear as `Scene [ID 3]`.

You can also use the standard light action. Copy the exact option from your light's `effect_list`:

```yaml
action: light.turn_on
target:
  entity_id: light.your_trimlight
data:
  effect: "Ocean [ID 1]"
```

Selecting a scene plays it and turns the controller on. If the same action includes brightness or color, the scene takes priority and those adjustments are ignored. Ordinary on/off actions preserve the controller's output mode.

The selected effect represents the **currently associated scene**, not a comparison with its saved settings. Unsaved previews and overwriting a scene in the Trimlight app keep the association; saving as a new scene follows the new ID reported by the controller. Home Assistant shows an association only when the controller is on, all enabled zones use effect output, and the ID exists in the saved scene list. Static output, disabled output, mixed zones, missing IDs and deleted scenes do not show a selected saved scene.

Runtime state is polled every 30 seconds. The saved list refreshes at startup and every 5 minutes; an unfamiliar associated ID triggers an earlier refresh, limited to once per 30 seconds. Renaming or deleting a scene may therefore take up to 5 minutes to appear while the controller is reachable. Renamed options must also be updated in automations. Stale lists are refreshed before playback; an unsuccessful refresh or invalid option produces an error instead of guessing a scene.

An empty scene library does not affect basic light controls. Older firmware that omits the association ID can still offer scene selection if its commands work, but the selected effect remains unknown. If the controller reports that scene queries are unsupported, only scene selection is disabled; reload the integration after a firmware update to check again. Temporary list errors are retried and preserve the last successful list.

Scene brightness adjustment is not supported. Brightness-only actions check current output and are rejected unless it is uniform static output, including when an App change has happened since the last poll. To leave a scene, explicitly select a static color; you can then adjust brightness. Brightness zero retains Home Assistant's standard turn-off behavior. Scene editing, saving, deletion, combined-scene selection and individual Zone entities are not provided.

No integration-specific actions, triggers or conditions are added; use the standard Home Assistant light actions and state-based automations.

## Notes

The integration currently exposes each supported Trimlight controller as a single light in Home Assistant.

Trimlight controllers can also be controlled through the Trimlight app. Changes made in the app are automatically detected by Home Assistant.

Lighting that uses different settings across multiple zones cannot be represented as a single Home Assistant light state. During scenes or mixed output, Home Assistant continues to show the controller's on/off state, but brightness and color are unavailable until it returns to uniform static output. On/off reflects the controller switch, not a guarantee that LEDs are currently emitting light.

Changing the color from Home Assistant switches the controller back to static output. Brightness alone does not switch an active scene to static output.

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

For a manual installation or an unreleased development checkout, copy `custom_components/trimlight` from the chosen revision into your Home Assistant configuration's `custom_components` directory, replacing the previous Trimlight folder, then restart Home Assistant. Home Assistant installs the pinned `aiotrimlight==0.3.0` dependency automatically; do not install a local development library into your running Home Assistant environment. Downloading a previous release does not include unreleased changes.

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
