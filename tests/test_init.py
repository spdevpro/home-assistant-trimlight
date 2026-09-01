"""Tests for Trimlight config entry setup."""

from unittest.mock import MagicMock

from aiotrimlight import TrimlightConnectionError
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trimlight.const import CONF_DID, DOMAIN

from . import setup_integration
from .conftest import (
    MAC,
    SECOND_DID,
    SECOND_HOST,
    SECOND_MAC,
    SECOND_NAME,
    create_mock_trimlight_client,
)


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Test setting up and unloading a Trimlight config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is mock_trimlight.return_value
    assert (
        mock_config_entry.runtime_data.device_info
        is mock_trimlight.return_value.get_device_info.return_value
    )
    assert mock_trimlight.call_count == 1
    assert mock_trimlight.call_args.args[0] == mock_config_entry.data[CONF_HOST]
    assert len(mock_trimlight.call_args.args) == 2
    mock_trimlight.return_value.get_device_info.assert_awaited_once_with()
    mock_trimlight.return_value.get_light_state.assert_awaited_once_with()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    assert entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get("light.test_controller")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_two_controllers_are_independent(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Test each controller has its own entry, device, entity, and client."""
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        title=SECOND_NAME,
        data={CONF_HOST: SECOND_HOST, CONF_DID: SECOND_DID, CONF_MAC: SECOND_MAC},
        unique_id=SECOND_DID,
    )
    first_client = mock_trimlight.return_value
    second_client = create_mock_trimlight_client()
    mock_trimlight.side_effect = [first_client, second_client]

    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, second_entry)

    assert mock_trimlight.call_args_list[0].args[0] == mock_config_entry.data[CONF_HOST]
    assert mock_trimlight.call_args_list[1].args[0] == SECOND_HOST
    assert mock_config_entry.runtime_data.client is first_client
    assert second_entry.runtime_data.client is second_client
    first_devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    second_devices = dr.async_entries_for_config_entry(
        device_registry, second_entry.entry_id
    )
    assert len(first_devices) == 1
    assert first_devices[0].connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}
    assert len(second_devices) == 1
    assert second_devices[0].connections == {(dr.CONNECTION_NETWORK_MAC, SECOND_MAC)}
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 1
    )
    assert (
        len(er.async_entries_for_config_entry(entity_registry, second_entry.entry_id))
        == 1
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    first_state = hass.states.get("light.test_controller")
    second_state = hass.states.get("light.second_controller")
    assert first_state is not None
    assert first_state.state == STATE_UNAVAILABLE
    assert second_state is not None
    assert second_state.state != STATE_UNAVAILABLE
    assert second_entry.state is ConfigEntryState.LOADED


async def test_setup_retries_when_client_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Test setup retry when the controller cannot be queried."""
    mock_trimlight.return_value.get_device_info.side_effect = TrimlightConnectionError(
        "connection failed"
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "setup_failed"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "error": "connection failed"
    }


async def test_setup_retries_when_first_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight: MagicMock,
) -> None:
    """Test setup retry when the initial runtime state cannot be queried."""
    mock_trimlight.return_value.get_light_state.side_effect = TrimlightConnectionError(
        "connection failed"
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
