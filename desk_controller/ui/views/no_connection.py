import Cocoa
import objc
from AppKit import (
    NSApplication, NSStatusBar, NSVariableStatusItemLength,
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


class NoConnectionView(NSView):
    """
    UI View for communicating connection issues with the local server.
    """

    def initWithApp_(self, app):
        self = objc.super(NoConnectionView, self).init()
        if self is None:
            return None

        self.app = app
        frame = NSMakeRect(0, 0, 364, 120)
        self = self.initWithFrame_(frame)
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(12)
        self.buildUI()

        return self

    def buildUI(self):
        """Initializes and positions all UI elements within the popover."""
        # Error label
        error_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(38, 78, 295, 30)
        )
        error_label.setStringValue_("Could not connect to your Desk!")
        error_label.setBezeled_(False)
        error_label.setDrawsBackground_(False)
        error_label.setEditable_(False)
        error_label.setSelectable_(False)
        error_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.8))
        error_label.setFont_(NSFont.systemFontOfSize_(14))
        error_label.setAlignment_(1)
        self.addSubview_(error_label)

        error_sub_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, 57, 325, 30)
        )
        error_sub_label.setStringValue_("Please check your UUID and Bluetooth connection")
        error_sub_label.setBezeled_(False)
        error_sub_label.setDrawsBackground_(False)
        error_sub_label.setEditable_(False)
        error_sub_label.setSelectable_(False)
        error_sub_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.6))
        error_sub_label.setFont_(NSFont.systemFontOfSize_(13))
        error_sub_label.setAlignment_(1)
        self.addSubview_(error_sub_label)

        # UUID field
        self.uuid_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(12, 38, 338, 25)
        )
        self.uuid_field.setPlaceholderString_("Please enter the UUID of your desk and try again")
        self.uuid_field.setStringValue_(constants.CONFIG_UUID)
        self.uuid_field.setBezeled_(True)
        self.uuid_field.setDrawsBackground_(True)
        self.uuid_field.setEditable_(True)
        self.uuid_field.setSelectable_(True)
        self.uuid_field.setTextColor_(NSColor.whiteColor())
        self.uuid_field.setFont_(NSFont.systemFontOfSize_(12))
        self.uuid_field.setAlignment_(0)
        self.addSubview_(self.uuid_field)

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

        # Retry button
        retry_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(154, 5, 75, 27))
        retry_button.setTitle_("Try again")
        retry_button.setBezelStyle_(8)
        retry_button.setTarget_(self)
        retry_button.setAction_("retry:")
        self.addSubview_(retry_button)

        # Settings button
        self.addSubview_(window.make_settings_button(self, NSMakeRect(245, 5, 33, 27)))

        # App Quit button
        quit_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(295, 5, 57, 27))
        quit_button.setTitle_("Quit")
        quit_button.setBezelStyle_(8)
        quit_button.setTarget_(self)
        quit_button.setAction_("quitApp:")
        self.addSubview_(quit_button)

    def openSettings_(self, sender):
        """Opens the settings window."""
        LOGGER.debug("Settings button pressed")
        self.app.openSettings()

    def drawRect_(self, rect):
        window.draw_rect(rect)

    def retry_(self, sender):
        """Triggers user initiated server retry"""
        LOGGER.debug("Retry button pressed")
        uuid = self.uuid_field.stringValue()
        if uuid != constants.CONFIG_UUID:
            LOGGER.info(f"user updated UUID: {uuid}")
            config.ConfigParser.update(uuid)
        self.app.server.retry()
        self.app.checkAndUpdatePopover()

    def quitApp_(self, sender):
        """Shuts down the controller server and exits the application."""
        LOGGER.debug("Quit button pressed")
        self.app.quit()
