import objc
from AppKit import (
    NSView, NSColor, NSProgressIndicator,
    NSProgressIndicatorStyleSpinning, NSControlSizeSmall,
)
from Foundation import NSObject, NSMakeRect

import constants
from constants import LOGGER
from ui import window
from ui import theme


class EstablishingConnectionView(NSView):
    """
    Intermediary UI view displayed while connecting and setting up desk connection.
    """

    def initWithApp_(self, app):
        self = objc.super(EstablishingConnectionView, self).init()
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

        spinner = NSProgressIndicator.alloc().initWithFrame_(
            NSMakeRect((width - 20) / 2, 108, 20, 20)
        )
        spinner.setStyle_(NSProgressIndicatorStyleSpinning)
        spinner.setControlSize_(NSControlSizeSmall)
        spinner.setDisplayedWhenStopped_(False)
        spinner.startAnimation_(None)
        self.addSubview_(spinner)

        self.addSubview_(theme.label(
            "Connecting to your desk…", NSMakeRect(pad, 78, width - 2 * pad, 22),
            size=15, color=NSColor.secondaryLabelColor(), align=theme.ALIGN_CENTER,
        ))

        # Footer: version + quit
        self.addSubview_(theme.label(
            constants.VERSION, NSMakeRect(pad, 13, 120, 16),
            size=11, color=NSColor.tertiaryLabelColor(),
        ))
        self.addSubview_(window.make_quit_button(
            self, NSMakeRect(width - pad - 24, 11, 24, 24)
        ))

    def quitApp_(self, sender):
        """Shuts down the controller server and exits the application."""
        LOGGER.debug("Quit button pressed")
        self.app.quit()
