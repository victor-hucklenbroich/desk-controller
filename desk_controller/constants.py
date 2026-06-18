import logging
import os
import shutil
import subprocess
import sys
import time

import yaml

from pathlib import Path

from AppKit import NSImage, NSSize, NSFont


# --- Paths ---
if getattr(sys, 'frozen', False):
    base_path = Path(sys._MEIPASS)
else:
    base_path = Path(os.path.dirname(__file__)).parent

LIBRARY_PATH = os.path.expanduser("~/Library/")
CONFIG_FILE_PATH = os.path.join(LIBRARY_PATH, "Application Support", "linak-controller","config.yaml")


# --- Logging Configuration ---
log_dir = os.path.join(LIBRARY_PATH, "Logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "DeskController.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
LOGGER = logging.getLogger(__name__)

def _find_linak_controller() -> str:
    for path in ("/opt/homebrew/bin/linak-controller", # Apple Silicon
                 "/usr/local/bin/linak-controller"): # Intel
        if os.path.exists(path):
            return path
    return shutil.which("linak-controller") or ""

LINAK_PATH = _find_linak_controller()


# --- Static Constants ---
VERSION: str = "v1.0.0"
MIN_HEIGHT: int = 63
MAX_HEIGHT: int = 127
FAILURE_MARKERS: tuple = ("Traceback", "Something unexpected went wrong")

# --- Preference constants ---
if not os.path.exists(CONFIG_FILE_PATH):
    LOGGER.warning("config.yaml not found, creating default one")
    subprocess.Popen((LINAK_PATH, "--config"), stdin=subprocess.PIPE, text=True)
    time.sleep(0.5)

with open(CONFIG_FILE_PATH) as stream:
    # Initial config parsing (before ConfigParser is fully initialized)
    try:
        CONFIG = yaml.safe_load(stream)
        CONFIG_SIT: int = CONFIG["favourites"]["sit"]
        CONFIG_STAND: int = CONFIG["favourites"]["stand"]
    except yaml.YAMLError as e:
        CONFIG_SIT: int = 750
        CONFIG_STAND: int = 1240
        LOGGER.warning(e)

PLACEHOLDER_UUID: str = "AA:AA:AA:AA:AA:AA"
CONFIG_UUID: str = CONFIG["mac_address"]
CONFIG_SIT = int(CONFIG_SIT / 10)
CONFIG_STAND = int(CONFIG_STAND / 10)


# Local server constants
SERVER_HOST: str = CONFIG.get("server_address", "127.0.0.1") if CONFIG else "127.0.0.1"
SERVER_PORT: int = int(CONFIG.get("server_port", 9123)) if CONFIG else 9123
MAX_RECONNECT_FAILURES: int = 3
HEALTH_CHECK_INTERVAL: float = 5.0


# --- UI Constants ---
ICON_SIZE = 22
ICON_FRAMES = []
for i in range(15):
    icon_path = os.path.join(base_path, "assets", "sprites", f"icon_{i}.png")
    icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
    icon.setSize_(NSSize(ICON_SIZE, ICON_SIZE))
    icon.setTemplate_(True)
    ICON_FRAMES.append(icon)
SPINNER_FRAMES = ["◴", "◷", "◶", "◵"]

MONO_FONT = NSFont.monospacedDigitSystemFontOfSize_weight_(13, 0)
