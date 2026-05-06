import queue
import subprocess
import threading
import time
import objc
from Foundation import NSObject, NSTimer

from constants import LOGGER


class _TimerProxy(NSObject):
    """Bridges NSTimer selector-based callback into a plain Python callable."""

    def initWithCallback_(self, callback):
        self = objc.super(_TimerProxy, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    def fire_(self, timer):
        self._callback()


class BackgroundProcess:
    """
    A wrapper around a subprocess.Popen object to manage its lifecycle,
    poll the process health and provide a clean way to terminate background
    tasks like the server.
    """

    def __init__(self, process):
        self.process = process
        self.active = True
        self._timer = None
        self._proxy = None
        LOGGER.info(f"BackgroundProcess created with PID: {process.pid}")

    def is_running(self):
        """Checks if the process is still active."""
        return self.process.poll() is None

    def start_health_check(self, interval=2.0, on_terminated=None):
        """
        Polls the process every interval seconds on the main run loop.
        Calls on_terminated(self) once if the process is no longer alive
        and stops polling.
        """
        if self._timer is not None:
            return  # already polling

        def tick():
            if not self.is_running() and self.active:
                LOGGER.warning(
                    f"BackgroundProcess {self.process.pid} died "
                    f"(rc={self.process.returncode})"
                )
                self.stop_health_check()
                if on_terminated is not None:
                    on_terminated(self)

        self._proxy = _TimerProxy.alloc().initWithCallback_(tick)
        self._timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            interval, self._proxy, "fire:", None, True
        )

    def stop_health_check(self):
        if self._timer is not None:
            self._timer.invalidate()
            self._timer = None
        self._proxy = None

    def stop(self):
        """Terminates the process, falling back to kill if necessary."""
        self.stop_health_check()
        if self.is_running():
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.active = False


class ProcessManager:
    """
    Handles communication with shell processes. Uses a dedicated reader thread
    to prevent the application from hanging while waiting for command output.
    """

    def __init__(self, command, timeout=2.0):
        self.command = command
        self.timeout = timeout
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        self.output_queue = queue.Queue()
        # Thread to drain stdout and prevent buffer bloat
        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()

    def _read_output(self):
        """Continuously reads lines from the process stdout and puts them in a queue."""
        try:
            for line in self.process.stdout:
                self.output_queue.put(line.rstrip())
        except Exception as e:
            LOGGER.error(f"Error reading output: {e}")
            self.output_queue.put(f"[Error reading output: {e}]")

    def send(self, command):
        """Sends a string command to the process stdin and waits for output until timeout."""
        if self.process.poll() is not None:
            raise RuntimeError("Process has terminated")

        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            raise RuntimeError("Process has terminated")

        output = []
        start_time = time.time()

        # Gather output lines until the queue is empty or timeout is reached
        while time.time() - start_time < self.timeout:
            try:
                line = self.output_queue.get(timeout=0.1)
                output.append(line)
                start_time = time.time()
            except queue.Empty:
                pass

        return output

    def execute_background(self, command):
        """Starts a process in the background without waiting for its completion."""
        cmd_list = command.split() if isinstance(command, str) else command

        bg_process = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )

        return BackgroundProcess(bg_process)

    def close(self):
        """Closes process pipes and terminates the process."""
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class Controller:
    @staticmethod
    def execute_command(cmd: str):
        """
        Static helper to run a command through a bash shell.
        Logs the result and handles exceptions.
        """
        LOGGER.info(f"Executing command: {cmd}")
        try:
            with ProcessManager(['bash']) as pm:
                result = pm.send(cmd)
                LOGGER.info(f"Command result: {result}")
        except Exception as e:
            LOGGER.error(f"Error executing command: {e}")
