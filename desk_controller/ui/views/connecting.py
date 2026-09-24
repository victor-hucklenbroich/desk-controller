import objc
from AppKit import (
    NSView, NSColor, NSImageView, NSImageScaleAxesIndependently,
)
from Foundation import (
    NSMakeRect, NSTimer, NSRunLoop, NSRunLoopCommonModes,
)

import constants
from constants import LOGGER
from ui import window
from ui import theme


# Seconds between sprite frames
FRAME_INTERVAL = 0.06

ICON_W = 48
ICON_H = 39


class EstablishingConnectionView(NSView):
    """
    Intermediary UI view displayed while connecting and setting up desk connection.
    """

    def initWithApp_(self, app):
        self = objc.super(EstablishingConnectionView, self).init()
        if self is None:
            return None

        self.app = app
        self._frames = constants.ICON_FRAMES
        self._frame_index = 0
        self._frame_step = 1
        self._timer = None
        frame = NSMakeRect(0, 0, theme.POPOVER_WIDTH, theme.POPOVER_HEIGHT)
        self = self.initWithFrame_(frame)
        self.buildUI()

        return self

    def buildUI(self):
        """Initializes and positions all UI elements within the popover."""
        pad = theme.PAD
        width = theme.POPOVER_WIDTH
        height = theme.POPOVER_HEIGHT

        # Controls: quit
        self.addSubview_(window.make_quit_button(
            self, NSMakeRect(width - pad - 24, height - 38, 24, 24)
        ))

        self.icon_view = NSImageView.alloc().initWithFrame_(
            NSMakeRect((width - ICON_W) / 2, 80, ICON_W, ICON_H)
        )
        self.icon_view.setImageScaling_(NSImageScaleAxesIndependently)
        self.icon_view.setContentTintColor_(NSColor.secondaryLabelColor())
        self.icon_view.setImage_(self._frames[self._frame_index])
        self.addSubview_(self.icon_view)

        self.addSubview_(theme.label(
            "Connecting to your desk…", NSMakeRect(pad, 54, width - 2 * pad, 22),
            size=15, color=NSColor.secondaryLabelColor(), align=theme.ALIGN_CENTER,
        ))

    def viewDidMoveToWindow(self):
        """Runs the sprite animation only while the view is on screen."""
        if self.window() is None:
            self._stopAnimation()
        else:
            self._startAnimation()

    @objc.python_method
    def _startAnimation(self):
        if self._timer is not None:
            return
        self._frame_index = 0
        self._frame_step = 1
        self.icon_view.setImage_(self._frames[self._frame_index])
        self._timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            FRAME_INTERVAL, self, "advanceFrame:", None, True
        )
        NSRunLoop.currentRunLoop().addTimer_forMode_(self._timer, NSRunLoopCommonModes)

    @objc.python_method
    def _stopAnimation(self):
        if self._timer is not None:
            self._timer.invalidate()
            self._timer = None

    def advanceFrame_(self, timer):
        last = len(self._frames) - 1
        self._frame_index += self._frame_step
        if self._frame_index >= last:
            self._frame_index = last
            self._frame_step = -1
        elif self._frame_index <= 0:
            self._frame_index = 0
            self._frame_step = 1
        self.icon_view.setImage_(self._frames[self._frame_index])

    def quitApp_(self, sender):
        """Shuts down the controller server and exits the application."""
        LOGGER.debug("Quit button pressed")
        self.app.quit()

    def dealloc(self):
        self._stopAnimation()
        objc.super(EstablishingConnectionView, self).dealloc()
