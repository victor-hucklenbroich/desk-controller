import logging
from typing import Dict, Optional

import objc

_log = logging.getLogger(__name__)

_IOBLUETOOTH_PATH = "/System/Library/Frameworks/IOBluetooth.framework"
_device_class = None


def _io_bluetooth_device():
    """IOBluetoothDevice, loaded on first use. Loading the framework directly
    spares a PyObjC wrapper dependency for the two calls made here."""
    global _device_class
    if _device_class is None:
        namespace = {}
        objc.loadBundle("IOBluetooth", namespace, bundle_path=_IOBLUETOOTH_PATH)
        _device_class = namespace["IOBluetoothDevice"]
    return _device_class


def format_address(address: str) -> str:
    """Normalises a hardware address to the AA:BB:CC:DD:EE:FF form."""
    return str(address).replace("-", ":").upper()


def peripheral_address(device) -> Optional[str]:
    """Hardware address of a bleak BLEDevice found through CoreBluetooth, or
    None when macOS won't tell. Bonded devices report their identity address,
    which is what IOBluetooth lists them by. Relies on CBCentralManager's
    undocumented retrieveAddressForPeripheral:, the call behind bleak's
    use_bdaddr option."""
    try:
        peripheral, manager = device.details
        central = manager.central_manager
        if not central.respondsToSelector_(b"retrieveAddressForPeripheral:"):
            return None
        raw = central.retrieveAddressForPeripheral_(peripheral)
    except Exception as e:
        _log.debug(f"No hardware address for {getattr(device, 'address', device)}: {e}")
        return None
    if raw is None or len(raw) != 6:
        return None
    return bytes(raw).hex(":").upper()


def paired_devices() -> Optional[Dict[str, str]]:
    """Hardware address -> name of every device paired with this Mac, or None
    when the list can't be read."""
    try:
        devices = _io_bluetooth_device().pairedDevices() or []
        return {
            format_address(device.addressString()): str(device.name() or "")
            for device in devices
        }
    except Exception as e:
        _log.warning(f"Could not read the paired Bluetooth devices: {e}")
        return None


def is_paired(address: Optional[str], name: Optional[str] = None,
              paired: Optional[Dict[str, str]] = None) -> Optional[bool]:
    """Whether macOS holds a pairing for a device, judged by its hardware
    address or, without one, by its name. None when it can't be told. Pass
    `paired` to check against a snapshot of paired_devices()."""
    if address is None and not name:
        return None
    if paired is None:
        paired = paired_devices()
        if paired is None:
            return None
    if address is not None:
        return format_address(address) in paired
    return name in paired.values()
