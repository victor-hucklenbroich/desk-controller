import Cocoa
import objc
from AppKit import NSApp, NSView, NSColor, NSTextField
from Foundation import NSObject, NSMakeRect

import constants
from constants import LOGGER
from control import config
from ui import window
from ui import theme


class InitialSetupView(NSView):
    """
    Onboarding view shown before a desk address has been configured.
    """

    def initWithApp_(self, app):
        self = objc.super(InitialSetupView, self).init()
        if self is None:
            return None

        self.app = app
        frame = NSMakeRect(0, 0, theme.POPOVER_WIDTH, theme.POPOVER_HEIGHT)
        self = self.initWithFrame_(frame)
        self.buildUI()

        return self

    def buildUI(self):
        """Initializes and positions all UI elements within the popover."""
        pad = theme.PAD
        width = theme.POPOVER_WIDTH
        inner = width - 2 * pad

        # Title + subtitle
        self.addSubview_(theme.label(
            "Welcome to DeskController", NSMakeRect(pad, 150, inner, 22),
            size=16, weight=theme.WEIGHT_SEMIBOLD, align=theme.ALIGN_CENTER,
        ))
        self.addSubview_(theme.label(
            "Enter your desk's Bluetooth address to get started",
            NSMakeRect(pad, 128, inner, 18),
            size=12, color=NSColor.secondaryLabelColor(), align=theme.ALIGN_CENTER,
        ))

        # UUID field
        self.uuid_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(pad, 90, inner, 24)
        )
        self.uuid_field.setPlaceholderString_("AA:AA:AA:AA:AA:AA")
        self.uuid_field.setBezeled_(True)
        self.uuid_field.setBezelStyle_(1)  # rounded bezel
        self.uuid_field.setDrawsBackground_(True)
        self.uuid_field.setEditable_(True)
        self.uuid_field.setSelectable_(True)
        self.uuid_field.setFont_(theme.font(12))
        self.uuid_field.setAlignment_(theme.ALIGN_CENTER)
        self.addSubview_(self.uuid_field)

        # Connect button (primary, default action)
        connect_button = Cocoa.NSButton.alloc().initWithFrame_(
            NSMakeRect((width - 120) / 2, 48, 120, 30)
        )
        connect_button.setTitle_("Connect")
        connect_button.setBezelStyle_(1)
        connect_button.setKeyEquivalent_("\r")
        connect_button.setTarget_(self)
        connect_button.setAction_("connect:")
        self.addSubview_(connect_button)

        # Footer: version + quit
        self.addSubview_(theme.label(
            constants.VERSION, NSMakeRect(pad, 13, 120, 16),
            size=11, color=NSColor.tertiaryLabelColor(),
        ))
        self.addSubview_(window.make_quit_button(
            self, NSMakeRect(width - pad - 24, 11, 24, 24)
        ))

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

    def connect_(self, sender):
        uuid = self.uuid_field.stringValue()
        LOGGER.info(f"user provided UUID: {uuid}")
        LOGGER.debug("Trying initial setup connection")
        config.ConfigParser.update(uuid)
        self.app.desk.retry()
        self.app.checkAndUpdatePopover()

    def quitApp_(self, sender):
        """Shuts down the controller server and exits the application."""
        LOGGER.debug("Quit button pressed")
        self.app.quit()
