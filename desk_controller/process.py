import queue
import subprocess
import threading
import time

from constants import LOGGER


class Controller:
    @staticmethod
    def start_background_server(command):
        """Static helper to initialize the linak-controller server process."""
        cmd_list = command.split() if isinstance(command, str) else command

        bg_process = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )
        return BackgroundProcess(bg_process)

    @staticmethod
    def execute(cmd: str):
        """
        Static helper to run a one-off command through a bash shell.
        Logs the result and handles exceptions.
        """
        LOGGER.info(f"Executing command: {cmd}")
        try:
            with ProcessManager(['bash']) as pm:
                result = pm.send(cmd)
                LOGGER.info(f"Command result: {result}")
        except Exception as e:
            LOGGER.error(f"Error executing command: {e}")


class BackgroundProcess:
    """
    A wrapper around a subprocess.Popen object to manage its lifecycle
    and provide a clean way to terminate background tasks like the server.
    """

    def __init__(self, process):
        self.process = process
        self.active = True
        LOGGER.info(f"BackgroundProcess created with PID: {process.pid}")

    def is_running(self):
        """Checks if the process is still active."""
        return self.process.poll() is None

    def stop(self):
        """Gracefully terminates the process, falling back to kill if necessary."""
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
