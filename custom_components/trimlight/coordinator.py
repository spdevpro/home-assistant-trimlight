"""Data coordinator for the Trimlight integration."""

import asyncio
import logging
from dataclasses import dataclass
from time import monotonic
from typing import NotRequired, TypedDict, Unpack, override

from aiotrimlight import (
    TrimlightClient,
    TrimlightCommandError,
    TrimlightDeviceInfo,
    TrimlightEffect,
    TrimlightError,
    TrimlightLightState,
    TrimlightOutputMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
EFFECT_REFRESH_INTERVAL = 300
EFFECT_RETRY_INTERVAL = 30


class TrimlightStateChanges(TypedDict):
    """Values accepted by the library's static output and switch command."""

    on: NotRequired[bool]
    brightness: NotRequired[int]
    red: NotRequired[int]
    green: NotRequired[int]
    blue: NotRequired[int]
    warm_white: NotRequired[int]
    cold_white: NotRequired[int]


@dataclass(frozen=True)
class TrimlightData:
    """Comparable runtime and library snapshot; None means no usable list."""

    state: TrimlightLightState
    effects: tuple[TrimlightEffect, ...] | None

    @property
    def effect_options(self) -> dict[str, int]:
        """Map unique HA labels to saved library IDs, never zone preset IDs."""
        return {
            f"{effect.name if effect.name.strip() else 'Scene'} [ID {effect.id}]": (
                effect.id
            )
            for effect in self.effects or ()
        }

    @property
    def output_modes(self) -> set[TrimlightOutputMode]:
        """Return modes of enabled outputs, independent of device power."""
        return {zone.output_mode for zone in self.state.zones if zone.output_enabled}

    @property
    def is_static(self) -> bool:
        """Whether readback describes uniform, adjustable static output."""
        return (
            self.output_modes == {TrimlightOutputMode.STATIC}
            and self.state.brightness is not None
        )


type TrimlightConfigEntry = ConfigEntry[TrimlightCoordinator]


class TrimlightCoordinator(DataUpdateCoordinator[TrimlightData]):
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
        self._command_lock = asyncio.Lock()
        self._effects: tuple[TrimlightEffect, ...] | None = None
        self._effects_unsupported = False
        self._effects_failed = False
        self._effects_attempt = float("-inf")
        self._effects_success = float("-inf")
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )

    @override
    async def _async_update_data(self) -> TrimlightData:
        """Fetch the current device state."""
        try:
            async with self._command_lock:
                state = await self.client.get_light_state()
                now = monotonic()
                unknown_id = state.scene_id is not None and not any(
                    effect.id == state.scene_id for effect in self._effects or ()
                )
                if (
                    not self._effects_unsupported
                    and now - self._effects_attempt >= EFFECT_RETRY_INTERVAL
                    and (
                        self._effects_failed
                        or now - self._effects_success >= EFFECT_REFRESH_INTERVAL
                        or unknown_id
                    )
                ):
                    await self._async_refresh_effects()
                return TrimlightData(state, self._effects)
        except TrimlightError as err:
            raise UpdateFailed(f"Error communicating with controller: {err}") from err

    async def _async_refresh_effects(self) -> bool:
        """Refresh optional capabilities while holding the command lock."""
        self._effects_attempt = monotonic()
        try:
            effects = await self.client.get_effect_list()
        except TrimlightError as err:
            if isinstance(err, TrimlightCommandError) and err.code == 101:
                self._effects_unsupported = True
                self._effects = None
                _LOGGER.debug("Controller does not support saved scenes")
            elif not self._effects_failed:
                _LOGGER.warning("Unable to refresh Trimlight scene list: %s", err)
            self._effects_failed = True
            return False
        if self._effects_failed:
            _LOGGER.info("Trimlight scene list refresh recovered")
        self._effects_failed = False
        self._effects = effects
        self._effects_success = monotonic()
        return True

    async def async_play_effect(self, option: str) -> None:
        """Validate a saved option, play, switch on and publish final readback."""
        async with self._command_lock:
            if (
                not self._effects_unsupported
                and monotonic() - self._effects_success >= EFFECT_REFRESH_INTERVAL
            ):
                refreshed = False
                if monotonic() - self._effects_attempt >= EFFECT_RETRY_INTERVAL:
                    refreshed = await self._async_refresh_effects()
                    self.async_set_updated_data(
                        TrimlightData(self.data.state, self._effects)
                    )
                if not refreshed:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="effect_list_unavailable",
                    )
            if (effect_id := self.data.effect_options.get(option)) is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_effect",
                    translation_placeholders={"effect": option},
                )
            # play_effect does not switch on. Both library calls include readback;
            # publish only the final one and never interleave a poll or command.
            await self.client.play_effect(effect_id)
            state = await self.client.set_light_state(on=True)
            self.async_set_updated_data(TrimlightData(state, self._effects))

    async def async_set_state(self, **changes: Unpack[TrimlightStateChanges]) -> None:
        """Serialize basic control, guarding brightness against App changes."""
        async with self._command_lock:
            if "brightness" in changes and "red" not in changes:
                state = await self.client.get_light_state()
                data = TrimlightData(state, self._effects)
                self.async_set_updated_data(data)
                if not data.is_static:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="scene_brightness_unsupported",
                    )
            state = await self.client.set_light_state(**changes)
            self.async_set_updated_data(TrimlightData(state, self._effects))
