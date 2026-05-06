import subprocess

from Foundation import NSObject, NSTimer

from constants import LOGGER
from control.process import BackgroundProcess, ProcessManager


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
