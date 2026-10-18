"""
Simulated Linak desk for development, used when the desk address is set to
constants.MOCK_ADDRESS. MockDeskClient implements the subset of BleakClient.
"""
import asyncio
import struct

from bleak.exc import BleakError

from .gatt import (
    DPGService,
    ControlService,
    ReferenceInputService,
    ReferenceOutputService,
)
from .util import logger


BASE_HEIGHT_MM = 620
MAX_HEIGHT_MM = 1270
START_HEIGHT_MM = 750
SPEED_MM_S = 35

CONNECT_DELAY = 1.0
RESPONSE_DELAY = 0.02
TICK = 0.1

MAX_HEIGHT = (MAX_HEIGHT_MM - BASE_HEIGHT_MM) * 10
SPEED = SPEED_MM_S * 100
STEP = round(SPEED_MM_S * 10 * TICK)

# memSize 4, autoUp, autoDown, bleAllow
CAPABILITIES = [4 | 8 | 16 | 32, 0]
# First byte already 1, so the handshake does not write the user id back
USER_ID = [1] + [0] * 15

_DPG = DPGService.DPG.uuid.lower()
_CONTROL = ControlService.COMMAND.uuid.lower()
_REFERENCE_INPUT = ReferenceInputService.ONE.uuid.lower()
_REFERENCE_OUTPUT = ReferenceOutputService.ONE.uuid.lower()


class MockDeskClient:
    _height = (START_HEIGHT_MM - BASE_HEIGHT_MM) * 10

    def __init__(self, address, disconnected_callback=None, **kwargs):
        self.address = address
        self._disconnected_callback = disconnected_callback
        self._connected = False
        self._notify = {}
        self._dpg_response = bytearray()
        self._speed = 0
        self._target = None
        self._move_task = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self, timeout=None, **kwargs) -> bool:
        await asyncio.sleep(CONNECT_DELAY)
        self._connected = True
        logger.log("Mock desk connected")
        return True

    async def disconnect(self) -> bool:
        if not self._connected:
            return True
        self._connected = False
        self._notify.clear()
        self._halt()
        if self._disconnected_callback is not None:
            # bleak schedules the callback for deliberate disconnects as well
            asyncio.get_running_loop().call_soon(self._disconnected_callback, self)
        return True

    async def read_gatt_char(self, char, **kwargs) -> bytearray:
        uuid = self._characteristic(char)
        if uuid == _REFERENCE_OUTPUT:
            return self._height_speed()
        if uuid == _DPG:
            return bytearray(self._dpg_response)
        raise BleakError(f"Mock desk cannot read characteristic {uuid}")

    async def write_gatt_char(self, char, data, response=None) -> None:
        uuid = self._characteristic(char)
        if uuid == _REFERENCE_INPUT:
            self._start_move(struct.unpack("<H", data)[0])
        elif uuid == _CONTROL:
            if data[0] == ControlService.COMMAND.CMD_STOP:
                self._halt()
        elif uuid == _DPG:
            self._answer_dpg(data)
        else:
            raise BleakError(f"Mock desk cannot write characteristic {uuid}")

    async def start_notify(self, char, callback, **kwargs) -> None:
        self._notify[self._characteristic(char)] = callback

    async def stop_notify(self, char) -> None:
        self._notify.pop(str(char).lower(), None)

    # --- Simulation ---

    def _characteristic(self, char) -> str:
        if not self._connected:
            raise BleakError("Mock desk is not connected")
        return str(char).lower()

    def _emit(self, uuid, data) -> None:
        callback = self._notify.get(uuid)
        if callback is not None:
            callback(uuid, bytearray(data))

    def _height_speed(self) -> bytearray:
        return bytearray(struct.pack("<Hh", MockDeskClient._height, self._speed))

    def _answer_dpg(self, data) -> None:
        """Answers a DPG command with a notification: [1, length, payload...]."""
        command = data[1]
        payload = []
        if data[2] != 128:  # read request; writes are only acknowledged
            if command == DPGService.DPG.CMD_GET_CAPABILITIES:
                payload = CAPABILITIES
            elif command == DPGService.DPG.CMD_USER_ID:
                payload = USER_ID
            elif command == DPGService.DPG.CMD_BASE_OFFSET:
                payload = [1] + list(struct.pack("<H", BASE_HEIGHT_MM * 10))
        self._dpg_response = bytearray([1, len(payload)] + payload)
        asyncio.get_running_loop().call_later(
            RESPONSE_DELAY, self._emit, _DPG, self._dpg_response
        )

    def _start_move(self, target) -> None:
        """Reference input: travel towards target. The speed is reported right
        away, as Desk.move_to stops polling once it reads a speed of 0."""
        self._target = max(0, min(int(target), MAX_HEIGHT))
        if self._target == MockDeskClient._height:
            return
        self._speed = SPEED if self._target > MockDeskClient._height else -SPEED
        if self._move_task is None:
            self._move_task = asyncio.get_running_loop().create_task(self._travel())

    async def _travel(self) -> None:
        while MockDeskClient._height != self._target:
            await asyncio.sleep(TICK)
            remaining = self._target - MockDeskClient._height
            MockDeskClient._height += max(-STEP, min(STEP, remaining))
            if MockDeskClient._height == self._target:
                self._speed = 0
            else:
                self._speed = SPEED if remaining > 0 else -SPEED
            self._emit(_REFERENCE_OUTPUT, self._height_speed())
        self._move_task = None

    def _halt(self) -> None:
        """Stop command: halt at the current height."""
        if self._move_task is not None:
            self._move_task.cancel()
            self._move_task = None
        self._target = None
        if self._speed != 0:
            self._speed = 0
            self._emit(_REFERENCE_OUTPUT, self._height_speed())
