import asyncio
from unittest.mock import Mock

import pytest
import yaml

import constants
from control import desk_service
from control.desk_service import DeskService, DeskState
from control.linak.util import Height, Speed


@pytest.fixture
def service(monkeypatch, fast_mock):
    """A DeskService for the simulated desk with a stub app. Tests drive it on
    their own event loop rather than its background thread, and main-thread
    hand-offs run inline."""
    monkeypatch.setattr(desk_service.AppHelper, "callAfter", lambda fn, *args: fn(*args))
    monkeypatch.setattr(constants, "CONFIG_UUID", constants.MOCK_ADDRESS)
    monkeypatch.setattr(constants, "RECONNECT_DELAY", 0)
    service = DeskService.alloc().init()
    service.setApp(Mock())
    return service


async def test_connect_reports_height_and_adopts_desk_base(service, monkeypatch):
    monkeypatch.setattr(constants, "MIN_HEIGHT", 60.0)  # differs from the desk's 62cm base
    service._loop = asyncio.get_running_loop()

    await service._connect()

    assert service.is_healthy()
    assert constants.MIN_HEIGHT == 62.0
    service._app.deskHeightChanged.assert_called_with(75, False)


async def test_unreachable_desk_gives_up_and_schedules_a_retry(service, monkeypatch):
    attempts = []

    class UnreachableClient:
        def __init__(self, address, **kwargs):
            pass

        async def connect(self, **kwargs):
            attempts.append(self)
            raise TimeoutError

        async def disconnect(self):
            pass

    monkeypatch.setattr(desk_service, "BleakClient", UnreachableClient)
    monkeypatch.setattr(constants, "CONFIG_UUID", "AA:BB:CC:DD:EE:FF")
    service._loop = asyncio.get_running_loop()

    await service._connect()

    assert len(attempts) == constants.MAX_RECONNECT_FAILURES
    assert service.is_dead()
    assert service._retry_handle is not None


@pytest.mark.parametrize("auto_connect, expected", [
    (True, DeskState.CONNECTED),
    (False, DeskState.IDLE),
])
async def test_dropped_link_is_restored_only_with_auto_connect(
        service, monkeypatch, auto_connect, expected):
    service._loop = asyncio.get_running_loop()
    await service._connect()
    monkeypatch.setattr(constants, "CONFIG_AUTO_CONNECT", auto_connect)

    service._on_ble_disconnected(service._client)  # bleak: the desk dropped the link

    assert not service.is_healthy()
    async with asyncio.timeout(1):
        while service._state != expected:
            await asyncio.sleep(0.01)


async def test_user_disconnect_sticks(service):
    service._loop = asyncio.get_running_loop()
    await service._connect()
    client = service._client

    service.disconnect()
    await asyncio.sleep(0.1)  # let the disconnect and bleak's callback run
    assert not client.is_connected
    assert service.is_idle()

    service.systemDidWake_(None)
    assert service.is_idle()


def test_taller_desk_raises_and_persists_max_height(service, config_file):
    top = Height(6700, base_height=620)  # 1290mm, above the 1270mm default

    service._push_height(top, Speed(350))
    assert constants.MAX_HEIGHT == 127.0  # only adopted once the desk stops
    service._push_height(top, Speed(0))

    assert constants.MAX_HEIGHT == 129.0
    assert yaml.safe_load(config_file.read_text())["max_height"] == 1290
    service._app.deskLimitsChanged.assert_called_once()
