import subprocess

import Cocoa
import objc
from Foundation import NSObject, NSTimer

from constants import LOGGER
from control.process import BackgroundProcess


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
        return self

    @objc.python_method
    def start(self):
        self._spawn("initial start")
        self._registerWorkspaceObservers()

    @objc.python_method
    def stop(self):
        self._unregisterWorkspaceObservers()
        self._teardownProcess("supervisor stop")

    @objc.python_method
    def is_running(self):
        return self._process is not None and self._process.is_running()

    @objc.python_method
    def _spawn(self, reason):
        LOGGER.info(f"Starting server ({reason})")
        cmd_list = self._command.split() if isinstance(self._command, str) else self._command
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

    @objc.python_method
    def _teardownProcess(self, reason):
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
        # Fired on the main thread by BackgroundProcess's NSTimer.
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
