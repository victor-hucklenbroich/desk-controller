import Cocoa
import objc
from AppKit import NSView, NSColor, NSTextField, NSSlider
from Foundation import NSObject, NSMakeRect

import constants
from constants import LOGGER
from control import config
from ui import theme


SETTINGS_WIDTH = 390
SETTINGS_HEIGHT = 294


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
        self.addSubview_(self._fieldLabel_("Desk address", 258))
        self.uuid_field = self._textField_(232)
        self.uuid_field.setPlaceholderString_("AA:AA:AA:AA:AA:AA")
        self.uuid_field.setStringValue_(constants.CONFIG_UUID)
        self.addSubview_(self.uuid_field)

        # Sit preset
        self.addSubview_(self._fieldLabel_("Sit preset height (cm)", 198))
        self.sit_slider = self._presetSlider_(174, constants.CONFIG_SIT)
        self.addSubview_(self.sit_slider)
        self.sit_value = self._valueLabel_(176, constants.CONFIG_SIT)
        self.addSubview_(self.sit_value)

        # Stand preset
        self.addSubview_(self._fieldLabel_("Stand preset height (cm)", 138))
        self.stand_slider = self._presetSlider_(114, constants.CONFIG_STAND)
        self.addSubview_(self.stand_slider)
        self.stand_value = self._valueLabel_(116, constants.CONFIG_STAND)
        self.addSubview_(self.stand_value)

        # Menu bar height readout toggle
        self.show_height_checkbox = Cocoa.NSButton.alloc().initWithFrame_(
            NSMakeRect(20, 72, 350, 20)
        )
        self.show_height_checkbox.setButtonType_(3)  # NSButtonTypeSwitch (checkbox)
        self.show_height_checkbox.setTitle_("Show desk height in menu bar")
        self.show_height_checkbox.setFont_(theme.font(13))
        self.show_height_checkbox.setState_(1 if constants.CONFIG_SHOW_HEIGHT else 0)
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

        # Save button
        save_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(282, 18, 88, 30))
        save_button.setTitle_("Save")
        save_button.setBezelStyle_(1)
        save_button.setKeyEquivalent_("\r")
        save_button.setTarget_(self)
        save_button.setAction_("save:")
        self.addSubview_(save_button)

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

    def save_(self, sender):
        """Persists the entered preferences to config.yaml and runtime constants."""
        uuid = self.uuid_field.stringValue().strip()
        sit = int(round(self.sit_slider.doubleValue()))
        stand = int(round(self.stand_slider.doubleValue()))
        show_height = self.show_height_checkbox.state() == 1

        uuid_changed = uuid != "" and uuid != constants.CONFIG_UUID
        LOGGER.info(
            f"Saving settings (uuid_changed={uuid_changed}, sit={sit}, "
            f"stand={stand}, show_height={show_height})"
        )
        config.ConfigParser.update(uuid, sit, stand, show_height)

        self.app.closeSettings()

        # A new UUID requires reconnecting to the new desk.
        if uuid_changed:
            self.app.desk.retry()
        self.app.checkAndUpdatePopover()
        self.app.refreshStatusItem()

    def cancel_(self, sender):
        """Discards changes and closes the settings window."""
        LOGGER.debug("Settings cancelled")
        self.app.closeSettings()
