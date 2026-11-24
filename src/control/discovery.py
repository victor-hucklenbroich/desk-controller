"""
Finds Linak desks nearby over Bluetooth LE.

This is what BLE browsers like Bluetility do to reveal a desk's address: an
unfiltered CoreBluetooth scan. Desks are told apart by the Linak control
service they advertise, or by LINAK A/S manufacturer data. A desk's address is
its CoreBluetooth peripheral UUID, which is specific to this Mac and is what
config.yaml names the current desk by, and its settings file is named after.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

import constants
from control import bluetooth
from control.linak.gatt import ControlService
from control.linak.mock import MockDeskClient

_log = logging.getLogger(__name__)

# Linak controllers advertise their control service
LINAK_SERVICE_UUID = ControlService.uuid.lower()
# LINAK A/S in the Bluetooth SIG company identifiers
LINAK_COMPANY_ID = 0x00A4

SIMULATED_DESK_NAME = "Simulated Desk"


class BluetoothUnavailableError(Exception):
    """Scanning is impossible: Bluetooth is off, unsupported or not allowed."""


@dataclass
class DiscoveredDesk:
    """A desk seen by a scan. `paired` and `rssi` describe it at that time."""
    address: str  # CoreBluetooth UUID, the key of the desk's settings
    name: str
    rssi: Optional[int] = None  # dBm; None when found already connected
    hardware_address: Optional[str] = None  # None when macOS won't tell
    paired: Optional[bool] = None  # macOS holds a pairing; None when unknown
    connected: bool = False  # connected to this Mac, so not advertising
    linak: bool = True  # False for the other devices an include_all scan lists
    # What bleak connects through, sparing a second scan
    device: Optional[BLEDevice] = field(default=None, repr=False, compare=False)

    @property
    def simulated(self) -> bool:
        return self.address == constants.MOCK_ADDRESS


def is_linak_desk(advertisement) -> bool:
    services = {uuid.lower() for uuid in advertisement.service_uuids}
    return (LINAK_SERVICE_UUID in services
            or LINAK_COMPANY_ID in advertisement.manufacturer_data)


def simulated_desk() -> DiscoveredDesk:
    """The development desk (control.linak.mock), as a scan would list it."""
    return DiscoveredDesk(
        address=constants.MOCK_ADDRESS, name=SIMULATED_DESK_NAME, rssi=-50,
        paired=MockDeskClient.paired,
    )


async def discover_desks(
        timeout: Optional[float] = None,
        on_found: Optional[Callable[[DiscoveredDesk], None]] = None,
        *,
        include_all: bool = False,
        simulated: bool = False,
        stop_when: Optional[Callable[[DiscoveredDesk], bool]] = None,
) -> List[DiscoveredDesk]:
    """Scans for `timeout` seconds and returns the desks found, already
    connected ones first, then by signal strength.

    on_found(desk) fires once per desk as it shows up. include_all lists every
    device in range, with `linak` telling desks apart. simulated adds the
    development desk. The scan ends early once stop_when(desk) is true for a
    found desk. Raises BluetoothUnavailableError when Bluetooth can't be used.
    """
    timeout = constants.SCAN_TIMEOUT if timeout is None else timeout
    found: Dict[str, DiscoveredDesk] = {}
    finished = asyncio.Event()
    paired_now = bluetooth.paired_devices()  # one snapshot for the whole scan

    def paired(hardware_address, name):
        if paired_now is None:
            return None
        return bluetooth.is_paired(hardware_address, name, paired_now)

    def add(desk: DiscoveredDesk):
        found[desk.address] = desk
        _log.info(f"Found {'desk' if desk.linak else 'device'} {desk.name!r} ({desk.address})")
        if on_found is not None:
            on_found(desk)
        if stop_when is not None and stop_when(desk):
            finished.set()

    def detected(device: BLEDevice, advertisement):
        linak = is_linak_desk(advertisement)
        if not (linak or include_all):
            return
        desk = found.get(device.address)
        if desk is not None:
            desk.rssi = advertisement.rssi
            return
        name = advertisement.local_name or device.name or ""
        hardware_address = bluetooth.peripheral_address(device)
        add(DiscoveredDesk(
            address=device.address, name=name, rssi=advertisement.rssi,
            hardware_address=hardware_address,
            paired=paired(hardware_address, name),
            linak=linak, device=device,
        ))

    scanner = BleakScanner(detection_callback=detected)
    try:
        await scanner.start()
    except BleakError as e:
        raise BluetoothUnavailableError(_explain(e)) from e
    try:
        for device in _connected_desks():
            if device.address not in found:
                hardware_address = bluetooth.peripheral_address(device)
                name = device.name or ""
                add(DiscoveredDesk(
                    address=device.address, name=name,
                    hardware_address=hardware_address,
                    paired=paired(hardware_address, name),
                    connected=True, device=device,
                ))
        if simulated:
            add(simulated_desk())
        if not finished.is_set():
            try:
                await asyncio.wait_for(finished.wait(), timeout)
            except asyncio.TimeoutError:
                pass
    finally:
        await scanner.stop()

    return sorted(found.values(), key=lambda desk: (
        not desk.linak, not desk.connected,
        -desk.rssi if desk.rssi is not None else 0,
    ))


async def find_desk(target: str, timeout: Optional[float] = None) -> Optional[DiscoveredDesk]:
    """Scans until the device with this address, or a desk with this name,
    shows up. None when it doesn't within `timeout` seconds."""
    wanted = target.strip().lower()
    if wanted == constants.MOCK_ADDRESS:
        return simulated_desk()

    def matches(desk: DiscoveredDesk) -> bool:
        return (desk.address.lower() == wanted
                or (desk.linak and desk.name.lower() == wanted))

    desks = await discover_desks(timeout, include_all=True, stop_when=matches)
    return next((desk for desk in desks if matches(desk)), None)


def _connected_desks() -> List[BLEDevice]:
    """Desks connected to this Mac, by this app or another, don't advertise,
    so a scan misses them; CoreBluetooth hands them out by service instead."""
    try:
        from bleak.backends.corebluetooth.CentralManagerDelegate import (
            CentralManagerDelegate,
        )
        from CoreBluetooth import CBUUID

        manager = CentralManagerDelegate.alloc().init()
        peripherals = manager.central_manager.retrieveConnectedPeripheralsWithServices_(
            [CBUUID.UUIDWithString_(LINAK_SERVICE_UUID)]
        ) or []
        return [
            BLEDevice(str(p.identifier().UUIDString()), p.name(), (p, manager))
            for p in peripherals
        ]
    except Exception as e:
        _log.warning(f"Could not look up connected desks: {e}")
        return []


def _explain(error: BleakError) -> str:
    """User-facing reason for bleak failing to start a scan."""
    message = str(error)
    if "not authorized" in message:
        return ("DeskController is not allowed to use Bluetooth. Allow it in "
                "System Settings → Privacy & Security → Bluetooth.")
    if "turned off" in message:
        return "Bluetooth is turned off."
    if "unsupported" in message:
        return "This Mac does not support Bluetooth LE."
    return f"Bluetooth is unavailable: {message}"
