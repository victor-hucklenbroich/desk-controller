import os

import yaml

import constants
from constants import LOGGER


class ConfigParser:
    @staticmethod
    def parse() -> dict:
        """The current desk's settings file."""
        return constants.read_yaml(constants.desk_file(constants.CONFIG_UUID))

    @staticmethod
    def select_desk(address: str):
        """Makes the desk with this address the current one and loads its
        settings, giving it a file with the defaults the first time."""
        address = address.strip()
        if not address or os.sep in address:
            LOGGER.warning(f"Not a desk address: {address!r}")
            return
        path = constants.desk_file(address)
        if not os.path.exists(path):
            ConfigParser._write(path, constants.DEFAULT_DESK_CONFIG)
            LOGGER.info(f"Created settings for desk {address}")
        ConfigParser._write(constants.CONFIG_FILE_PATH, {"desk": address})
        constants.load_desk(address)

    @staticmethod
    def update(preset_1: int = -1, preset_2: int = -1,
               preset_1_name: str = None, preset_2_name: str = None,
               show_height: bool = None, auto_connect: bool = None):
        """Changes the current desk's settings and saves them to its file."""
        if preset_1 != -1:
            constants.CONFIG_PRESET_1 = preset_1
        if preset_2 != -1:
            constants.CONFIG_PRESET_2 = preset_2
        if preset_1_name is not None:
            constants.CONFIG_PRESET_1_NAME = constants.preset_name(
                preset_1_name, constants.DEFAULT_PRESET_1_NAME
            )
        if preset_2_name is not None:
            constants.CONFIG_PRESET_2_NAME = constants.preset_name(
                preset_2_name, constants.DEFAULT_PRESET_2_NAME
            )
        if show_height is not None:
            constants.CONFIG_SHOW_HEIGHT = show_height
        if auto_connect is not None:
            constants.CONFIG_AUTO_CONNECT = auto_connect

        config = ConfigParser.parse()
        config["presets"] = {
            "preset_1": {
                "name": str(constants.CONFIG_PRESET_1_NAME),
                "height": int(constants.CONFIG_PRESET_1) * 10,
            },
            "preset_2": {
                "name": str(constants.CONFIG_PRESET_2_NAME),
                "height": int(constants.CONFIG_PRESET_2) * 10,
            },
        }
        config["show_height"] = bool(constants.CONFIG_SHOW_HEIGHT)
        config["auto_connect"] = bool(constants.CONFIG_AUTO_CONNECT)
        ConfigParser._write(constants.desk_file(constants.CONFIG_UUID), config)
        LOGGER.info(f"Saved the settings of desk {constants.CONFIG_UUID}")

    @staticmethod
    def update_max_height(max_height_mm: int):
        config = ConfigParser.parse()
        config["max_height"] = int(max_height_mm)
        ConfigParser._write(constants.desk_file(constants.CONFIG_UUID), config)
        LOGGER.info(f"Persisted learned max height of {max_height_mm}mm")

    @staticmethod
    def _write(path: str, config: dict):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as out:
            yaml.safe_dump(config, out, default_flow_style=False)
