import Cocoa
import objc
from AppKit import NSView, NSColor, NSTextField, NSSlider
from Foundation import NSObject, NSMakeRect

import constants
from constants import LOGGER
from control import config
from ui import theme


SETTINGS_WIDTH = 390
SETTINGS_HEIGHT = 324


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
        self.addSubview_(self._fieldLabel_("Desk address", 288))
        self.uuid_field = self._textField_(262)
        self.uuid_field.setPlaceholderString_("AA:AA:AA:AA:AA:AA")
        self.uuid_field.setStringValue_(constants.CONFIG_UUID)
        self.addSubview_(self.uuid_field)

        # Automatic (re)connection toggle
        self.auto_connect_checkbox = self._checkbox_(
            "Automatically connect to desk", 232, constants.CONFIG_AUTO_CONNECT
        )
        self.addSubview_(self.auto_connect_checkbox)

        # Sit preset
        self.addSubview_(self._fieldLabel_("\"Sit\" preset height", 198))
        self.sit_slider = self._presetSlider_(174, constants.CONFIG_SIT)
        self.addSubview_(self.sit_slider)
        self.sit_value = self._valueLabel_(176, constants.CONFIG_SIT)
        self.addSubview_(self.sit_value)

        # Stand preset
        self.addSubview_(self._fieldLabel_("\"Stand\" preset height", 138))
        self.stand_slider = self._presetSlider_(114, constants.CONFIG_STAND)
        self.addSubview_(self.stand_slider)
        self.stand_value = self._valueLabel_(116, constants.CONFIG_STAND)
        self.addSubview_(self.stand_value)

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
    def _checkbox_(self, title, y, checked):
        """Builds a full-width checkbox for a boolean preference."""
        checkbox = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(20, y, 350, 20))
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
        slider = NSSlider.alloc().initWithFrame_(NSMakeRect(20, y, 280, 20))
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
            self._formatHeight(value), NSMakeRect(312, y, 58, 16),
            size=13, weight=theme.WEIGHT_SEMIBOLD, align=theme.ALIGN_RIGHT,
        )

    @objc.python_method
    def _formatHeight(self, cm):
        return f"{int(round(cm))} cm"

    def viewDidMoveToWindow(self):
        # The window is brought to the front by the app.
        if self.window() is not None:
            self.window().makeFirstResponder_(self.uuid_field)

    def sliderChanged_(self, sender):
        """Live-updates the value indicator as a preset slider is dragged."""
        if sender is self.sit_slider:
            self.sit_value.setStringValue_(self._formatHeight(sender.doubleValue()))
        elif sender is self.stand_slider:
            self.stand_value.setStringValue_(self._formatHeight(sender.doubleValue()))

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

    def cancel_(self, sender):
        """Discards changes and closes the settings window."""
        LOGGER.debug("Settings cancelled")
        self.app.closeSettings()
