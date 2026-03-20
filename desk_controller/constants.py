import logging
import os
import sys

from pathlib import Path

from AppKit import NSImage, NSSize, NSFont


# --- Base path ---
if getattr(sys, 'frozen', False):
    base_path = Path(sys._MEIPASS)
else:
    base_path = Path(os.path.dirname(__file__)).parent

# --- Static Constants ---
VERSION: str = "1.0.0"
MIN_HEIGHT = 63
MAX_HEIGHT = 127
LINAK: str = "/opt/homebrew/anaconda3/bin/linak-controller"
MOVE_CMD: str = LINAK + " --forward --move-to "

# --- UI Constants ---
ICON_SIZE = 22
ICON_SPRITES = []
for i in range(15):
    icon_path = os.path.join(base_path, "assets", "sprites", f"icon_{i}.png")
    icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
    icon.setSize_(NSSize(ICON_SIZE, ICON_SIZE))
    icon.setTemplate_(True)
    ICON_SPRITES.append(icon)

MONO_FONT = NSFont.monospacedDigitSystemFontOfSize_weight_(13, 0)

# --- Logging Configuration ---
log_dir = os.path.expanduser("~/Library/Logs")
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
