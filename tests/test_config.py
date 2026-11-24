import pytest
import yaml

import constants
from control.config import ConfigParser


OTHER_DESK = "00000000-0000-4000-8000-000000000002"


@pytest.mark.parametrize("raw, expected", [
    (None, "Sit"),
    ("  Standing\n desk\t", "Standing desk"),
    ("\x00\x07", "Sit"),
])
def test_preset_name_is_flattened_to_a_single_line(raw, expected):
    assert constants.preset_name(raw, "Sit") == expected


def test_saved_settings_read_back_and_keep_other_keys(desk_file):
    desk_file.write_text(yaml.safe_dump({"base_height": 640}))

    ConfigParser.update(preset_1=72, preset_1_name="Low")

    saved = yaml.safe_load(desk_file.read_text())
    assert saved["base_height"] == 640  # not managed by the settings window
    constants.load_desk(constants.MOCK_ADDRESS)
    assert (constants.CONFIG_PRESET_1, constants.CONFIG_PRESET_1_NAME) == (72, "Low")


def test_each_desk_keeps_its_own_settings():
    ConfigParser.update(preset_1=80, show_height=False)
    ConfigParser.update_max_height(1300)

    # A desk selected for the first time starts off with the defaults
    ConfigParser.select_desk(OTHER_DESK)
    assert constants.read_yaml(constants.CONFIG_FILE_PATH) == {"desk": OTHER_DESK}
    assert constants.read_yaml(constants.desk_file(OTHER_DESK)) == constants.DEFAULT_DESK_CONFIG
    assert (constants.CONFIG_PRESET_1, constants.CONFIG_SHOW_HEIGHT, constants.MAX_HEIGHT) == (
        75, True, 127.0
    )

    ConfigParser.select_desk(constants.MOCK_ADDRESS)
    assert (constants.CONFIG_PRESET_1, constants.CONFIG_SHOW_HEIGHT, constants.MAX_HEIGHT) == (
        80, False, 130.0
    )


@pytest.mark.parametrize("address", ["", "  ", "../config"])
def test_addresses_that_cant_name_a_settings_file_are_ignored(address):
    ConfigParser.select_desk(address)

    assert constants.CONFIG_UUID == constants.MOCK_ADDRESS
    assert constants.read_yaml(constants.CONFIG_FILE_PATH) == {"desk": constants.MOCK_ADDRESS}
