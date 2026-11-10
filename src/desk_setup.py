import argparse
import asyncio
import logging
import sys

BUNDLE_ID = "com.victorhucklenbroich.DeskController"


def _parse(argv):
    parser = argparse.ArgumentParser(description="Find and pair Linak desks.")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="list the desks nearby")
    scan.add_argument("--timeout", type=float, help="scan duration in seconds")
    scan.add_argument("--all", action="store_true", help="list every Bluetooth LE device in range")
    scan.add_argument("--simulated", action="store_true", help="include the simulated development desk")

    pair = commands.add_parser("pair", help="pair this Mac with a desk")
    pair.add_argument("desk", nargs="?", help="address (UUID) or name; asks after a scan when left out")
    pair.add_argument("--timeout", type=float, help="seconds to give macOS to pair once connected")
    pair.add_argument("--save", action="store_true", help="make it DeskController's desk once paired")
    pair.add_argument("--simulated", action="store_true", help="include the simulated development desk")
    pair.add_argument("-y", "--yes", action="store_true", help="don't wait for Enter before pairing")
    return parser.parse_args(argv)


def _row(desk, all_devices=False):
    if desk.connected:
        signal = "connected"
    else:
        signal = f"{desk.rssi} dBm" if desk.rssi is not None else ""
    paired = {True: "paired", False: "not paired", None: "unknown"}[desk.paired]
    kind = ("desk  " if desk.linak else "      ") if all_devices else ""
    return (f"{kind}{desk.name or '(no name)':<24} {desk.address:<36}  "
            f"{desk.hardware_address or '-':<17}  {signal:>9}  {paired}")


def _print_desks(desks, all_devices=False):
    kind = "      " if all_devices else ""
    print(f"   {kind}{'NAME':<24} {'ADDRESS (CoreBluetooth UUID)':<36}  "
          f"{'HARDWARE ADDRESS':<17}  {'SIGNAL':>9}  PAIRED")
    for index, desk in enumerate(desks, 1):
        print(f"{index:>2} {_row(desk, all_devices)}")


async def _ask(prompt):
    """input() off the event loop, so CoreBluetooth callbacks keep flowing."""
    return await asyncio.get_running_loop().run_in_executor(None, input, prompt)


async def _scan(args):
    import constants
    from control import discovery

    seconds = args.timeout if args.timeout is not None else constants.SCAN_TIMEOUT
    print(f"Scanning for {'Bluetooth LE devices' if args.all else 'desks'} ({seconds:g}s)…")
    desks = await discovery.discover_desks(
        args.timeout, include_all=args.all, simulated=args.simulated
    )
    count = sum(desk.linak for desk in desks)
    if desks:
        _print_desks(desks, args.all)
    print(f"Found {count} desk{'' if count == 1 else 's'}"
          + (f" among {len(desks)} devices." if args.all else "."))
    if not count:
        print("A desk that is connected to another device, like a phone, doesn't show up.")
    return 0 if count else 1


async def _choose_desk(args):
    from control import discovery

    if args.desk is not None:
        print(f"Looking for {args.desk}…")
        desk = await discovery.find_desk(args.desk)
        if desk is None:
            print(f"Couldn't find {args.desk}. Make sure the desk is nearby, has power "
                  f"and isn't connected to another device, like a phone.")
        return desk

    print("Scanning for desks…")
    desks = await discovery.discover_desks(simulated=args.simulated)
    if not desks:
        print("No desks found. Make sure the desk is nearby, has power and isn't "
              "connected to another device, like a phone.")
        return None
    _print_desks(desks)
    if len(desks) == 1:
        return desks[0]
    if not sys.stdin.isatty():
        print("Several desks found; pass the address of the one to pair with.")
        return None
    while True:
        answer = (await _ask(f"Pair with which desk? [1-{len(desks)}] ")).strip()
        if answer.isdigit() and 1 <= int(answer) <= len(desks):
            return desks[int(answer) - 1]


async def _pair(args):
    from control import pairing
    from control.pairing import PairingOutcome, PairingStep

    desk = await _choose_desk(args)
    if desk is None:
        return 1
    name = desk.name or "the desk"
    if desk.paired is not True and not args.yes and sys.stdin.isatty():
        await _ask(f"Hold the Bluetooth button on {name}'s control panel until its "
                   f"light blinks, then press Enter.")

    def on_step(step):
        if step == PairingStep.CONNECTING:
            print(f"Connecting to {name}…")
        elif step == PairingStep.PAIRING:
            if desk.paired:
                print("Connected. Checking the desk…")
            else:
                print(f"Connected. Waiting for macOS to pair; if it asks to pair "
                      f"with “{name}”, accept.")

    result = await pairing.pair_desk(desk, args.timeout, on_step)
    if result.outcome == PairingOutcome.PAIRED:
        print(f"Paired with {name}.")
    elif result.outcome == PairingOutcome.ALREADY_PAIRED:
        print(f"{name} was already paired with this Mac, and the connection works.")
    elif result.outcome == PairingOutcome.UNKNOWN:
        print(f"Connected to {name}, but macOS won't say whether it is paired.")
    else:
        print(result.error)
        return 1

    print(f"  Address:          {result.desk.address}")
    if result.desk.hardware_address:
        print(f"  Hardware address: {result.desk.hardware_address}")
    if result.height_mm is not None:
        print(f"  Height:           {result.height_mm / 10:.1f} cm")
    if args.save:
        _save(result.desk.address)
    else:
        print("Pass --save to make it DeskController's desk.")
    return 0


def _save(address):
    import constants
    from AppKit import NSRunningApplication
    from control.config import ConfigParser

    ConfigParser.update(uuid=address)
    print(f"Saved as DeskController's desk in {constants.CONFIG_FILE_PATH}")
    if NSRunningApplication.runningApplicationsWithBundleIdentifier_(BUNDLE_ID):
        print("DeskController is running: quit and reopen it now, before changing "
              "its settings, so it doesn't write back the old desk.")


def main(argv=None):
    args = _parse(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    from control.discovery import BluetoothUnavailableError

    command = _scan if args.command == "scan" else _pair
    try:
        return asyncio.run(command(args))
    except BluetoothUnavailableError as e:
        print(e)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
