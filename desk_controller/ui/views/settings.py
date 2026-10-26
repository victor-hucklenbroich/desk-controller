import Cocoa
import objc
from AppKit import (
    NSView, NSColor, NSTextField, NSSlider, NSImageView,
    NSImageScaleAxesIndependently,
)
from Foundation import NSObject, NSMakeRect

import constants
from constants import LOGGER
from control import config
from ui import theme


SETTINGS_WIDTH = 390
SETTINGS_HEIGHT = 330

# Preset height sprite, sized to the sprite's aspect ratio
ICON_W = 22
ICON_H = 18


class SettingsView(NSView):
    """
    UI View for editing user preferences (desk UUID, sit/stand presets).
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
        self.addSubview_(self._fieldLabel_("Desk address", 294))
        self.uuid_field = self._textField_(268)
        self.uuid_field.setPlaceholderString_("AA:AA:AA:AA:AA:AA")
        self.uuid_field.setStringValue_(constants.CONFIG_UUID)
        self.addSubview_(self.uuid_field)

        self.auto_connect_checkbox = self._checkbox_(
            "Automatically connect to desk", 231, constants.CONFIG_AUTO_CONNECT,
            width=254,
        )
        self.addSubview_(self.auto_connect_checkbox)

        # Disconnect button, only enabled while a desk is connected
        self.disconnect_button = Cocoa.NSButton.alloc().initWithFrame_(
            NSMakeRect(282, 226, 88, 30)
        )
        self.disconnect_button.setTitle_("Disconnect")
        self.disconnect_button.setBezelStyle_(1)
        self.disconnect_button.setTarget_(self)
        self.disconnect_button.setAction_("disconnect:")
        self.addSubview_(self.disconnect_button)
        self.refreshConnectionState()

        # Sit preset
        self.addSubview_(self._fieldLabel_("\"Sit\" preset height", 198))
        self.sit_slider = self._presetSlider_(174, constants.CONFIG_SIT)
        self.addSubview_(self.sit_slider)
        self.sit_value = self._valueLabel_(176, constants.CONFIG_SIT)
        self.addSubview_(self.sit_value)
        self.sit_icon = self._presetIcon_(175, constants.CONFIG_SIT)
        self.addSubview_(self.sit_icon)

        # Stand preset
        self.addSubview_(self._fieldLabel_("\"Stand\" preset height", 138))
        self.stand_slider = self._presetSlider_(114, constants.CONFIG_STAND)
        self.addSubview_(self.stand_slider)
        self.stand_value = self._valueLabel_(116, constants.CONFIG_STAND)
        self.addSubview_(self.stand_value)
        self.stand_icon = self._presetIcon_(115, constants.CONFIG_STAND)
        self.addSubview_(self.stand_icon)

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
    def _fieldLabel_(self, text, y):
        """Builds a dimmed caption label positioned above a text field."""
        return theme.label(
            text, NSMakeRect(20, y, 350, 16),
            size=12, color=NSColor.secondaryLabelColor(),
        )

    @objc.python_method
    def _textField_(self, y):
        """Builds an editable text field. The text colour is left at its
        default so the field tracks light/dark appearance."""
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y, 350, 24))
        field.setBezeled_(True)
        field.setDrawsBackground_(True)
        field.setEditable_(True)
        field.setSelectable_(True)
        field.setFont_(theme.font(13))
        field.setAlignment_(theme.ALIGN_LEFT)
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
        if sender is self.sit_slider:
            value, icon = self.sit_value, self.sit_icon
        elif sender is self.stand_slider:
            value, icon = self.stand_value, self.stand_icon
        else:
            return
        value.setStringValue_(self._formatHeight(sender.doubleValue()))
        icon.setImage_(constants.icon_frame(sender.doubleValue()))

    def apply_(self, sender):
        """Persists the entered preferences to config.yaml and runtime constants."""
        uuid = self.uuid_field.stringValue().strip()
        sit = int(round(self.sit_slider.doubleValue()))
        stand = int(round(self.stand_slider.doubleValue()))
        show_height = self.show_height_checkbox.state() == 1
        auto_connect = self.auto_connect_checkbox.state() == 1

        uuid_changed = uuid != "" and uuid != constants.CONFIG_UUID
        auto_connect_enabled = auto_connect and not constants.CONFIG_AUTO_CONNECT
        LOGGER.info(
            f"Saving settings (uuid_changed={uuid_changed}, sit={sit}, "
            f"stand={stand}, show_height={show_height}, auto_connect={auto_connect})"
        )
        config.ConfigParser.update(uuid, sit, stand, show_height, auto_connect)

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
