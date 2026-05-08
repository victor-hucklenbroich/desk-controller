import socket
import subprocess

import Cocoa
import objc
from Foundation import NSObject, NSTimer

import constants
from constants import LOGGER
from control.process import BackgroundProcess, _TimerProxy


class Server(NSObject):
    """
    Owns the lifecycle of a long-running background server:
    spawns it, polls for unexpected death, and recycles it across
    system sleep/wake. Exposes is_running()/stop() so callers can
    treat it like a BackgroundProcess.
    """

    def initWithCommand_(self, command):
        self = objc.super(Server, self).init()
        if self is None:
            return None
        self._command = command
        self._process = None
        self._observing_workspace = False
        self._dead = False
        self._failures = 0
        self._probe_timer = None
        self._probe_proxy = None
        return self

    @objc.python_method
    def start(self):
        self._dead = False
        self._failures = 0
        self._spawn("initial start")
        self._registerWorkspaceObservers()

    @objc.python_method
    def stop(self):
        self._cancelProbe()
        self._unregisterWorkspaceObservers()
        self._teardownProcess("supervisor stop")

    @objc.python_method
    def is_running(self):
        return self._process is not None and self._process.is_running()

    @objc.python_method
    def is_dead(self):
        return self._dead

    @objc.python_method
    def is_healthy(self):
        """Process alive AND TCP port reachable."""
        return self.is_running() and self._probePort()

    @objc.python_method
    def retry(self):
        """User-initiated retry after the server has been declared dead."""
        if not self._dead:
            return
        LOGGER.info("Retrying server")
        self._dead = False
        self._failures = 0
        self._spawn("user retry")

    @objc.python_method
    def _probePort(self):
        try:
            with socket.create_connection(
                    (constants.SERVER_HOST, constants.SERVER_PORT), timeout=0.5
            ):
                return True
        except (OSError, socket.timeout):
            return False

    @objc.python_method
    def _scheduleReadinessProbe(self):
        self._cancelProbe()
        self._probe_proxy = _TimerProxy.alloc().initWithCallback_(self._onProbe)
        self._probe_timer = (
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                2.5, self._probe_proxy, "fire:", None, False
            )
        )

    @objc.python_method
    def _cancelProbe(self):
        if self._probe_timer is not None:
            self._probe_timer.invalidate()
            self._probe_timer = None
        self._probe_proxy = None

    @objc.python_method
    def _onProbe(self):
        self._cancelProbe()
        if self._process is None or self._dead:
            return  # torn down or already given up

        if self.is_running() and self._probePort():
            LOGGER.info(
                f"Server ready on {constants.SERVER_HOST}:{constants.SERVER_PORT}"
            )
            self._failures = 0
            # TODO checkAndUpdatePopover
            return

        self._failures += 1
        LOGGER.warning(
            f"Server probe failed ({self._failures}/{constants.MAX_RECONNECT_FAILURES})"
        )
        if self._failures >= constants.MAX_RECONNECT_FAILURES:
            LOGGER.error("Server unreachable after retries; marking dead")
            self._teardownProcess("max failures reached")
            self._dead = True
            # TODO checkAndUpdatePopover
            return

        self._recycle("retry after failed probe")

    @objc.python_method
    def _spawn(self, reason):
        LOGGER.info(f"Starting server ({reason})")
        cmd_list = (
            self._command.split() if isinstance(self._command, str) else self._command
        )
        popen = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._process = BackgroundProcess(popen)
        self._process.start_health_check(
            interval=2.0, on_terminated=self._onProcessDied
        )
        self._scheduleReadinessProbe()

    @objc.python_method
    def _teardownProcess(self, reason):
        self._cancelProbe()
        if self._process is None:
            return
        LOGGER.info(f"Stopping server ({reason})")
        try:
            self._process.stop()
        except Exception as e:
            LOGGER.warning(f"Error stopping server: {e}")
        self._process = None

    @objc.python_method
    def _recycle(self, reason):
        self._teardownProcess(reason)
        self._spawn(reason)

    @objc.python_method
    def _onProcessDied(self, bg_process):
        if self._dead:
            return
        self._failures += 1
        if self._failures >= constants.MAX_RECONNECT_FAILURES:
            LOGGER.error("Server keeps dying; marking dead")
            self._teardownProcess("max failures reached")
            self._dead = True
            # TODO checkAndUpdatePopover
            return
        self._recycle("process exited")

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
        self._teardownProcess("system will sleep")

    def systemDidWake_(self, notification):
        self._spawn("system wake")
