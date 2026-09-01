"""The Trimlight integration."""

from aiotrimlight import TrimlightClient, TrimlightError
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import TrimlightConfigEntry, TrimlightCoordinator

PLATFORMS = (Platform.LIGHT,)


async def async_setup_entry(hass: HomeAssistant, entry: TrimlightConfigEntry) -> bool:
    """Set up Trimlight from a config entry."""
    client = TrimlightClient(
        entry.data[CONF_HOST],
        async_get_clientsession(hass),
    )
    try:
        device_info = await client.get_device_info()
    except TrimlightError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"error": str(err)},
        ) from err

    coordinator = TrimlightCoordinator(hass, entry, client, device_info)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TrimlightConfigEntry) -> bool:
    """Unload a Trimlight config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
