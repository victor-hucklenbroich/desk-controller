import logging
import os
import sys
import unicodedata

import yaml

from pathlib import Path

from AppKit import NSImage, NSSize, NSFont


# --- Paths ---
if getattr(sys, 'frozen', False):
    base_path = Path(sys._MEIPASS)
else:
    base_path = Path(os.path.dirname(__file__)).parent

LIBRARY_PATH = os.path.expanduser("~/Library/")
# Names the current desk by its address
CONFIG_FILE_PATH = os.path.join(LIBRARY_PATH, "Application Support", "DeskController","config.yaml")
# Each desk's settings, in a file named after its address
DESKS_PATH = os.path.join(os.path.dirname(CONFIG_FILE_PATH), "desks")


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


# --- Static Constants ---
VERSION: str = "v1.4.2"
PLACEHOLDER_UUID: str = "AA:AA:AA:AA:AA:AA"
MOCK_ADDRESS: str = "dev"

# --- Desk height limits (cm, floats for mm precision) ---
# Defaults match a typical Idasen (620-1270mm) and are refined per desk
MIN_HEIGHT: float = 62.0
MAX_HEIGHT: float = 127.0


# --- Desk connection constants ---
MAX_RECONNECT_FAILURES: int = 3
RECONNECT_DELAY: float = 2.0
WAKE_RECONNECT_DELAY: float = 2.0
HANDSHAKE_TIMEOUT: float = 15.0 # seconds
AUTO_RETRY_DELAY: float = 360.0 # seconds


# --- Desk discovery and pairing constants ---
SCAN_TIMEOUT: float = 8.0 # seconds
PAIRING_TIMEOUT: float = 30.0
PAIRING_POLL_INTERVAL: float = 0.5 # seconds


# --- Preference constants ---
DEFAULT_PRESET_1_NAME: str = "Sit"
DEFAULT_PRESET_2_NAME: str = "Stand"

# Settings a desk starts off with in its file
DEFAULT_DESK_CONFIG: dict = {
    "presets": {
        "preset_1": {"name": DEFAULT_PRESET_1_NAME, "height": 750},
        "preset_2": {"name": DEFAULT_PRESET_2_NAME, "height": 1240},
    },
    "max_height": 1270,
    "show_height": True,
    "auto_connect": True,
}


def read_yaml(path):
    """A config file's contents; empty when it's missing or can't be read."""
    try:
        with open(path) as stream:
            return yaml.safe_load(stream) or {}
    except FileNotFoundError:
        return {}
    except (OSError, yaml.YAMLError) as e:
        LOGGER.warning(f"Error reading {path}: {e}")
        return {}


def desk_file(address):
    """Path of the settings file of the desk with this address."""
    return os.path.join(DESKS_PATH, f"{address}.yaml")


def preset_name(name, default):
    """Flattens a preset name to a single line without control characters,
    falling back to the default when nothing is left."""
    if name is None:
        return default
    name = " ".join(str(name).split())
    name = "".join(c for c in name if unicodedata.category(c) != "Cc")
    return name or default


def _preset(presets, key, default_height, default_name):
    """Reads a preset as (height in cm, name)."""
    preset = presets.get(key)
    if not isinstance(preset, dict):
        preset = {}
    height = int(preset.get("height", default_height))
    return int(height / 10), preset_name(preset.get("name"), default_name)


def load_desk(address):
    """Makes the desk with this address the current one, with the settings
    from its file and defaults for any it doesn't set. None is no desk."""
    global CONFIG_UUID, CONFIG_PRESET_1, CONFIG_PRESET_1_NAME
    global CONFIG_PRESET_2, CONFIG_PRESET_2_NAME, CONFIG_SHOW_HEIGHT
    global CONFIG_AUTO_CONNECT, CONFIG_BASE_HEIGHT, CONNECTION_TIMEOUT
    global MOVE_COMMAND_PERIOD, MIN_HEIGHT, MAX_HEIGHT
    address = str(address) if address else None
    desk = read_yaml(desk_file(address)) if address else {}
    presets = desk.get("presets") or {}

    CONFIG_UUID = address or PLACEHOLDER_UUID
    CONFIG_PRESET_1, CONFIG_PRESET_1_NAME = _preset(presets, "preset_1", 750, DEFAULT_PRESET_1_NAME)
    CONFIG_PRESET_2, CONFIG_PRESET_2_NAME = _preset(presets, "preset_2", 1240, DEFAULT_PRESET_2_NAME)

    CONFIG_SHOW_HEIGHT = bool(desk.get("show_height", True))

    CONFIG_AUTO_CONNECT = bool(desk.get("auto_connect", True))

    # Height of the tabletop above ground at the lowest position (mm);
    # read from the desk controller during connect when unset.
    CONFIG_BASE_HEIGHT = desk.get("base_height")
    CONNECTION_TIMEOUT = float(desk.get("connection_timeout", 10))
    MOVE_COMMAND_PERIOD = float(desk.get("move_command_period", 0.4))

    MIN_HEIGHT = float(CONFIG_BASE_HEIGHT) / 10.0 if CONFIG_BASE_HEIGHT else 62.0
    MAX_HEIGHT = float(desk.get("max_height", 1270)) / 10.0
    if MAX_HEIGHT <= MIN_HEIGHT:
        LOGGER.warning(
            f"Nonsensical height limits in config "
            f"({MIN_HEIGHT}cm-{MAX_HEIGHT}cm); using defaults"
        )
        MIN_HEIGHT = 62.0
        MAX_HEIGHT = 127.0


load_desk(read_yaml(CONFIG_FILE_PATH).get("desk"))


# --- UI Constants ---
ICON_SIZE = 22
ICON_FRAMES = []
for i in range(15):
    icon_path = os.path.join(base_path, "assets", "sprites", f"icon_{i}.png")
    icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
    icon.setSize_(NSSize(ICON_SIZE, ICON_SIZE))
    icon.setTemplate_(True)
    ICON_FRAMES.append(icon)


def icon_frame(height_cm):
    """Returns the desk icon sprite matching a height within the travel range,
    or the lowest one while the height is unknown (None)."""
    if height_cm is None:
        return ICON_FRAMES[0]
    last = len(ICON_FRAMES) - 1
    normalized = (height_cm - MIN_HEIGHT) / (MAX_HEIGHT - MIN_HEIGHT)
    return ICON_FRAMES[max(0, min(last, round(normalized * last)))]


SPINNER_FRAMES = ["◴", "◷", "◶", "◵"]

MONO_FONT = NSFont.monospacedDigitSystemFontOfSize_weight_(13, 0)
