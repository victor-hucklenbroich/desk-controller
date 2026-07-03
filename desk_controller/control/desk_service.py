import asyncio
import threading
from enum import Enum

import Cocoa
import objc
from Foundation import NSObject
from PyObjCTools import AppHelper
from bleak import BleakClient

import constants
from constants import LOGGER
from control.config import ConfigParser
from control.linak.desk import Desk
from control.linak.util import Height


class DeskState(Enum):
    IDLE = 0        # no connection attempt running (setup pending or stopped)
    CONNECTING = 1
    CONNECTED = 2
    DEAD = 3        # gave up after repeated failures; waiting for user retry


class DeskService(NSObject):
    """
    Owns the native BLE link to the desk: connects on startup, keeps a
    height/speed watch subscription running, reconnects after unexpected
    drops and system sleep/wake, and executes move commands.

    Runs an asyncio event loop on a background thread for all bleak I/O.
    UI-facing callbacks (state changes, height events, move completion) are
    marshalled onto the main thread, so the app only ever hears from this
    class there. `_client`/`_desk` are only touched on the loop thread.
    """

    def init(self):
        self = objc.super(DeskService, self).init()
        if self is None:
            return None
        self._app = None
        self._loop = None
        self._thread = None
        self._state = DeskState.IDLE
        self._client = None
        self._desk = None
        self._connecting = False
        self._suspended = False   # system sleep in progress
        self._closing = False
        self._was_moving = False
        self._max_seen_mm = 0.0
        self._observing_workspace = False
        return self

    # --- Public API (main thread) ---

    @objc.python_method
    def setApp(self, app):
        """Reference App instance for UI update callbacks."""
        self._app = app

    @objc.python_method
    def start(self):
        """Start the BLE loop thread and connect if a desk UUID is configured."""
        if self._thread is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._runLoop, name="desk-ble", daemon=True
        )
        self._thread.start()
        self._registerWorkspaceObservers()
        self._beginConnect("initial start")

    @objc.python_method
    def stop(self):
        """Disconnect cleanly and shut down the BLE loop thread."""
        if self._closing:
            return
        self._closing = True
        self._unregisterWorkspaceObservers()
        if self._loop is not None and self._thread is not None and self._thread.is_alive():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._disconnect_current(), self._loop
                )
                future.result(timeout=3.0)
            except Exception as e:
                LOGGER.warning(f"Error disconnecting from desk: {e}")
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2.0)
        self._state = DeskState.IDLE

    @objc.python_method
    def retry(self):
        """User-initiated (re)connect: after setup, a UUID change, or DEAD."""
        self._beginConnect("user retry")

    @objc.python_method
    def is_healthy(self):
        return self._state == DeskState.CONNECTED

    @objc.python_method
    def is_dead(self):
        return self._state == DeskState.DEAD

    @objc.python_method
    def move_to_cm(self, target_cm, on_done=None):
        """Move the desk to target_cm. on_done(success) fires on the main thread
        once the desk reports it has stopped."""
        if self._loop is None or self._state != DeskState.CONNECTED:
            LOGGER.warning("Ignoring move request; desk not connected")
            if on_done is not None:
                on_done(False)
            return
        target_cm = max(constants.MIN_HEIGHT, min(constants.MAX_HEIGHT, float(target_cm)))
        future = asyncio.run_coroutine_threadsafe(self._do_move(target_cm), self._loop)

        def _completed(fut):
            try:
                ok = bool(fut.result())
            except Exception as e:
                LOGGER.error(f"Desk move failed: {e}")
                ok = False
                self._handle_move_failure()
            if on_done is not None:
                AppHelper.callAfter(on_done, ok)

        future.add_done_callback(_completed)

    # --- Connection lifecycle (BLE loop thread) ---

    @objc.python_method
    def _runLoop(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            finally:
                self._loop.close()

    @objc.python_method
    def _beginConnect(self, reason, initial_delay=0.0):
        """Kick off (re)connection. Main thread only."""
        if self._closing or self._loop is None:
            return
        if constants.CONFIG_UUID == constants.PLACEHOLDER_UUID:
            LOGGER.info("No desk UUID configured yet; waiting for setup")
            self._applyState(DeskState.IDLE)
            return
        LOGGER.info(f"Connecting to desk ({reason})")
        self._applyState(DeskState.CONNECTING)
        asyncio.run_coroutine_threadsafe(
            self._recycle_and_connect(initial_delay), self._loop
        )

    @objc.python_method
    async def _recycle_and_connect(self, initial_delay=0.0):
        await self._disconnect_current()
        await self._connect(initial_delay)

    @objc.python_method
    async def _connect(self, initial_delay=0.0):
        if self._connecting:
            return  # a connect loop is already running; it reads the config fresh
        self._connecting = True
        try:
            if initial_delay:
                await asyncio.sleep(initial_delay)
            failures = 0
            while not self._closing and not self._suspended:
                uuid = constants.CONFIG_UUID
                if uuid == constants.PLACEHOLDER_UUID:
                    self._request_state(DeskState.IDLE)
                    return
                client = BleakClient(
                    uuid, disconnected_callback=self._on_ble_disconnected
                )
                try:
                    LOGGER.info(f"Desk connection attempt to {uuid}")
                    await client.connect(timeout=constants.CONNECTION_TIMEOUT)
                    desk, height, speed = await asyncio.wait_for(
                        self._perform_handshake(client),
                        timeout=constants.HANDSHAKE_TIMEOUT,
                    )
                    self._client = client
                    self._desk = desk
                    self._max_seen_mm = 0.0
                    LOGGER.info(f"Connected to desk at {height.human}mm")

                    base_mm = (
                        None if desk.base_height_estimated
                        else float(desk.config["base_height"])
                    )
                    max_mm = max(constants.MAX_HEIGHT * 10.0, float(height.human))
                    AppHelper.callAfter(self._applyLimits, base_mm, max_mm)

                    self._push_height(height, speed)
                    self._request_state(DeskState.CONNECTED)
                    return
                except Exception as e:
                    LOGGER.warning(f"Desk connection attempt failed: {e}")
                    await self._safe_disconnect(client)
                    failures += 1
                    if failures >= constants.MAX_RECONNECT_FAILURES:
                        LOGGER.error("Desk unreachable after retries; marking dead")
                        self._request_state(DeskState.DEAD)
                        return
                    await asyncio.sleep(constants.RECONNECT_DELAY)
        finally:
            self._connecting = False

    @objc.python_method
    async def _perform_handshake(self, client):
        """Initialise the desk over a freshly-connected client and start the
        height/speed watch. Kept as one coroutine so the caller can bound the
        whole GATT exchange with a single timeout."""
        desk = await Desk.initialise(
            {
                "base_height": constants.CONFIG_BASE_HEIGHT,
                "move_command_period": constants.MOVE_COMMAND_PERIOD,
            },
            client,
        )
        desk.subscribe(self._on_height_speed)
        await desk.start_watching()
        height = desk.latest_height
        speed = desk.latest_speed
        if height is None:
            height, speed = await desk.get_height_speed()
        return desk, height, speed

    @objc.python_method
    async def _safe_disconnect(self, client):
        """Best-effort disconnect of a failed attempt that can't hang the loop."""
        try:
            await asyncio.wait_for(
                client.disconnect(), timeout=constants.CONNECTION_TIMEOUT
            )
        except Exception:
            pass

    @objc.python_method
    async def _disconnect_current(self):
        """Deliberately drop the current connection. Detaches refs first so the
        bleak disconnect callback recognises this as expected."""
        client, desk = self._client, self._desk
        self._client = None
        self._desk = None
        if desk is not None:
            try:
                await desk.stop_watching()
            except Exception:
                pass
        if client is not None:
            try:
                await client.disconnect()
            except Exception as e:
                LOGGER.warning(f"BLE disconnect failed: {e}")

    @objc.python_method
    def _on_ble_disconnected(self, client):
        """bleak disconnect callback (loop thread). Reconnect on unexpected drops."""
        if client is not self._client:
            return  # deliberate disconnect or a stale client from an old session
        self._client = None
        self._desk = None
        if self._closing or self._suspended:
            return
        LOGGER.warning("Lost connection to desk; reconnecting")
        self._request_state(DeskState.CONNECTING)
        asyncio.run_coroutine_threadsafe(
            self._connect(constants.RECONNECT_DELAY), self._loop
        )

    # --- Moving (BLE loop thread) ---

    @objc.python_method
    async def _do_move(self, target_cm):
        desk = self._desk
        if desk is None:
            return False
        # The desk works in mm, the UI in cm; convert without losing precision
        target_mm = int(round(target_cm * 10))
        target = Height(target_mm, desk.config["base_height"], True)
        if target.value < 0 or target.value > 65535:
            LOGGER.warning(f"Target height {target_cm}cm is out of range for this desk")
            return False
        LOGGER.info(f"Moving desk to {target_mm}mm")
        await desk.move_to(target)
        return True

    @objc.python_method
    def _handle_move_failure(self):
        """A move that failed while the link still looks up means the connection
        wedged; recycle it. A dropped link is handled by _on_ble_disconnected."""
        client = self._client
        if self._closing or self._suspended or client is None:
            return
        if client.is_connected:
            LOGGER.warning("Move failed on a live connection; recycling BLE link")
            self._request_state(DeskState.CONNECTING)
            asyncio.run_coroutine_threadsafe(self._recycle_and_connect(), self._loop)

    # --- Height events (BLE loop thread -> main thread) ---

    @objc.python_method
    def _on_height_speed(self, height, speed):
        """Desk pub/sub subscriber; fires for app moves and external moves alike."""
        self._push_height(height, speed)

    @objc.python_method
    def _push_height(self, height, speed):
        mm = float(height.human)
        cm = int(round(mm / 10.0))
        moving = bool(speed is not None and speed.value != 0)
        if mm > self._max_seen_mm:
            self._max_seen_mm = mm
        if moving != self._was_moving:
            self._was_moving = moving
            LOGGER.info(
                f"Desk movement {'started' if moving else 'stopped'} at {cm}cm"
            )
            # The desk clamps at its physical top, so any height report above
            # the known maximum proves a larger range; adopt it once the desk
            # has stopped moving
            if not moving and self._max_seen_mm > constants.MAX_HEIGHT * 10.0 + 0.5:
                AppHelper.callAfter(self._applyLimits, None, self._max_seen_mm)
        AppHelper.callAfter(self._notifyHeight, cm, moving)

    @objc.python_method
    def _notifyHeight(self, cm, moving):
        if self._app is not None and not self._closing:
            self._app.deskHeightChanged(cm, moving)

    @objc.python_method
    def _applyLimits(self, base_mm, max_mm):
        """Adopt desk-derived height limits. Main thread only. MIN mirrors the
        desk's base offset; MAX only ever grows and is persisted to config."""
        changed = False
        if base_mm is not None:
            min_cm = base_mm / 10.0
            if abs(min_cm - constants.MIN_HEIGHT) > 0.01:
                constants.MIN_HEIGHT = min_cm
                changed = True
        if max_mm is not None:
            max_cm = max_mm / 10.0
            if max_cm > constants.MAX_HEIGHT + 0.01:
                constants.MAX_HEIGHT = max_cm
                try:
                    ConfigParser.update_max_height(int(round(max_mm)))
                except Exception as e:
                    LOGGER.warning(f"Could not persist max height: {e}")
                changed = True
        if constants.MAX_HEIGHT <= constants.MIN_HEIGHT:
            # Nonsensical combination (e.g. bad config override)
            # keep the slider usable with a typical 65cm travel.
            constants.MAX_HEIGHT = constants.MIN_HEIGHT + 65.0
            changed = True
        if changed:
            LOGGER.info(
                f"Desk height limits now "
                f"{constants.MIN_HEIGHT:.1f}-{constants.MAX_HEIGHT:.1f}cm"
            )
            if self._app is not None:
                self._app.deskLimitsChanged()

    # --- State handling ---

    @objc.python_method
    def _request_state(self, state):
        """Ask the main thread to apply a state change (loop thread side)."""
        AppHelper.callAfter(self._applyState, state)

    @objc.python_method
    def _applyState(self, state):
        """Apply a state change and refresh the UI. Main thread only."""
        if self._closing or state == self._state:
            return
        LOGGER.info(f"Desk connection state: {self._state.name} -> {state.name}")
        self._state = state
        if self._app is not None:
            self._app.checkAndUpdatePopover()

    # --- System sleep/wake ---

    @objc.python_method
    def _registerWorkspaceObservers(self):
        if self._observing_workspace:
            return
        nc = Cocoa.NSWorkspace.sharedWorkspace().notificationCenter()
        nc.addObserver_selector_name_object_(
            self, "systemWillSleep:", "NSWorkspaceWillSleepNotification", None
        )
        nc.addObserver_selector_name_object_(
            self, "systemDidWake:", "NSWorkspaceDidWakeNotification", None
        )
        self._observing_workspace = True

    @objc.python_method
    def _unregisterWorkspaceObservers(self):
        if not self._observing_workspace:
            return
        Cocoa.NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(self)
        self._observing_workspace = False

    def systemWillSleep_(self, notification):
        LOGGER.info("System will sleep; disconnecting from desk")
        self._suspended = True
        if self._loop is not None:
            asyncio.run_coroutine_threadsafe(self._disconnect_current(), self._loop)

    def systemDidWake_(self, notification):
        LOGGER.info("System woke; reconnecting to desk")
        self._suspended = False
        self._beginConnect(
            "system wake", initial_delay=constants.WAKE_RECONNECT_DELAY
        )
