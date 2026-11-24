import pytest

from control.linak.desk import Desk
from control.linak.gatt import (
    DPGService, MAX_POSITION, ReferenceInputService, ReferenceOutputService,
)
from control.linak.mock import MockDeskClient
from control.linak.util import Height

DPG = DPGService.DPG


def test_wire_format_matches_linak_protocol():
    # Reference output: little-endian height in 10ths of a mm above the desk's
    # lowest position, then a signed speed (negative while moving down)
    height, speed = ReferenceOutputService.decode_height_speed(bytearray.fromhex("d80ea2fe"))
    height.base_height = 620
    assert (height.human, speed.value) == (1000, -350)

    # Reference input encodes a target height the same way
    target = Height(1000, base_height=620, convertFromHuman=True)
    assert ReferenceInputService.encode_height(target.value) == bytearray.fromhex("d80e")


def test_positions_beyond_the_desks_travel_never_cross_the_wire():
    height, _ = ReferenceOutputService.decode_height_speed(bytearray.fromhex("9eff0000"))
    assert height is None

    assert ReferenceInputService.encode_height(MAX_POSITION) == bytearray.fromhex("401f")
    for target in (-1, MAX_POSITION + 1, 60150):
        with pytest.raises(ValueError):
            ReferenceInputService.encode_height(target)


async def simulated_desk():
    client = MockDeskClient("dev")
    await client.connect()
    return await Desk.initialise({"base_height": None, "move_command_period": 0.01}, client)


async def test_handshake_and_move_against_simulated_desk(fast_mock):
    client = MockDeskClient("dev")
    await client.connect()
    desk = await Desk.initialise({"base_height": None, "move_command_period": 0.01}, client)
    assert desk.config["base_height"] == 620  # read from the controller

    reported = []
    desk.subscribe(lambda height, speed: reported.append(height.human))
    await desk.start_watching()
    assert await desk.move_to(Height(1000, desk.config["base_height"], convertFromHuman=True))

    height, _ = await desk.get_height_speed()
    assert height.human == 1000
    assert reported[-1] == 1000  # subscribers follow the move


async def test_desk_that_doesnt_know_its_position_is_not_moved(fast_mock, monkeypatch):
    monkeypatch.setattr(MockDeskClient, "_height", -98)  # reports 9e ff
    desk = await simulated_desk()

    assert await desk.move_to(Height(1000, desk.config["base_height"], convertFromHuman=True)) is False
    assert MockDeskClient._height == -98


async def test_move_stops_a_desk_heading_away_from_the_target(fast_mock, monkeypatch):
    monkeypatch.setattr(
        ReferenceInputService, "encode_height", lambda height: bytearray.fromhex("f6ea")
    )
    desk = await simulated_desk()

    assert await desk.move_to(Height(1100, desk.config["base_height"], convertFromHuman=True)) is False
    _, speed = await desk.get_height_speed()
    assert speed.value == 0  # stopped


async def test_handshake_adapts_to_controller_quirks(monkeypatch):
    writes = []

    async def dpg_command(client, command, data=None):
        if data is not None:
            writes.append((command, bytes(data)))
        return {
            DPG.CMD_GET_CAPABILITIES: bytearray([0, 0]),
            DPG.CMD_USER_ID: bytearray([0, 7]),
            DPG.CMD_BASE_OFFSET: bytearray(),  # acknowledged without a value
        }[command]

    monkeypatch.setattr(DPGService, "dpg_command", dpg_command)
    desk = await Desk.initialise({"base_height": None}, client=None)

    # DPG1C controllers need the first user id byte set to 1
    assert writes == [(DPG.CMD_USER_ID, bytes([1, 7]))]
    # A missing base height falls back to a typical frame instead of crashing
    assert desk.config["base_height"] == 620
    assert desk.base_height_estimated
