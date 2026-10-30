from control.linak.desk import Desk
from control.linak.gatt import DPGService, ReferenceInputService, ReferenceOutputService
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


async def test_handshake_and_move_against_simulated_desk(fast_mock):
    client = MockDeskClient("dev")
    await client.connect()
    desk = await Desk.initialise({"base_height": None, "move_command_period": 0.01}, client)
    assert desk.config["base_height"] == 620  # read from the controller

    reported = []
    desk.subscribe(lambda height, speed: reported.append(height.human))
    await desk.start_watching()
    await desk.move_to(Height(1000, desk.config["base_height"], convertFromHuman=True))

    height, _ = await desk.get_height_speed()
    assert height.human == 1000
    assert reported[-1] == 1000  # subscribers follow the move


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
