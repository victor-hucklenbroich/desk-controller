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
from ui import window


class EstablishingConnectionView(NSView):
    """
    Intermediary UI view displayed while connecting and setting up desk connection.
    """

    def initWithApp_(self, app):
        self = objc.super(EstablishingConnectionView, self).init()
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
            NSMakeRect(38, 40, 295, 50)
        )
        error_label.setStringValue_("Connecting to your Desk...")
        error_label.setBezeled_(False)
        error_label.setDrawsBackground_(False)
        error_label.setEditable_(False)
        error_label.setSelectable_(False)
        error_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.6))
        error_label.setFont_(NSFont.systemFontOfSize_(15))
        error_label.setAlignment_(1)
        self.addSubview_(error_label)

        error_sub_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(38, 18, 295, 50)
        )
        error_sub_label.setStringValue_("Please wait")
        error_sub_label.setBezeled_(False)
        error_sub_label.setDrawsBackground_(False)
        error_sub_label.setEditable_(False)
        error_sub_label.setSelectable_(False)
        error_sub_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.6))
        error_sub_label.setFont_(NSFont.systemFontOfSize_(13))
        error_sub_label.setAlignment_(1)
        self.addSubview_(error_sub_label)

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

        # App Quit button
        quit_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(295, 5, 57, 27))
        quit_button.setTitle_("Quit")
        quit_button.setBezelStyle_(8)
        quit_button.setTarget_(self)
        quit_button.setAction_("quitApp:")
        self.addSubview_(quit_button)

    def drawRect_(self, rect):
        window.draw_rect(rect)

    def quitApp_(self, sender):
        """Shuts down the controller server and exits the application."""
        LOGGER.debug("Quit button pressed")
        self.app.quit()
