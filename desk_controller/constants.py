import logging
import os

# --- Static Constants ---
ICON: str = "|‾‾‾|"
VERSION: str = "1.0.0"
LINAK: str = "/opt/homebrew/anaconda3/bin/linak-controller"
MOVE_CMD: str = LINAK + " --forward --move-to "


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
