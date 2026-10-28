import Cocoa
import objc
from AppKit import (
    NSView, NSColor, NSTextField, NSSlider, NSImageView, NSFormatter,
    NSImageScaleAxesIndependently,
)
from Foundation import NSObject, NSMakeRect

import constants
from constants import LOGGER
from control import config
from ui import theme


SETTINGS_WIDTH = 390
SETTINGS_HEIGHT = 350

# Preset height sprite, sized to the sprite's aspect ratio
ICON_W = 22
ICON_H = 18

# Preset name field, inline after its caption and as wide as the popover button
PRESET_CAPTION_W = 50
PRESET_NAME_X = 20 + PRESET_CAPTION_W + 2


class PresetNameFormatter(NSFormatter):
    """Rejects edits to a preset name field that would make the name too wide
    for its button in the popover."""

    def stringForObjectValue_(self, value):
        return value if isinstance(value, str) else ""

    def getObjectValue_forString_errorDescription_(self, value, string, error):
        return True, string, None

    def isPartialStringValid_newEditingString_errorDescription_(self, partial, new, error):
        return theme.fits_preset_button(partial), None, None


class SettingsView(NSView):
    """
    UI View for editing user preferences (desk UUID, presets).
    Content view of a standard titled window.
    """

    def initWithApp_(self, app):
        self = objc.super(SettingsView, self).init()
        if self is None:
            return None

        self.app = app
        frame = NSMakeRect(0, 0, SETTINGS_WIDTH, SETTINGS_HEIGHT)
        self = self.initWithFrame_(frame)
        self.buildUI()

        return self

    def buildUI(self):
        """Initializes and positions all UI elements within the settings window."""
        # Desk address
        self.addSubview_(self._fieldLabel_("Desk address", 314))
        self.uuid_field = self._textField_(288)
        self.uuid_field.setPlaceholderString_("AA:AA:AA:AA:AA:AA")
        self.uuid_field.setStringValue_(constants.CONFIG_UUID)
        self.addSubview_(self.uuid_field)

        self.auto_connect_checkbox = self._checkbox_(
            "Automatically connect to desk", 251, constants.CONFIG_AUTO_CONNECT,
            width=254,
        )
        self.addSubview_(self.auto_connect_checkbox)

        # Disconnect button, only enabled while a desk is connected
        self.disconnect_button = Cocoa.NSButton.alloc().initWithFrame_(
            NSMakeRect(282, 246, 88, 30)
        )
        self.disconnect_button.setTitle_("Disconnect")
        self.disconnect_button.setBezelStyle_(1)
        self.disconnect_button.setTarget_(self)
        self.disconnect_button.setAction_("disconnect:")
        self.addSubview_(self.disconnect_button)
        self.refreshConnectionState()

        # Preset 1
        self.addSubview_(self._fieldLabel_("Preset:", 214, width=PRESET_CAPTION_W))
        self.preset_1_name = self._presetNameField_(
            210, constants.CONFIG_PRESET_1_NAME, constants.DEFAULT_PRESET_1_NAME
        )
        self.addSubview_(self.preset_1_name)
        self.preset_1_slider = self._presetSlider_(184, constants.CONFIG_PRESET_1)
        self.addSubview_(self.preset_1_slider)
        self.preset_1_value = self._valueLabel_(186, constants.CONFIG_PRESET_1)
        self.addSubview_(self.preset_1_value)
        self.preset_1_icon = self._presetIcon_(185, constants.CONFIG_PRESET_1)
        self.addSubview_(self.preset_1_icon)

        # Preset 2
        self.addSubview_(self._fieldLabel_("Preset:", 144, width=PRESET_CAPTION_W))
        self.preset_2_name = self._presetNameField_(
            140, constants.CONFIG_PRESET_2_NAME, constants.DEFAULT_PRESET_2_NAME
        )
        self.addSubview_(self.preset_2_name)
        self.preset_2_slider = self._presetSlider_(114, constants.CONFIG_PRESET_2)
        self.addSubview_(self.preset_2_slider)
        self.preset_2_value = self._valueLabel_(116, constants.CONFIG_PRESET_2)
        self.addSubview_(self.preset_2_value)
        self.preset_2_icon = self._presetIcon_(115, constants.CONFIG_PRESET_2)
        self.addSubview_(self.preset_2_icon)

        # Menu bar height readout toggle
        self.show_height_checkbox = self._checkbox_(
            "Show desk height in menu bar", 72, constants.CONFIG_SHOW_HEIGHT
        )
        self.addSubview_(self.show_height_checkbox)

        # Version label
        self.addSubview_(theme.label(
            constants.VERSION, NSMakeRect(20, 22, 120, 16),
            size=12, color=NSColor.tertiaryLabelColor(),
        ))

        # Cancel button
        cancel_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(186, 18, 88, 30))
        cancel_button.setTitle_("Cancel")
        cancel_button.setBezelStyle_(1)
        cancel_button.setKeyEquivalent_("\x1b")  # Escape
        cancel_button.setTarget_(self)
        cancel_button.setAction_("cancel:")
        self.addSubview_(cancel_button)

        # Apply button
        apply_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(282, 18, 88, 30))
        apply_button.setTitle_("Apply")
        apply_button.setBezelStyle_(1)
        apply_button.setKeyEquivalent_("\r")
        apply_button.setTarget_(self)
        apply_button.setAction_("apply:")
        self.addSubview_(apply_button)

    @objc.python_method
    def _fieldLabel_(self, text, y, width=350):
        """Builds a dimmed caption label positioned above a text field."""
        return theme.label(
            text, NSMakeRect(20, y, width, 16),
            size=12, color=NSColor.secondaryLabelColor(),
        )

    @objc.python_method
    def _textField_(self, y, x=20, width=350):
        """Builds an editable text field. The text colour is left at its
        default so the field tracks light/dark appearance."""
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, width, 24))
        field.setBezeled_(True)
        field.setDrawsBackground_(True)
        field.setEditable_(True)
        field.setSelectable_(True)
        field.setFont_(theme.font(13))
        field.setAlignment_(theme.ALIGN_LEFT)
        return field

    @objc.python_method
    def _presetNameField_(self, y, name, default):
        """Builds the name field of a preset, limited to names that fit on its
        popover button. A name already too wide (e.g. hand-edited in the
        config) is shortened first, so the field can still be edited."""
        field = self._textField_(y, x=PRESET_NAME_X, width=theme.PRESET_BUTTON_WIDTH)
        field.setPlaceholderString_(default)
        field.setFormatter_(PresetNameFormatter.alloc().init())
        while not theme.fits_preset_button(name):
            name = name[:-1]
        field.setStringValue_(name)
        return field

    @objc.python_method
    def _checkbox_(self, title, y, checked, width=350):
        """Builds a checkbox for a boolean preference."""
        checkbox = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(20, y, width, 20))
        checkbox.setButtonType_(3)  # NSButtonTypeSwitch (checkbox)
        checkbox.setTitle_(title)
        checkbox.setFont_(theme.font(13))
        checkbox.setState_(1 if checked else 0)
        return checkbox

    @objc.python_method
    def _presetSlider_(self, y, value):
        """Builds a preset height slider spanning the desk's travel range,
        mirroring the main popover control. Continuous so the value indicator
        tracks the handle live while dragging."""
        slider = NSSlider.alloc().initWithFrame_(NSMakeRect(20, y, 254, 20))
        slider.setMinValue_(constants.MIN_HEIGHT)
        slider.setMaxValue_(constants.MAX_HEIGHT)
        slider.setDoubleValue_(value)
        slider.setContinuous_(True)
        slider.setTarget_(self)
        slider.setAction_("sliderChanged:")
        return slider

    @objc.python_method
    def _valueLabel_(self, y, value):
        """Builds the numeric readout shown next to a preset slider."""
        return theme.label(
            self._formatHeight(value), NSMakeRect(286, y, 58, 16),
            size=13, weight=theme.WEIGHT_SEMIBOLD, align=theme.ALIGN_RIGHT,
        )

    @objc.python_method
    def _presetIcon_(self, y, value):
        """Builds the desk sprite shown next to a preset readout, picking the
        same frame the menu bar icon shows at that height."""
        icon = NSImageView.alloc().initWithFrame_(
            NSMakeRect(370 - ICON_W, y, ICON_W, ICON_H)
        )
        icon.setImageScaling_(NSImageScaleAxesIndependently)
        icon.setContentTintColor_(NSColor.secondaryLabelColor())
        icon.setImage_(constants.icon_frame(value))
        return icon

    @objc.python_method
    def _formatHeight(self, cm):
        return f"{int(round(cm))} cm"

    def viewDidMoveToWindow(self):
        # The window is brought to the front by the app.
        if self.window() is not None:
            self.window().makeFirstResponder_(self.uuid_field)

    @objc.python_method
    def refreshConnectionState(self):
        """Greys out Disconnect while no desk is connected."""
        self.disconnect_button.setEnabled_(self.app.desk.is_healthy())

    def sliderChanged_(self, sender):
        """Live-updates the value indicator and sprite as a preset slider is dragged."""
        if sender is self.preset_1_slider:
            value, icon = self.preset_1_value, self.preset_1_icon
        elif sender is self.preset_2_slider:
            value, icon = self.preset_2_value, self.preset_2_icon
        else:
            return
        value.setStringValue_(self._formatHeight(sender.doubleValue()))
        icon.setImage_(constants.icon_frame(sender.doubleValue()))

    def apply_(self, sender):
        """Persists the entered preferences to config.yaml and runtime constants."""
        uuid = self.uuid_field.stringValue().strip()
        preset_1 = int(round(self.preset_1_slider.doubleValue()))
        preset_2 = int(round(self.preset_2_slider.doubleValue()))
        preset_1_name = self.preset_1_name.stringValue()
        preset_2_name = self.preset_2_name.stringValue()
        show_height = self.show_height_checkbox.state() == 1
        auto_connect = self.auto_connect_checkbox.state() == 1

        uuid_changed = uuid != "" and uuid != constants.CONFIG_UUID
        auto_connect_enabled = auto_connect and not constants.CONFIG_AUTO_CONNECT
        LOGGER.info(
            f"Saving settings (uuid_changed={uuid_changed}, "
            f"preset_1={preset_1_name!r}@{preset_1}, preset_2={preset_2_name!r}@{preset_2}, "
            f"show_height={show_height}, auto_connect={auto_connect})"
        )
        config.ConfigParser.update(
            uuid, preset_1=preset_1, preset_2=preset_2,
            preset_1_name=preset_1_name, preset_2_name=preset_2_name,
            show_height=show_height, auto_connect=auto_connect,
        )

        self.app.closeSettings()

        if uuid_changed or (auto_connect_enabled and not self.app.desk.is_healthy()):
            self.app.desk.retry()
        self.app.checkAndUpdatePopover()
        self.app.refreshStatusItem()

    def disconnect_(self, sender):
        """Drops the desk connection right away, until the user connects again."""
        LOGGER.debug("Disconnect button pressed")
        self.app.desk.disconnect()

    def cancel_(self, sender):
        """Discards changes and closes the settings window."""
        LOGGER.debug("Settings cancelled")
        self.app.closeSettings()
