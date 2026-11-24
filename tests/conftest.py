"""
Shared test setup. Importing `constants` reads the settings in
~/Library/Application Support/DeskController and creates a log file, so HOME
is pointed at a throwaway directory first. Tests never use the real config or
Bluetooth.
"""
import asyncio
import inspect
import os
import tempfile
from pathlib import Path

_home = tempfile.TemporaryDirectory(prefix="deskcontroller-tests-")
os.environ["HOME"] = _home.name

import pytest
import yaml

import constants
from control.linak import mock


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Runs `async def` tests in a fresh event loop."""
    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None
    params = inspect.signature(pyfuncitem.obj).parameters
    asyncio.run(pyfuncitem.obj(**{name: pyfuncitem.funcargs[name] for name in params}))
    return True


@pytest.fixture(autouse=True)
def desk_file(tmp_path, monkeypatch):
    """Per test, a config.yaml naming the simulated desk as the current one
    and that desk's settings file with the defaults, which is returned.
    Restores the runtime settings that the code under test rewrites on
    `constants`."""
    config = tmp_path / "config.yaml"
    monkeypatch.setattr(constants, "CONFIG_FILE_PATH", str(config))
    monkeypatch.setattr(constants, "DESKS_PATH", str(tmp_path / "desks"))
    for name in (
        "CONFIG_UUID", "CONFIG_AUTO_CONNECT", "CONFIG_SHOW_HEIGHT",
        "CONFIG_PRESET_1", "CONFIG_PRESET_1_NAME",
        "CONFIG_PRESET_2", "CONFIG_PRESET_2_NAME", "CONFIG_BASE_HEIGHT",
        "CONNECTION_TIMEOUT", "MOVE_COMMAND_PERIOD", "MIN_HEIGHT", "MAX_HEIGHT",
    ):
        monkeypatch.setattr(constants, name, getattr(constants, name))

    path = Path(constants.desk_file(constants.MOCK_ADDRESS))
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(constants.DEFAULT_DESK_CONFIG))
    config.write_text(yaml.safe_dump({"desk": constants.MOCK_ADDRESS}))
    constants.load_desk(constants.MOCK_ADDRESS)
    return path


@pytest.fixture
def fast_mock(monkeypatch):
    """Removes the simulated desk's delays and puts it back at its start height."""
    monkeypatch.setattr(mock, "CONNECT_DELAY", 0)
    monkeypatch.setattr(mock, "RESPONSE_DELAY", 0)
    monkeypatch.setattr(mock, "TICK", 0.001)
    monkeypatch.setattr(
        mock.MockDeskClient, "_height", (mock.START_HEIGHT_MM - mock.BASE_HEIGHT_MM) * 10
    )
