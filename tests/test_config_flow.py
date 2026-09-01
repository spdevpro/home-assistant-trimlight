"""Tests for the Trimlight config flow."""

from ipaddress import IPv4Address
from unittest.mock import MagicMock

import pytest
from aiotrimlight import (
    TrimlightCommandError,
    TrimlightConnectionError,
    TrimlightHTTPError,
    TrimlightProtocolError,
    TrimlightUnsupportedICError,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trimlight.const import CONF_DID, DOMAIN

from . import setup_integration
from .conftest import (
    DID,
    HOST,
    MAC,
    NAME,
    SECOND_DID,
    SECOND_HOST,
    SECOND_MAC,
    SECOND_NAME,
    create_mock_trimlight_client,
)


def zeroconf_info(
    *,
    host: str = HOST,
    name: str = NAME,
    properties: dict[str, str] | None = None,
    port: int = 8586,
) -> ZeroconfServiceInfo:
    """Return Trimlight Zeroconf discovery information."""
    ip_address = IPv4Address(host)
    return ZeroconfServiceInfo(
        ip_address=ip_address,
        ip_addresses=[ip_address],
        port=port,
        hostname="Test-controller.local.",
        type="_tlight._tcp.local.",
        name="Test-controller._tlight._tcp.local.",
        properties=(
            properties
            if properties is not None
            else {"did": DID, "name": name, "mfr": "invalid"}
        ),
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow(
    hass: HomeAssistant, mock_trimlight_config_flow: MagicMock
) -> None:
    """Test configuring a discovered Trimlight controller."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "host": HOST,
        "name": NAME,
    }
    mock_trimlight_config_flow.assert_called_once()
    assert mock_trimlight_config_flow.call_args.args[0] == HOST
    assert len(mock_trimlight_config_flow.call_args.args) == 2

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_HOST: HOST, CONF_DID: DID, CONF_MAC: MAC}
    assert result["result"].unique_id == DID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flows_create_independent_entries(
    hass: HomeAssistant, mock_trimlight_config_flow: MagicMock
) -> None:
    """Test separate discovered DIDs create separate config entries."""
    first_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(),
    )
    assert first_result["type"] is FlowResultType.FORM
    first_result = await hass.config_entries.flow.async_configure(
        first_result["flow_id"], {}
    )

    second_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(
            host=SECOND_HOST,
            properties={"did": SECOND_DID, "name": SECOND_NAME},
        ),
    )
    assert second_result["type"] is FlowResultType.FORM
    second_result = await hass.config_entries.flow.async_configure(
        second_result["flow_id"], {}
    )

    assert first_result["type"] is FlowResultType.CREATE_ENTRY
    assert second_result["type"] is FlowResultType.CREATE_ENTRY
    entries = hass.config_entries.async_entries(DOMAIN)
    assert {entry.unique_id for entry in entries} == {DID, SECOND_DID}
    assert {entry.data[CONF_MAC] for entry in entries} == {MAC, SECOND_MAC}
    assert mock_trimlight_config_flow.call_count == 2


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_uses_service_name_fallback(
    hass: HomeAssistant, mock_trimlight_config_flow: MagicMock
) -> None:
    """Test using the service instance when the TXT name is absent."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(properties={"did": DID}),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] is not None
    assert result["description_placeholders"]["name"] == "Test-controller"


@pytest.mark.parametrize(
    "properties",
    [
        pytest.param({"mfr": "ignored"}, id="manufacturer-data-only"),
        pytest.param({"did": "invalid"}, id="invalid-did"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry", "mock_trimlight_config_flow")
async def test_zeroconf_flow_rejects_invalid_discovery_identity(
    hass: HomeAssistant, properties: dict[str, str]
) -> None:
    """Test rejecting invalid discovery identities."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(properties=properties),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_zeroconf_flow_updates_existing_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_trimlight_config_flow: MagicMock,
    mock_trimlight: MagicMock,
) -> None:
    """Test rediscovery reloads only the matching DID with its new host."""
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        title=SECOND_NAME,
        data={CONF_HOST: SECOND_HOST, CONF_DID: SECOND_DID, CONF_MAC: SECOND_MAC},
        unique_id=SECOND_DID,
    )
    first_client = mock_trimlight.return_value
    second_client = create_mock_trimlight_client()
    replacement_client = create_mock_trimlight_client()
    mock_trimlight.side_effect = [first_client, second_client, replacement_client]
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, second_entry)
    old_coordinator = mock_config_entry.runtime_data
    other_coordinator = second_entry.runtime_data
    mock_trimlight.reset_mock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(host="192.0.2.16"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.0.2.16"
    assert mock_config_entry.data[CONF_MAC] == MAC
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data is not old_coordinator
    assert mock_config_entry.runtime_data.client is replacement_client
    assert second_entry.runtime_data is other_coordinator
    assert second_entry.runtime_data.client is second_client
    mock_trimlight.assert_called_once()
    assert mock_trimlight.call_args.args[0] == "192.0.2.16"
    mock_trimlight_config_flow.assert_not_called()


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(
            TrimlightConnectionError("connection failed"),
            "cannot_connect",
            id="connection",
        ),
        pytest.param(
            TrimlightHTTPError(503),
            "cannot_connect",
            id="http",
        ),
        pytest.param(
            TrimlightCommandError(201, "MCU timeout"),
            "invalid_response",
            id="device-error",
        ),
        pytest.param(
            TrimlightProtocolError("invalid response"),
            "invalid_response",
            id="protocol",
        ),
        pytest.param(
            TrimlightUnsupportedICError(3),
            "unsupported_device",
            id="unsupported-ic",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_trimlight_config_flow: MagicMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test errors while probing a discovered controller."""
    mock_trimlight_config_flow.return_value.get_device_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_unexpected_error(
    hass: HomeAssistant,
    mock_trimlight_config_flow: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected probe error is logged and safely aborted."""
    mock_trimlight_config_flow.return_value.get_device_info.side_effect = RuntimeError(
        "unexpected failure"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"
    assert "Unexpected exception while probing Trimlight controller" in caplog.text


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_recovers_after_error(
    hass: HomeAssistant,
    mock_trimlight_config_flow: MagicMock,
) -> None:
    """Test a later discovery can complete after a connection error."""
    client = mock_trimlight_config_flow.return_value
    device_info = client.get_device_info.return_value
    client.get_device_info.side_effect = [
        TrimlightConnectionError("connection failed"),
        device_info,
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_info(),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {CONF_HOST: HOST, CONF_DID: DID, CONF_MAC: MAC}
    assert result["result"].unique_id == DID
    assert client.get_device_info.await_count == 2


async def test_user_flow(
    hass: HomeAssistant, mock_trimlight_config_flow: MagicMock
) -> None:
    """Test manual setup points the user to automatic discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"
    mock_trimlight_config_flow.assert_not_called()
