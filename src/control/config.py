import yaml

import constants
from constants import LOGGER


class ConfigParser:
    @staticmethod
    def parse() -> dict:
        with (open(constants.CONFIG_FILE_PATH) as stream):
            try:
                CONFIG = yaml.safe_load(stream)
                return CONFIG or {}
            except yaml.YAMLError as e:
                LOGGER.warning(f"Error parsing config.yaml: {e}")
                return {}

    @staticmethod
    def update(uuid: str = "", preset_1: int = -1, preset_2: int = -1,
               preset_1_name: str = None, preset_2_name: str = None,
               show_height: bool = None, auto_connect: bool = None):
        if uuid != "":
            constants.CONFIG_UUID = uuid
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
        config["mac_address"] = str(constants.CONFIG_UUID)
        # Replaces the whole section, which also drops legacy "sit"/"stand" keys
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
        with open(constants.CONFIG_FILE_PATH, 'w') as out:
            yaml.safe_dump(config, out, default_flow_style=False)
        LOGGER.info("Updated config.yaml with updated preferences")

    @staticmethod
    def update_max_height(max_height_mm: int):
        config = ConfigParser.parse()
        config["max_height"] = int(max_height_mm)
        with open(constants.CONFIG_FILE_PATH, 'w') as out:
            yaml.safe_dump(config, out, default_flow_style=False)
        LOGGER.info(f"Persisted learned max height of {max_height_mm}mm")
