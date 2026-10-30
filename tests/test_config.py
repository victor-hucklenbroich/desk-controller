import pytest
import yaml

import constants
from control.config import ConfigParser


@pytest.mark.parametrize("raw, expected", [
    (None, "Sit"),
    ("  Standing\n desk\t", "Standing desk"),
    ("\x00\x07", "Sit"),
])
def test_preset_name_is_flattened_to_a_single_line(raw, expected):
    assert constants.preset_name(raw, "Sit") == expected


def test_presets_from_legacy_config_still_load(monkeypatch):
    # Before presets could be renamed, their heights were keyed by "sit"/"stand"
    monkeypatch.setattr(constants, "_presets", {"sit": 700, "stand": 1200})
    assert constants._preset("preset_2", "stand", 1240, "Stand") == (120, "Stand")


def test_saved_settings_read_back_and_keep_other_keys(config_file, monkeypatch):
    config_file.write_text(yaml.safe_dump({"presets": {"sit": 700}, "base_height": 640}))

    ConfigParser.update(preset_1=72, preset_1_name="Low")

    saved = ConfigParser.parse()
    assert saved["base_height"] == 640  # not managed by the settings window
    monkeypatch.setattr(constants, "_presets", saved["presets"])
    assert constants._preset("preset_1", "sit", 750, "Sit") == (72, "Low")
