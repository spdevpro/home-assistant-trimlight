"""Data coordinator for the Trimlight integration."""

import logging
from typing import override

from aiotrimlight import (
    TrimlightClient,
    TrimlightDeviceInfo,
    TrimlightError,
    TrimlightLightState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


type TrimlightConfigEntry = ConfigEntry[TrimlightCoordinator]


class TrimlightCoordinator(DataUpdateCoordinator[TrimlightLightState]):
    """Coordinate runtime state polling for one Trimlight controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: TrimlightConfigEntry,
        client: TrimlightClient,
        device_info: TrimlightDeviceInfo,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.device_info = device_info
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )

    @override
    async def _async_update_data(self) -> TrimlightLightState:
        """Fetch the current device state."""
        try:
            return await self.client.get_light_state()
        except TrimlightError as err:
            raise UpdateFailed(f"Error communicating with controller: {err}") from err
