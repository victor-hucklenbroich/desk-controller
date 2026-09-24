import Cocoa
import objc
from AppKit import NSView, NSColor, NSTextField
from Foundation import NSObject, NSMakeRect

import constants
from constants import LOGGER
from control import config
from ui import window
from ui import theme


class NoConnectionView(NSView):
    """
    UI View shown when the desk connection could not be established.
    """

    def initWithApp_(self, app):
        self = objc.super(NoConnectionView, self).init()
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
        height = theme.POPOVER_HEIGHT
        inner = width - 2 * pad

        # Controls: settings and quit
        self.addSubview_(window.make_settings_button(
            self, NSMakeRect(width - pad - 54, height - 38, 24, 24)
        ))
        self.addSubview_(window.make_quit_button(
            self, NSMakeRect(width - pad - 24, height - 38, 24, 24)
        ))

        # Header
        self.addSubview_(theme.label(
            "Couldn't connect to your desk", NSMakeRect(pad, 128, inner - 70, 22),
            size=16, weight=theme.WEIGHT_SEMIBOLD,
        ))
        self.addSubview_(theme.label(
            "Check the address and that Bluetooth is on",
            NSMakeRect(pad, 104, inner, 18),
            size=12, color=NSColor.secondaryLabelColor(),
        ))

        # UUID field (prefilled with the current address)
        self.uuid_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(pad, 64, inner, 24)
        )
        self.uuid_field.setPlaceholderString_("AA:AA:AA:AA:AA:AA")
        self.uuid_field.setStringValue_(constants.CONFIG_UUID)
        self.uuid_field.setBezeled_(True)
        self.uuid_field.setBezelStyle_(1)  # rounded bezel
        self.uuid_field.setDrawsBackground_(True)
        self.uuid_field.setEditable_(True)
        self.uuid_field.setSelectable_(True)
        self.uuid_field.setFont_(theme.font(12))
        self.uuid_field.setAlignment_(theme.ALIGN_CENTER)
        self.addSubview_(self.uuid_field)

        # Try again button (primary, default action)
        retry_button = Cocoa.NSButton.alloc().initWithFrame_(
            NSMakeRect((width - 120) / 2, 18, 120, 30)
        )
        retry_button.setTitle_("Try Again")
        retry_button.setBezelStyle_(1)
        retry_button.setKeyEquivalent_("\r")
        retry_button.setTarget_(self)
        retry_button.setAction_("retry:")
        self.addSubview_(retry_button)

    def openSettings_(self, sender):
        """Opens the settings window."""
        LOGGER.debug("Settings button pressed")
        self.app.openSettings()

    def retry_(self, sender):
        """Triggers user initiated server retry"""
        LOGGER.debug("Retry button pressed")
        uuid = self.uuid_field.stringValue()
        if uuid != constants.CONFIG_UUID:
            LOGGER.info(f"user updated UUID: {uuid}")
            config.ConfigParser.update(uuid)
        self.app.desk.retry()
        self.app.checkAndUpdatePopover()

    def quitApp_(self, sender):
        """Shuts down the controller server and exits the application."""
        LOGGER.debug("Quit button pressed")
        self.app.quit()
