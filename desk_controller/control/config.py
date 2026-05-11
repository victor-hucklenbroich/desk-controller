import time

import yaml

import constants
from constants import LOGGER


class ConfigParser:
    @staticmethod
    def parse() -> dict:
        with (open(constants.CONFIG_FILE_PATH) as stream):
            try:
                CONFIG = yaml.safe_load(stream)
                return CONFIG
            except yaml.YAMLError as e:
                LOGGER.warning(f"Error parsing config.yaml: {e}")
                return {}

    @staticmethod
    def update(uuid: str = "", sit: int = -1, stand: int = -1):
        if uuid != "":
            constants.CONFIG_UUID = uuid
        if sit != -1:
            constants.CONFIG_SIT = sit
        if stand != -1:
            constants.CONFIG_STAND = stand

        config = ConfigParser.parse()
        config["mac_address"] = str(constants.CONFIG_UUID)
        config["favourites"]["sit"] = int(constants.CONFIG_SIT)
        config["favourites"]["stand"] = int(constants.CONFIG_STAND)
        with open(constants.CONFIG_FILE_PATH, 'w') as out:
            yaml.safe_dump(config, out, default_flow_style=False)
        time.sleep(0.2)
        LOGGER.info("Updated config.yaml with updated preferences")
