"""Light platform for Trimlight controllers."""

from collections.abc import Awaitable
from typing import Any, NotRequired, TypedDict, Unpack, override

from aiotrimlight import TrimlightError, TrimlightICType, TrimlightLightState
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DID, DOMAIN, MANUFACTURER
from .coordinator import TrimlightConfigEntry, TrimlightCoordinator

PARALLEL_UPDATES = 1

IC_COLOR_MODES = {
    TrimlightICType.RGB: ColorMode.RGB,
    TrimlightICType.RGBW: ColorMode.RGBW,
    TrimlightICType.RGBCW: ColorMode.RGBWW,
}


class _TrimlightStateChanges(TypedDict):
    """Values that may be changed by a Home Assistant light command."""

    on: NotRequired[bool]
    brightness: NotRequired[int]
    red: NotRequired[int]
    green: NotRequired[int]
    blue: NotRequired[int]
    warm_white: NotRequired[int]
    cold_white: NotRequired[int]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrimlightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one light for a Trimlight controller."""
    async_add_entities([TrimlightLight(entry)])


class TrimlightLight(CoordinatorEntity[TrimlightCoordinator], LightEntity):
    """Representation of a Trimlight controller."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: TrimlightConfigEntry) -> None:
        """Initialize the Trimlight light."""
        coordinator = entry.runtime_data
        super().__init__(coordinator)
        did = entry.data[CONF_DID]
        self._attr_unique_id = did
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, entry.data[CONF_MAC])},
            identifiers={(DOMAIN, did)},
            manufacturer=MANUFACTURER,
            name=entry.title,
            sw_version=coordinator.device_info.firmware_version,
        )
        self._client = coordinator.client
        self._color_mode = IC_COLOR_MODES[coordinator.device_info.ic_type]
        self._attr_color_mode = self._color_mode
        self._attr_supported_color_modes = {self._color_mode}
        self._apply_state(coordinator.data)

    def _apply_state(self, state: TrimlightLightState) -> None:
        """Apply controller readback to Home Assistant attributes."""
        self._attr_is_on = state.is_on
        self._attr_brightness = state.brightness
        red = state.red
        green = state.green
        blue = state.blue
        if self._color_mode is ColorMode.RGB:
            self._attr_rgb_color = (
                None
                if red is None or green is None or blue is None
                else (red, green, blue)
            )
        elif self._color_mode is ColorMode.RGBW:
            warm_white = state.warm_white
            self._attr_rgbw_color = (
                None
                if red is None or green is None or blue is None or warm_white is None
                else (red, green, blue, warm_white)
            )
        else:
            cold_white = state.cold_white
            warm_white = state.warm_white
            self._attr_rgbww_color = (
                None
                if red is None
                or green is None
                or blue is None
                or cold_white is None
                or warm_white is None
                else (red, green, blue, cold_white, warm_white)
            )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Apply a runtime state update from the coordinator."""
        self._apply_state(self.coordinator.data)
        super()._handle_coordinator_update()

    async def _async_set_state(self, **changes: Unpack[_TrimlightStateChanges]) -> None:
        """Set state and publish the controller readback."""
        await self._async_execute_command(self._client.set_light_state(**changes))

    async def _async_execute_command(
        self, command: Awaitable[TrimlightLightState]
    ) -> None:
        """Execute a device command and publish its readback."""
        try:
            state = await command
        except TrimlightError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        self.coordinator.async_set_updated_data(state)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        changes: _TrimlightStateChanges = {"on": True}
        if ATTR_BRIGHTNESS in kwargs:
            changes["brightness"] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            changes["red"] = red
            changes["green"] = green
            changes["blue"] = blue
        elif ATTR_RGBW_COLOR in kwargs:
            red, green, blue, warm_white = kwargs[ATTR_RGBW_COLOR]
            changes["red"] = red
            changes["green"] = green
            changes["blue"] = blue
            changes["warm_white"] = warm_white
        elif ATTR_RGBWW_COLOR in kwargs:
            red, green, blue, cold_white, warm_white = kwargs[ATTR_RGBWW_COLOR]
            changes["red"] = red
            changes["green"] = green
            changes["blue"] = blue
            changes["cold_white"] = cold_white
            changes["warm_white"] = warm_white

        await self._async_set_state(**changes)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_set_state(on=False)
