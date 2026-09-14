"""Tests for the Trimlight light platform."""

from unittest.mock import MagicMock

import pytest
from aiotrimlight import (
    TrimlightConnectionError,
    TrimlightDeviceInfo,
    TrimlightICType,
    TrimlightLightState,
    TrimlightOutputMode,
    TrimlightZoneState,
)
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
)
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.trimlight.const import DOMAIN, MANUFACTURER, SCAN_INTERVAL

from . import setup_integration
from .conftest import DID, MAC, NAME

ENTITY_ID = "light.test_controller"
FIRMWARE_VERSION = "1.0.38.1.0.13r"


@pytest.mark.parametrize(
    ("ic_type", "color_mode", "color_attribute"),
    [
        pytest.param(
            TrimlightICType.RGB,
            ColorMode.RGB,
            ATTR_RGB_COLOR,
            id="rgb",
        ),
        pytest.param(
            TrimlightICType.RGBW,
            ColorMode.RGBW,
            ATTR_RGBW_COLOR,
            id="rgbw",
        ),
        pytest.param(
            TrimlightICType.RGBCW,
            ColorMode.RGBWW,
            ATTR_RGBWW_COLOR,
            id="rgbww",
        ),
    ],
)
async def test_light_capabilities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
    ic_type: TrimlightICType,
    color_mode: ColorMode,
    color_attribute: str,
) -> None:
    """Test one light is created with the IC-specific color mode."""
    mock_trimlight.return_value.get_device_info.return_value = TrimlightDeviceInfo(
        firmware_version=FIRMWARE_VERSION,
        ic_type=ic_type,
    )

    await setup_integration(hass, mock_config_entry)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 1
    assert entries[0].entity_id == ENTITY_ID
    assert entries[0].unique_id == DID

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert "assumed_state" not in state.attributes
    assert state.attributes[ATTR_BRIGHTNESS] is None
    assert state.attributes[ATTR_COLOR_MODE] is None
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [color_mode]
    assert state.attributes[color_attribute] is None


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Test the light device registry information."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}
    assert (
        device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, MAC), mock_config_entry.entry_id
        )
        is device
    )
    assert device.name == NAME
    assert device.manufacturer == MANUFACTURER
    assert device.sw_version == FIRMWARE_VERSION
    assert device.configuration_url is None


async def test_non_static_output_has_unknown_color(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Test effect or mixed-zone state reports ON without a static color."""
    mock_trimlight.return_value.get_device_info.return_value = TrimlightDeviceInfo(
        firmware_version=FIRMWARE_VERSION,
        ic_type=TrimlightICType.RGBW,
    )
    mock_trimlight.return_value.state = TrimlightLightState(is_on=True)

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] is None
    assert state.attributes[ATTR_RGBW_COLOR] is None


async def test_light_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Test authoritative ON and OFF control."""
    await setup_integration(hass, mock_config_entry)
    client = mock_trimlight.return_value

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    client.set_light_state.assert_awaited_once_with(on=True)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert client.set_light_state.await_args_list[-1].kwargs == {"on": False}
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    client.get_light_state.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("ic_type", "service_attribute", "service_color", "expected_changes"),
    [
        pytest.param(
            TrimlightICType.RGB,
            ATTR_RGB_COLOR,
            (1, 2, 3),
            {"red": 1, "green": 2, "blue": 3},
            id="rgb",
        ),
        pytest.param(
            TrimlightICType.RGBW,
            ATTR_RGBW_COLOR,
            (1, 2, 3, 4),
            {"red": 1, "green": 2, "blue": 3, "warm_white": 4},
            id="rgbw",
        ),
        pytest.param(
            TrimlightICType.RGBCW,
            ATTR_RGBWW_COLOR,
            (1, 2, 3, 4, 5),
            {
                "red": 1,
                "green": 2,
                "blue": 3,
                "cold_white": 4,
                "warm_white": 5,
            },
            id="rgbww-cold-warm-order",
        ),
    ],
)
async def test_light_color_control(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
    ic_type: TrimlightICType,
    service_attribute: str,
    service_color: tuple[int, ...],
    expected_changes: dict[str, int],
) -> None:
    """Test brightness and native color control through HA services."""
    mock_trimlight.return_value.get_device_info.return_value = TrimlightDeviceInfo(
        firmware_version=FIRMWARE_VERSION,
        ic_type=ic_type,
    )
    await setup_integration(hass, mock_config_entry)
    client = mock_trimlight.return_value

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_BRIGHTNESS: 24,
            service_attribute: service_color,
        },
        blocking=True,
    )

    client.set_light_state.assert_awaited_once_with(
        on=True,
        brightness=24,
        **expected_changes,
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 24
    assert state.attributes[service_attribute] == service_color


async def test_command_failure_keeps_previous_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Test a failed command does not replace coordinator state."""
    await setup_integration(hass, mock_config_entry)
    client = mock_trimlight.return_value
    client.set_light_state.side_effect = TrimlightConnectionError("request failed")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "command_failed"
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_BRIGHTNESS] is None
    assert not client.state.is_on
    assert client.state.brightness is None
    client.get_light_state.assert_awaited_once_with()


async def test_coordinator_refreshes_external_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator polling publishes externally changed runtime state."""
    await setup_integration(hass, mock_config_entry)
    client = mock_trimlight.return_value
    coordinator = mock_config_entry.runtime_data
    assert coordinator.update_interval == SCAN_INTERVAL

    client.state = TrimlightLightState(
        is_on=True,
        brightness=80,
        red=10,
        green=20,
        blue=30,
        warm_white=40,
        cold_white=50,
        zones=(TrimlightZoneState(255, True, TrimlightOutputMode.STATIC),),
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 80
    assert state.attributes[ATTR_RGB_COLOR] == (10, 20, 30)
    assert client.get_light_state.await_count == 2


async def test_coordinator_marks_entity_unavailable_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Test runtime polling controls entity availability."""
    await setup_integration(hass, mock_config_entry)
    client = mock_trimlight.return_value
    coordinator = mock_config_entry.runtime_data
    client.get_light_state.side_effect = TrimlightConnectionError("request failed")

    await coordinator.async_refresh()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    client.get_light_state.side_effect = None
    client.get_light_state.return_value = client.state
    await coordinator.async_refresh()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
