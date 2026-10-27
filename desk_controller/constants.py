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
CONFIG_FILE_PATH = os.path.join(LIBRARY_PATH, "Application Support", "DeskController","config.yaml")


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
VERSION: str = "v1.4.1"
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


# --- Preference constants ---
DEFAULT_PRESET_1_NAME: str = "Sit"
DEFAULT_PRESET_2_NAME: str = "Stand"

DEFAULT_CONFIG: dict = {
    "mac_address": PLACEHOLDER_UUID,
    "presets": {
        "preset_1": {"name": DEFAULT_PRESET_1_NAME, "height": 750},
        "preset_2": {"name": DEFAULT_PRESET_2_NAME, "height": 1240},
    },
    "max_height": 1270,
    "show_height": True,
    "auto_connect": True,
}

if not os.path.exists(CONFIG_FILE_PATH):
    LOGGER.warning("config.yaml not found, creating default one")
    os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
    with open(CONFIG_FILE_PATH, "w") as out:
        yaml.safe_dump(DEFAULT_CONFIG, out, default_flow_style=False)

try:
    with open(CONFIG_FILE_PATH) as stream:
        CONFIG = yaml.safe_load(stream) or {}
except (OSError, yaml.YAMLError) as e:
    LOGGER.warning(f"Error reading config.yaml: {e}")
    CONFIG = {}


def preset_name(name, default):
    """Flattens a preset name to a single line without control characters,
    falling back to the default when nothing is left."""
    if name is None:
        return default
    name = " ".join(str(name).split())
    name = "".join(c for c in name if unicodedata.category(c) != "Cc")
    return name or default


def _preset(key, legacy_key, default_height, default_name):
    """Reads a preset as (height in cm, name). Configs from before presets
    could be renamed keyed the heights by "sit"/"stand", so those still count."""
    preset = _presets.get(key)
    if not isinstance(preset, dict):
        preset = {}
    height = int(preset.get("height", _presets.get(legacy_key, default_height)))
    return int(height / 10), preset_name(preset.get("name"), default_name)


_presets = CONFIG.get("presets") or {}
CONFIG_UUID: str = str(CONFIG.get("mac_address", PLACEHOLDER_UUID))
CONFIG_PRESET_1, CONFIG_PRESET_1_NAME = _preset("preset_1", "sit", 750, DEFAULT_PRESET_1_NAME)
CONFIG_PRESET_2, CONFIG_PRESET_2_NAME = _preset("preset_2", "stand", 1240, DEFAULT_PRESET_2_NAME)

# Whether the current desk height is shown next to the menu bar icon.
CONFIG_SHOW_HEIGHT: bool = bool(CONFIG.get("show_height", True))

CONFIG_AUTO_CONNECT: bool = bool(CONFIG.get("auto_connect", True))

# Height of the tabletop above ground at the lowest position (mm);
# read from the desk controller during connect when unset.
CONFIG_BASE_HEIGHT = CONFIG.get("base_height")
CONNECTION_TIMEOUT: float = float(CONFIG.get("connection_timeout", 10))
MOVE_COMMAND_PERIOD: float = float(CONFIG.get("move_command_period", 0.4))

if CONFIG_BASE_HEIGHT:
    MIN_HEIGHT = float(CONFIG_BASE_HEIGHT) / 10.0
MAX_HEIGHT = float(CONFIG.get("max_height", 1270)) / 10.0
if MAX_HEIGHT <= MIN_HEIGHT:
    LOGGER.warning(
        f"Nonsensical height limits in config "
        f"({MIN_HEIGHT}cm-{MAX_HEIGHT}cm); using defaults"
    )
    MIN_HEIGHT = 62.0
    MAX_HEIGHT = 127.0


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
    """Returns the desk icon sprite matching a height within the travel range."""
    last = len(ICON_FRAMES) - 1
    normalized = (height_cm - MIN_HEIGHT) / (MAX_HEIGHT - MIN_HEIGHT)
    return ICON_FRAMES[max(0, min(last, round(normalized * last)))]


SPINNER_FRAMES = ["◴", "◷", "◶", "◵"]

MONO_FONT = NSFont.monospacedDigitSystemFontOfSize_weight_(13, 0)
