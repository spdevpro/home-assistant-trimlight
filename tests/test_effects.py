"""Saved scene behavior using synthetic library models, never device captures."""

import asyncio
from dataclasses import replace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from aiotrimlight import (
    TrimlightCommandError,
    TrimlightConnectionError,
    TrimlightDeviceInfo,
    TrimlightEffect,
    TrimlightICType,
    TrimlightLightState,
)
from aiotrimlight import (
    TrimlightOutputMode as Mode,
)
from aiotrimlight import (
    TrimlightZoneState as Zone,
)
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.light import ColorMode, LightEntityFeature
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from . import setup_integration
from .conftest import (
    SECOND_DID,
    SECOND_HOST,
    SECOND_MAC,
    SECOND_NAME,
    create_mock_trimlight_client,
)
from .test_light import ENTITY_ID

STATIC = TrimlightLightState(
    is_on=True,
    brightness=20,
    red=10,
    green=20,
    blue=30,
    warm_white=40,
    cold_white=50,
    scene_id=1,
    zones=(Zone(255, True, Mode.STATIC),),
)
SCENE = replace(STATIC, zones=(Zone(1, True, Mode.EFFECT),))
LABEL = "Test [ID 1]"


@pytest.fixture
def scene_client(mock_trimlight: MagicMock) -> MagicMock:
    """Mock the public library contract, including authoritative readback."""
    client = cast(MagicMock, mock_trimlight.return_value)
    client.state = STATIC
    client.get_effect_list.return_value = (TrimlightEffect(1, "Test"),)

    async def play(effect_id: int) -> TrimlightLightState:
        client.state = replace(SCENE, is_on=client.state.is_on, scene_id=effect_id)
        return cast(TrimlightLightState, client.state)

    client.play_effect.side_effect = play
    return client


def entity_state(hass: HomeAssistant) -> State:
    """Get the light through the HA state machine."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    return state


async def turn_on(hass: HomeAssistant, **data: Any) -> None:
    """Exercise HA's native light service validation and parameter handling."""
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": ENTITY_ID, **data}, blocking=True
    )


@pytest.mark.parametrize(
    ("runtime", "effect", "color_mode"),
    [
        (SCENE, LABEL, ColorMode.ONOFF),
        (STATIC, "off", ColorMode.RGB),
        (replace(SCENE, is_on=False), None, None),
        (replace(SCENE, scene_id=None), None, ColorMode.UNKNOWN),
        (replace(SCENE, scene_id=120), None, ColorMode.UNKNOWN),
        (replace(SCENE, zones=()), None, ColorMode.UNKNOWN),
        (
            replace(SCENE, zones=(Zone(1, False, Mode.EFFECT),)),
            "off",
            ColorMode.UNKNOWN,
        ),
        (replace(SCENE, zones=(Zone(1, True, Mode.NONE),)), "off", ColorMode.UNKNOWN),
        (
            replace(
                SCENE, zones=(Zone(1, True, Mode.EFFECT), Zone(2, True, Mode.STATIC))
            ),
            None,
            ColorMode.UNKNOWN,
        ),
        (
            replace(
                SCENE, zones=(Zone(1, True, Mode.EFFECT), Zone(2, True, Mode.NONE))
            ),
            None,
            ColorMode.UNKNOWN,
        ),
        (
            replace(
                SCENE, zones=(Zone(1, True, Mode.EFFECT), Zone(2, False, Mode.STATIC))
            ),
            LABEL,
            ColorMode.ONOFF,
        ),
        (
            replace(
                SCENE, zones=(Zone(1, True, Mode.EFFECT), Zone(4, True, Mode.EFFECT))
            ),
            LABEL,
            ColorMode.ONOFF,
        ),
    ],
)
async def test_scene_display(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    runtime: TrimlightLightState,
    effect: str | None,
    color_mode: ColorMode | None,
) -> None:
    """Association requires power, uniform effect output and a known library ID."""
    scene_client.state = runtime
    await setup_integration(hass, mock_config_entry)
    state = entity_state(hass)
    assert state.attributes["effect"] == effect
    assert state.attributes["color_mode"] == color_mode
    assert state.attributes["supported_color_modes"] == [ColorMode.RGB]
    assert state.attributes["effect_list"] == [LABEL]
    if color_mode != ColorMode.RGB:
        assert state.attributes["brightness"] is None
        assert state.attributes["rgb_color"] is None


