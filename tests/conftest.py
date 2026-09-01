"""Fixtures for the Trimlight integration tests."""

from collections.abc import Generator
from dataclasses import replace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiotrimlight import TrimlightDeviceInfo, TrimlightICType, TrimlightLightState
from homeassistant.const import CONF_HOST, CONF_MAC
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trimlight.const import CONF_DID, DOMAIN

HOST = "192.0.2.10"
DID = "544c0003a1b2c3d4e5f6"
MAC = "a1:b2:c3:d4:e5:f6"
NAME = "Test controller"
SECOND_HOST = "192.0.2.11"
SECOND_DID = "544c0003010203040506"
SECOND_MAC = "01:02:03:04:05:06"
SECOND_NAME = "Second controller"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations for every test."""


def create_mock_trimlight_client() -> MagicMock:
    """Create a mocked Trimlight client."""
    client = MagicMock()
    client.state = TrimlightLightState(is_on=False)
    client.get_device_info = AsyncMock(
        return_value=TrimlightDeviceInfo(
            firmware_version="1.0.38.1.0.13r",
            ic_type=TrimlightICType.RGB,
        )
    )

    async def async_get_light_state() -> TrimlightLightState:
        return cast(TrimlightLightState, client.state)

    async def async_set_light_state(
        **changes: bool | int,
    ) -> TrimlightLightState:
        state_changes = dict(changes)
        if "on" in state_changes:
            state_changes["is_on"] = state_changes.pop("on")
        client.state = replace(client.state, **state_changes)
        return cast(TrimlightLightState, client.state)

    client.get_light_state = AsyncMock(side_effect=async_get_light_state)
    client.set_light_state = AsyncMock(side_effect=async_set_light_state)
    return client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a Trimlight config entry."""
    with patch(
        "custom_components.trimlight.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_trimlight_config_flow() -> Generator[MagicMock]:
    """Mock the Trimlight client used by the config flow."""
    with patch(
        "custom_components.trimlight.config_flow.TrimlightClient",
        autospec=True,
    ) as client_class:
        client = client_class.return_value
        client.get_device_info = AsyncMock(
            return_value=TrimlightDeviceInfo(
                firmware_version="1.0.38.1.0.13r",
                ic_type=TrimlightICType.RGB,
            )
        )
        yield client_class


@pytest.fixture
def mock_trimlight() -> Generator[MagicMock]:
    """Mock the Trimlight client used during config entry setup."""
    with patch(
        "custom_components.trimlight.TrimlightClient",
        autospec=True,
    ) as client_class:
        client_class.return_value = create_mock_trimlight_client()
        yield client_class


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked Trimlight config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=NAME,
        data={CONF_HOST: HOST, CONF_DID: DID, CONF_MAC: MAC},
        unique_id=DID,
    )
