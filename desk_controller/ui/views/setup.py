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

from constants import LOGGER
from ui import window


class InitialSetupView(NSView):
    """
    UI View for communicating connection issues with the local server.
    """

    def initWithApp_(self, app):
        self = objc.super(InitialSetupView, self).init()
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
        # Welcome label
        welcome_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(38, 71, 295, 30)
        )
        welcome_label.setStringValue_("Welcome to DeskController!")
        welcome_label.setBezeled_(False)
        welcome_label.setDrawsBackground_(False)
        welcome_label.setEditable_(False)
        welcome_label.setSelectable_(False)
        welcome_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.9))
        welcome_label.setFont_(NSFont.systemFontOfSize_(15))
        welcome_label.setAlignment_(1)
        self.addSubview_(welcome_label)

        # UUID field
        self.uuid_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(12, 46, 338, 25)
        )
        self.uuid_field.setPlaceholderString_("Please enter the UUID of your desk, then press 'Connect'")
        self.uuid_field.setBezeled_(True)
        self.uuid_field.setDrawsBackground_(True)
        self.uuid_field.setEditable_(True)
        self.uuid_field.setSelectable_(True)
        self.uuid_field.setTextColor_(NSColor.whiteColor())
        self.uuid_field.setFont_(NSFont.systemFontOfSize_(12))
        self.uuid_field.setAlignment_(0)
        self.addSubview_(self.uuid_field)

        # Retry button
        retry_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(154, 5, 75, 27))
        retry_button.setTitle_("Connect")
        retry_button.setBezelStyle_(8)
        retry_button.setTarget_(self)
        retry_button.setAction_("connect:")
        self.addSubview_(retry_button)

        # App Quit button
        quit_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(295, 5, 57, 27))
        quit_button.setTitle_("Quit")
        quit_button.setBezelStyle_(8)
        quit_button.setTarget_(self)
        quit_button.setAction_("quitApp:")
        self.addSubview_(quit_button)

    def viewDidMoveToWindow(self):
        if self.window() is not None:
            NSApp.activateIgnoringOtherApps_(True)
            self.window().makeKeyWindow()
            self.window().makeFirstResponder_(self.uuid_field)
            self.performSelector_withObject_afterDelay_(
                "focusTextField", None, 0.1
            )

    def focusTextField(self):
        self.window().makeKeyWindow()
        self.window().makeFirstResponder_(self.uuid_field)

    def drawRect_(self, rect):
        window.draw_rect(rect)

    def connect_(self, sender):
        uuid = self.uuid_field.stringValue()
        LOGGER.info(f"user provided UUID: {uuid}")
        LOGGER.debug("Trying initial setup connection")
        # TODO write uuid to config.yaml
        self.app.server.retry()
        self.app.checkAndUpdatePopover()

    def quitApp_(self, sender):
        """Shuts down the controller server and exits the application."""
        LOGGER.debug("Quit button pressed")
        self.app.quit()