async def test_unique_options_and_empty_library(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
) -> None:
    """Keep duplicate and whitespace names, and accept an empty library."""
    scene_client.get_effect_list.return_value = (
        TrimlightEffect(1, "Test"),
        TrimlightEffect(2, "Test"),
        TrimlightEffect(3, " \t"),
        TrimlightEffect(4, " Test "),
    )
    with patch(
        "custom_components.trimlight.coordinator.monotonic", return_value=0
    ) as clock:
        await setup_integration(hass, mock_config_entry)
        assert entity_state(hass).attributes["effect_list"] == [
            LABEL,
            "Test [ID 2]",
            "Scene [ID 3]",
            " Test  [ID 4]",
        ]
        scene_client.get_effect_list.return_value = ()
        clock.return_value = 300
        await mock_config_entry.runtime_data.async_refresh()
    assert entity_state(hass).attributes["effect_list"] == []
    assert (
        entity_state(hass).attributes["supported_features"] == LightEntityFeature.EFFECT
    )
    await turn_on(hass, brightness=40)
    assert entity_state(hass).attributes["brightness"] == 40


@pytest.mark.parametrize(
    "extra", [{}, {"brightness": 40}, {"rgb_color": (1, 2, 3), "brightness": 40}]
)
async def test_play_from_off_scene_priority(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    extra: dict[str, Any],
) -> None:
    """Play, then explicitly switch on; never apply accompanying static parameters."""
    scene_client.state = replace(STATIC, is_on=False)
    await setup_integration(hass, mock_config_entry)
    await turn_on(hass, effect=LABEL, **extra)
    scene_client.play_effect.assert_awaited_once_with(1)
    scene_client.set_light_state.assert_awaited_once_with(on=True)
    assert entity_state(hass).state == STATE_ON
    assert entity_state(hass).attributes["effect"] == LABEL


@pytest.mark.parametrize("stage", ["play_effect", "set_light_state"])
async def test_play_failure_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    stage: str,
) -> None:
    """Failure (including library readback failure) never publishes assumed success."""
    await setup_integration(hass, mock_config_entry)
    command = getattr(scene_client, stage)
    original = command.side_effect
    command.side_effect = TrimlightConnectionError("readback failed")
    with pytest.raises(HomeAssistantError) as err:
        await turn_on(hass, effect=LABEL)
    assert err.value.translation_key == "command_failed"
    assert entity_state(hass).attributes["effect"] == "off"
    if stage == "play_effect":
        scene_client.set_light_state.assert_not_awaited()
    command.side_effect = original
    await turn_on(hass, effect=LABEL)
    assert entity_state(hass).attributes["effect"] == LABEL


@pytest.mark.parametrize(
    "runtime",
    [
        SCENE,
        replace(SCENE, is_on=False),
        replace(SCENE, scene_id=120),
        replace(SCENE, zones=()),
    ],
)
async def test_brightness_uses_fresh_output_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    runtime: TrimlightLightState,
) -> None:
    """An App change since the last poll cannot turn a scene into static output."""
    await setup_integration(hass, mock_config_entry)
    scene_client.state = runtime
    with pytest.raises(ServiceValidationError) as err:
        await turn_on(hass, brightness=40)
    assert err.value.translation_key == "scene_brightness_unsupported"
    scene_client.set_light_state.assert_not_awaited()
    scene_client.state = STATIC
    await turn_on(hass, brightness=40)
    assert entity_state(hass).attributes["brightness"] == 40


async def test_explicit_color_and_zero_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
) -> None:
    """Color intentionally returns to static; native brightness zero switches off."""
    scene_client.state = SCENE
    await setup_integration(hass, mock_config_entry)
    await turn_on(hass, rgb_color=(1, 2, 3), brightness=60)
    assert entity_state(hass).attributes["effect"] == "off"
    assert entity_state(hass).attributes["rgb_color"] == (1, 2, 3)
    await turn_on(hass, effect=LABEL)
    await turn_on(hass, brightness=0)
    assert scene_client.set_light_state.await_args.kwargs == {"on": False}
    assert scene_client.state.zones == SCENE.zones


