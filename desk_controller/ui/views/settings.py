import Cocoa
import objc
from AppKit import (
    NSApplication, NSApp, NSStatusBar, NSVariableStatusItemLength,
    NSWindow, NSView, NSSlider, NSSliderCell, NSTextField, NSFont,
    NSColor, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSMenu, NSMenuItem, NSBezierPath, NSSize, NSImage,
    NSAttributedString, NSFontAttributeName
)
from Foundation import NSObject, NSMakeRect

import constants
from constants import LOGGER
from control import config
from ui import window


class SettingsView(NSView):
    """
    UI View for editing user preferences (desk UUID, sit/stand presets).
    Displayed in a standalone, centered window rather than the menu bar popover.
    """

    def initWithApp_(self, app):
        self = objc.super(SettingsView, self).init()
        if self is None:
            return None

        self.app = app
        frame = NSMakeRect(0, 0, 364, 300)
        self = self.initWithFrame_(frame)
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(12)
        self.buildUI()

        return self

    def buildUI(self):
        """Initializes and positions all UI elements within the settings window."""
        # Title
        title_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(32, 258, 300, 30)
        )
        title_label.setStringValue_("DeskController Settings")
        title_label.setBezeled_(False)
        title_label.setDrawsBackground_(False)
        title_label.setEditable_(False)
        title_label.setSelectable_(False)
        title_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.9))
        title_label.setFont_(NSFont.systemFontOfSize_(15))
        title_label.setAlignment_(1)
        self.addSubview_(title_label)

        # UUID
        self.addSubview_(self._fieldLabel_("Desk UUID", 224))
        self.uuid_field = self._textField_(199)
        self.uuid_field.setPlaceholderString_("e.g. AA:AA:AA:AA:AA:AA")
        self.uuid_field.setStringValue_(constants.CONFIG_UUID)
        self.addSubview_(self.uuid_field)

        # Sit preset
        self.addSubview_(self._fieldLabel_("Sit preset height (cm)", 164))
        self.sit_field = self._textField_(139)
        self.sit_field.setStringValue_(str(constants.CONFIG_SIT))
        self.addSubview_(self.sit_field)

        # Stand preset
        self.addSubview_(self._fieldLabel_("Stand preset height (cm)", 104))
        self.stand_field = self._textField_(79)
        self.stand_field.setStringValue_(str(constants.CONFIG_STAND))
        self.addSubview_(self.stand_field)

        # Version label
        version_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, 8, 90, 16)
        )
        version_label.setStringValue_(constants.VERSION)
        version_label.setBezeled_(False)
        version_label.setDrawsBackground_(False)
        version_label.setEditable_(False)
        version_label.setSelectable_(False)
        version_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.5))
        version_label.setFont_(NSFont.systemFontOfSize_(12))
        version_label.setAlignment_(0)
        self.addSubview_(version_label)

        # Cancel button
        cancel_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(207, 5, 70, 27))
        cancel_button.setTitle_("Cancel")
        cancel_button.setBezelStyle_(8)
        cancel_button.setKeyEquivalent_("\x1b")  # Escape
        cancel_button.setTarget_(self)
        cancel_button.setAction_("cancel:")
        self.addSubview_(cancel_button)

        # Save button
        save_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(282, 5, 70, 27))
        save_button.setTitle_("Save")
        save_button.setBezelStyle_(8)
        save_button.setKeyEquivalent_("\r")  # Return -> default action
        save_button.setTarget_(self)
        save_button.setAction_("save:")
        self.addSubview_(save_button)

    @objc.python_method
    def _fieldLabel_(self, text, y):
        """Builds a dimmed caption label positioned above a text field."""
        label = NSTextField.alloc().initWithFrame_(NSMakeRect(14, y, 240, 16))
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.6))
        label.setFont_(NSFont.systemFontOfSize_(12))
        label.setAlignment_(0)
        return label

    @objc.python_method
    def _textField_(self, y):
        """Builds an editable text field matching the app's input styling."""
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(12, y, 340, 25))
        field.setBezeled_(True)
        field.setDrawsBackground_(True)
        field.setEditable_(True)
        field.setSelectable_(True)
        field.setTextColor_(NSColor.whiteColor())
        field.setFont_(NSFont.systemFontOfSize_(12))
        field.setAlignment_(0)
        return field

    def viewDidMoveToWindow(self):
        if self.window() is not None:
            NSApp.activateIgnoringOtherApps_(True)
            self.window().makeKeyWindow()
            self.window().makeFirstResponder_(self.uuid_field)

    def drawRect_(self, rect):
        window.draw_rect(rect)

    @objc.python_method
    def _parseHeight(self, raw, fallback):
        """Parses a height (cm) entry, falling back to the current value if invalid."""
        try:
            value = int(round(float(raw.strip())))
        except (ValueError, TypeError, AttributeError):
            LOGGER.warning(f"Invalid height input '{raw}', keeping {fallback}cm")
            return fallback
        if value < constants.MIN_HEIGHT or value > constants.MAX_HEIGHT:
            LOGGER.warning(
                f"Height {value}cm out of range "
                f"({constants.MIN_HEIGHT}-{constants.MAX_HEIGHT}), keeping {fallback}cm"
            )
            return fallback
        return value

    def save_(self, sender):
        """Persists the entered preferences to config.yaml and runtime constants."""
        uuid = self.uuid_field.stringValue().strip()
        sit = self._parseHeight(self.sit_field.stringValue(), constants.CONFIG_SIT)
        stand = self._parseHeight(self.stand_field.stringValue(), constants.CONFIG_STAND)

        uuid_changed = uuid != "" and uuid != constants.CONFIG_UUID
        LOGGER.info(f"Saving settings (uuid_changed={uuid_changed}, sit={sit}, stand={stand})")
        config.ConfigParser.update(uuid, sit, stand)

        self.app.closeSettings()

        # A new UUID requires reconnecting the server to the new desk.
        if uuid_changed:
            self.app.server.retry()
        self.app.checkAndUpdatePopover()

    def cancel_(self, sender):
        """Discards changes and closes the settings window."""
        LOGGER.debug("Settings cancelled")
        self.app.closeSettings()
