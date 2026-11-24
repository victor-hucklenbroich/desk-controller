import asyncio
import dataclasses
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Union

from bleak import BleakClient

import constants
from control import bluetooth
from control.discovery import BluetoothUnavailableError, DiscoveredDesk, find_desk
from control.linak.desk import Desk
from control.linak.mock import MockDeskClient

_log = logging.getLogger(__name__)


class PairingStep(Enum):
    SEARCHING = "searching"
    CONNECTING = "connecting"
    PAIRING = "pairing"


class PairingOutcome(Enum):
    PAIRED = "paired"  # macOS paired with the desk just now
    ALREADY_PAIRED = "already paired"  # paired before; the connection works
    UNKNOWN = "unknown"  # the desk answers, but macOS won't say if it's paired
    NOT_PAIRED = "not paired"  # the desk answers, but macOS didn't pair
    NOT_FOUND = "not found"
    FAILED = "failed"


@dataclass
class PairingResult:
    outcome: PairingOutcome
    desk: Optional[DiscoveredDesk] = None
    height_mm: Optional[int] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        """The desk is ready for use: store desk.address as the config's
        mac_address and connect."""
        return self.outcome in (
            PairingOutcome.PAIRED, PairingOutcome.ALREADY_PAIRED, PairingOutcome.UNKNOWN,
        )


def is_paired(desk: DiscoveredDesk) -> Optional[bool]:
    """Whether macOS holds a pairing for the desk right now; None if unknown."""
    if desk.simulated:
        return MockDeskClient.paired
    return bluetooth.is_paired(desk.hardware_address, desk.name)


async def pair_desk(
        desk: Union[DiscoveredDesk, str],
        timeout: Optional[float] = None,
        on_step: Optional[Callable[[PairingStep], None]] = None,
        *,
        client_factory=None,
        paired_lookup: Callable[[DiscoveredDesk], Optional[bool]] = is_paired,
) -> PairingResult:
    """Pairs with a desk in pairing mode and checks that it answers.

    `desk` is a scan result, or an address or name to scan for. on_step(step)
    reports progress. `timeout` bounds the time from connecting until macOS
    has paired, which includes the user accepting macOS' pairing request. A
    desk that is paired already only gets its connection checked.
    """
    timeout = constants.PAIRING_TIMEOUT if timeout is None else timeout
    step = on_step or (lambda _step: None)

    if not isinstance(desk, DiscoveredDesk):
        step(PairingStep.SEARCHING)
        target = desk
        try:
            desk = await find_desk(target)
        except BluetoothUnavailableError as e:
            return PairingResult(PairingOutcome.FAILED, error=str(e))
        if desk is None:
            return PairingResult(PairingOutcome.NOT_FOUND, error=(
                f"Couldn't find {target}. Make sure the desk is nearby, has "
                f"power and isn't connected to another device, like a phone."
            ))

    name = desk.name or "the desk"
    was_paired = paired_lookup(desk)
    _log.info(f"Pairing with {desk.name!r} ({desk.address}), paired before: {was_paired}")

    disconnected = asyncio.Event()
    factory = client_factory or (MockDeskClient if desk.simulated else BleakClient)
    client = factory(
        desk.device or desk.address,
        disconnected_callback=lambda _client: disconnected.set(),
    )

    step(PairingStep.CONNECTING)
    try:
        await client.connect(timeout=constants.CONNECTION_TIMEOUT)
    except Exception as e:
        _log.warning(f"Pairing: could not connect to {desk.address}: {e}")
        await _disconnect(client)
        return PairingResult(PairingOutcome.FAILED, desk, error=f"Couldn't connect to {name}: {e}")

    step(PairingStep.PAIRING)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    dropped = (
        f"{name} ended the connection. Accept the pairing request if macOS "
        f"shows one, and make sure the desk is in pairing mode."
    )
    try:
        linak_desk = await asyncio.wait_for(
            _handshake(client), max(deadline - loop.time(), 0.1)
        )
        paired = was_paired or await _wait_for_pairing(
            paired_lookup, desk, deadline, disconnected
        )
        if paired is False:
            if disconnected.is_set():
                return PairingResult(PairingOutcome.FAILED, desk, error=dropped)
            return PairingResult(
                PairingOutcome.NOT_PAIRED, dataclasses.replace(desk, paired=False),
                error=(
                    f"macOS didn't pair with {name}. Hold the Bluetooth button "
                    f"on the desk until its light blinks, then try again."
                ),
            )
        # Proves the link still works now that it's paired (and encrypted)
        height, _speed = await asyncio.wait_for(
            linak_desk.get_height_speed(), constants.HANDSHAKE_TIMEOUT
        )
        if paired is None:
            outcome = PairingOutcome.UNKNOWN
        else:
            outcome = PairingOutcome.ALREADY_PAIRED if was_paired else PairingOutcome.PAIRED
        _log.info(f"Pairing with {desk.address} finished: {outcome.value}")
        return PairingResult(
            outcome, dataclasses.replace(desk, paired=paired),
            height_mm=None if height is None else height.human,
        )
    except asyncio.TimeoutError:
        _log.warning(f"Pairing: {desk.address} did not answer in time")
        return PairingResult(PairingOutcome.FAILED, desk, error=dropped if disconnected.is_set() else (
            f"{name} didn't answer in time. Accept the pairing request if "
            f"macOS shows one."
        ))
    except Exception as e:
        _log.warning(f"Pairing: talking to {desk.address} failed: {e}")
        if disconnected.is_set():
            return PairingResult(PairingOutcome.FAILED, desk, error=dropped)
        return PairingResult(
            PairingOutcome.FAILED, desk, error=f"{name} didn't answer like a Linak desk: {e}"
        )
    finally:
        await _disconnect(client)


async def _handshake(client) -> Desk:
    """The handshake every connection runs. On a desk in pairing mode, this is
    where macOS pairs, unless the desk asked for it right on connecting."""
    return await Desk.initialise(
        {"base_height": None, "move_command_period": constants.MOVE_COMMAND_PERIOD},
        client,
    )


async def _wait_for_pairing(lookup, desk, deadline, disconnected) -> Optional[bool]:
    """Polls until macOS lists the desk as paired: True. False once the
    deadline passes or the desk drops the connection, None if it can't tell."""
    loop = asyncio.get_running_loop()
    while True:
        paired = lookup(desk)
        if paired is not False:
            return paired
        if disconnected.is_set() or loop.time() >= deadline:
            return False
        await asyncio.sleep(constants.PAIRING_POLL_INTERVAL)


async def _disconnect(client) -> None:
    try:
        await asyncio.wait_for(client.disconnect(), constants.CONNECTION_TIMEOUT)
    except Exception as e:
        _log.debug(f"Pairing: disconnecting failed: {e}")