async def test_external_edits_and_list_only_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
) -> None:
    """Preview/overwrite keep A; save-as follows B; rename/deletion update alone."""
    scene_client.state = SCENE
    with patch(
        "custom_components.trimlight.coordinator.monotonic", return_value=0
    ) as clock:
        await setup_integration(hass, mock_config_entry)
        coordinator = mock_config_entry.runtime_data
        for tick in (30, 60):
            clock.return_value = tick
            scene_client.state = replace(SCENE, brightness=tick)
            await coordinator.async_refresh()
            assert entity_state(hass).attributes["effect"] == LABEL
        scene_client.get_effect_list.assert_awaited_once()
        clock.return_value = 90
        scene_client.state = replace(SCENE, scene_id=2)
        scene_client.get_effect_list.return_value = (
            TrimlightEffect(1, "Test"),
            TrimlightEffect(2, "B"),
        )
        await coordinator.async_refresh()
        assert entity_state(hass).attributes["effect"] == "B [ID 2]"
        clock.return_value = 390
        scene_client.get_effect_list.return_value = (TrimlightEffect(2, "Renamed"),)
        await coordinator.async_refresh()
        assert entity_state(hass).attributes["effect"] == "Renamed [ID 2]"
        clock.return_value = 690
        scene_client.get_effect_list.return_value = ()
        await coordinator.async_refresh()
        assert entity_state(hass).attributes["effect"] is None
        assert entity_state(hass).attributes["effect_list"] == []
        assert coordinator.data.state.scene_id == 2
        for tick in (691, 719):
            clock.return_value = tick
            await coordinator.async_refresh()
        assert scene_client.get_effect_list.await_count == 4
        clock.return_value = 720
        await coordinator.async_refresh()
        assert scene_client.get_effect_list.await_count == 5


@pytest.mark.parametrize("initial", [True, False])
async def test_optional_list_failure_throttling_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    initial: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Transient list errors neither empty a cache nor make runtime unavailable."""
    with patch(
        "custom_components.trimlight.coordinator.monotonic", return_value=0
    ) as clock:
        if initial:
            scene_client.get_effect_list.side_effect = TrimlightConnectionError(
                "list offline"
            )
        await setup_integration(hass, mock_config_entry)
        coordinator = mock_config_entry.runtime_data
        scene_client.get_effect_list.side_effect = TrimlightConnectionError(
            "list offline"
        )
        clock.return_value = 300
        await coordinator.async_refresh()
        assert entity_state(hass).state == STATE_ON
        assert entity_state(hass).attributes.get("effect_list") == (
            None if initial else [LABEL]
        )
        calls = scene_client.get_effect_list.await_count
        clock.return_value = 301
        await coordinator.async_refresh()
        assert scene_client.get_effect_list.await_count == calls
        assert caplog.text.count("Unable to refresh Trimlight scene list") == 1
        scene_client.get_effect_list.side_effect = None
        clock.return_value = 330
        await coordinator.async_refresh()
        assert entity_state(hass).attributes["effect_list"] == [LABEL]
        assert "Trimlight scene list refresh recovered" in caplog.text


@pytest.mark.parametrize("code", [101, 102])
async def test_unsupported_is_not_transient_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    code: int,
) -> None:
    """Only explicit unsupported disables capabilities until reload."""
    scene_client.get_effect_list.side_effect = TrimlightCommandError(
        code, "device error"
    )
    with patch(
        "custom_components.trimlight.coordinator.monotonic", return_value=0
    ) as clock:
        await setup_integration(hass, mock_config_entry)
        clock.return_value = 300
        await mock_config_entry.runtime_data.async_refresh()
        assert scene_client.get_effect_list.await_count == (1 if code == 101 else 2)
        assert entity_state(hass).state == STATE_ON
        assert entity_state(hass).attributes["supported_features"] == 0
        if code == 101:
            with pytest.raises(ServiceValidationError) as err:
                await mock_config_entry.runtime_data.async_play_effect(LABEL)
            assert err.value.translation_key == "invalid_effect"
        scene_client.get_effect_list.side_effect = None
        assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert entity_state(hass).attributes["effect_list"] == [LABEL]


@pytest.mark.parametrize("option", ["Test", "Unknown [ID 1]", "off"])
async def test_reject_arbitrary_labels(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    option: str,
) -> None:
    """Never parse arbitrary user strings into library IDs."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await turn_on(hass, effect=option)
    assert err.value.translation_key == "invalid_effect"
    scene_client.play_effect.assert_not_awaited()


@pytest.mark.parametrize("result", ["success", "renamed", "failure", "unsupported"])
async def test_stale_list_before_play(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    result: str,
) -> None:
    """A stale cache must be refreshed successfully and its label revalidated."""
    with patch(
        "custom_components.trimlight.coordinator.monotonic", return_value=0
    ) as clock:
        await setup_integration(hass, mock_config_entry)
        clock.return_value = 301
        if result == "renamed":
            scene_client.get_effect_list.return_value = (TrimlightEffect(1, "Changed"),)
        elif result == "failure":
            scene_client.get_effect_list.side_effect = TrimlightConnectionError(
                "list offline"
            )
        elif result == "unsupported":
            scene_client.get_effect_list.side_effect = TrimlightCommandError(101, None)
        if result == "success":
            await turn_on(hass, effect=LABEL)
            assert entity_state(hass).attributes["effect"] == LABEL
        else:
            with pytest.raises(ServiceValidationError) as err:
                await turn_on(hass, effect=LABEL)
            assert err.value.translation_key == (
                "invalid_effect" if result == "renamed" else "effect_list_unavailable"
            )
            scene_client.play_effect.assert_not_awaited()
            if result == "failure":
                with pytest.raises(ServiceValidationError):
                    await turn_on(hass, effect=LABEL)
        assert scene_client.get_effect_list.await_count == 2


@pytest.mark.parametrize("cancel", [False, True])
async def test_play_serializes_poll_and_control_and_releases_lock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    cancel: bool,
) -> None:
    """No poll/control can split playback and switch readback; cancellation releases."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []

    async def play(effect_id: int) -> TrimlightLightState:
        calls.append("play")
        started.set()
        await release.wait()
        return SCENE

    async def read() -> TrimlightLightState:
        calls.append("poll")
        return STATIC

    async def switch(**changes: bool | int) -> TrimlightLightState:
        calls.append("on" if changes["on"] else "off")
        return SCENE

    scene_client.play_effect.side_effect = play
    scene_client.get_light_state.side_effect = read
    scene_client.set_light_state.side_effect = switch
    playback = asyncio.create_task(coordinator.async_play_effect(LABEL))
    await started.wait()
    poll = asyncio.create_task(coordinator.async_refresh())
    control = asyncio.create_task(coordinator.async_set_state(on=False))
    await asyncio.sleep(0)
    assert calls == ["play"]
    if cancel:
        playback.cancel()
        with pytest.raises(asyncio.CancelledError):
            await playback
    else:
        release.set()
        await playback
    await asyncio.gather(poll, control)
    assert calls == (
        ["play", "poll", "off"] if cancel else ["play", "on", "poll", "off"]
    )


async def test_old_firmware_play_does_not_assume_scene_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
) -> None:
    """Synthetic old firmware supports commands but omits the association field."""
    await setup_integration(hass, mock_config_entry)
    scene_client.set_light_state.side_effect = None
    scene_client.set_light_state.return_value = replace(SCENE, scene_id=None)
    await turn_on(hass, effect=LABEL)
    assert entity_state(hass).attributes["effect"] is None
    assert entity_state(hass).attributes["color_mode"] == ColorMode.UNKNOWN


async def test_real_poll_schedule_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The existing HA timer drives both polls; unloading removes subscriptions."""
    with patch(
        "custom_components.trimlight.coordinator.monotonic", return_value=0
    ) as clock:
        await setup_integration(hass, mock_config_entry)
        scene_client.get_effect_list.return_value = (TrimlightEffect(1, "Renamed"),)
        for tick in range(30, 301, 30):
            clock.return_value = tick
            freezer.tick(30)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
        assert scene_client.get_light_state.await_count == 11
        assert scene_client.get_effect_list.await_count == 2
        assert entity_state(hass).attributes["effect_list"] == ["Renamed [ID 1]"]
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        freezer.tick(300)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert scene_client.get_light_state.await_count == 11


@pytest.mark.parametrize("ic_type", list(TrimlightICType))
async def test_static_scene_static_roundtrip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    ic_type: TrimlightICType,
) -> None:
    """All IC modes hide static attributes during scenes and restore on readback."""
    scene_client.get_device_info.return_value = TrimlightDeviceInfo("test", ic_type)
    await setup_integration(hass, mock_config_entry)
    before = dict(entity_state(hass).attributes)
    await turn_on(hass, effect=LABEL)
    assert entity_state(hass).attributes["brightness"] is None
    scene_client.state = STATIC
    await mock_config_entry.runtime_data.async_refresh()
    assert dict(entity_state(hass).attributes) == before


async def test_brightness_readback_failure_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
) -> None:
    """A failed safety read sends no static command and releases the lock."""
    await setup_integration(hass, mock_config_entry)
    original = scene_client.get_light_state.side_effect
    scene_client.get_light_state.side_effect = TrimlightConnectionError("offline")
    with pytest.raises(HomeAssistantError) as err:
        await turn_on(hass, brightness=40)
    assert err.value.translation_key == "command_failed"
    scene_client.set_light_state.assert_not_awaited()
    scene_client.get_light_state.side_effect = original
    await turn_on(hass, brightness=40)
    assert entity_state(hass).attributes["brightness"] == 40


@pytest.mark.parametrize("stage", ["get_effect_list", "set_light_state"])
async def test_cancel_list_or_final_readback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    stage: str,
) -> None:
    """Cancel at either awaited boundary without a false success or stuck lock."""
    with patch(
        "custom_components.trimlight.coordinator.monotonic", return_value=0
    ) as clock:
        await setup_integration(hass, mock_config_entry)
        coordinator = mock_config_entry.runtime_data
        started = asyncio.Event()

        async def blocked(*args: Any, **kwargs: Any) -> None:
            started.set()
            await asyncio.Event().wait()

        command = getattr(scene_client, stage)
        original = command.side_effect
        command.side_effect = blocked
        clock.return_value = 301
        playback = asyncio.create_task(coordinator.async_play_effect(LABEL))
        await started.wait()
        playback.cancel()
        with pytest.raises(asyncio.CancelledError):
            await playback
        assert entity_state(hass).attributes["effect"] == "off"
        command.side_effect = original
        clock.return_value = 331
        await coordinator.async_play_effect(LABEL)
        assert entity_state(hass).attributes["effect"] == LABEL


async def test_each_controller_has_its_own_scene_cache_and_lock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    scene_client: MagicMock,
    mock_trimlight: MagicMock,
) -> None:
    """A blocked controller does not block another controller's coordinator."""
    second = create_mock_trimlight_client()
    second.get_effect_list.return_value = (TrimlightEffect(2, "Second"),)
    mock_trimlight.side_effect = [scene_client, second]
    second_entry = MockConfigEntry(
        domain="trimlight",
        title=SECOND_NAME,
        data={"host": SECOND_HOST, "did": SECOND_DID, "mac": SECOND_MAC},
        unique_id=SECOND_DID,
    )
    await setup_integration(hass, mock_config_entry)
    await setup_integration(hass, second_entry)
    started = asyncio.Event()
    release = asyncio.Event()

    async def play(effect_id: int) -> TrimlightLightState:
        started.set()
        await release.wait()
        return SCENE

    scene_client.play_effect.side_effect = play
    playback = asyncio.create_task(
        mock_config_entry.runtime_data.async_play_effect(LABEL)
    )
    await started.wait()
    await second_entry.runtime_data.async_set_state(on=True)
    assert not playback.done()
    second_state = hass.states.get("light.second_controller")
    assert second_state is not None
    assert second_state.attributes["effect_list"] == ["Second [ID 2]"]
    assert entity_state(hass).attributes["effect_list"] == [LABEL]
    release.set()
    await playback
