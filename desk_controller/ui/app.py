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

from ui.views.slider import SliderView
from ui.views.no_connection import NoConnectionView
from control.server import Server
from constants import LOGGER
import constants

class MenuBarApp(NSObject):
    """
    The main application class. Manages the system status bar item,
    the background server lifecycle, and the popover window visibility.
    """

    def init(self):
        LOGGER.debug("Initializing MenuBarApp NSObject")
        self = objc.super(MenuBarApp, self).init()
        if self is None:
            return None
        try:
            self.status_bar = NSStatusBar.systemStatusBar()
            self.status_item = self.status_bar.statusItemWithLength_(
                NSVariableStatusItemLength
            )

            SliderView.updateUI(self.status_item, None, 75, False) # initial UI state
            self.status_item.button().setTarget_(self)
            self.status_item.button().setAction_("togglePopover:")
            LOGGER.debug("Status bar item created")

            self.server = Server.alloc().initWithCommand_(
                constants.LINAK_PATH + " --server"
            )
            self.server.start()
            LOGGER.info(f"Server started, running: {self.server.is_running()}")

            self.popover_window = None
            self.is_visible = False

            LOGGER.debug("MenuBarApp NSObject initialized successfully")
        except Exception as e:
            LOGGER.error(f"Error initializing MenuBarApp NSObject: {e}", exc_info=True)
        return self

    def togglePopover_(self, sender):
        """Shows or hides popover window."""
        if self.is_visible:
            self.hidePopover()
        else:
            self.showPopover()

    def showPopover(self):
        """Creates and displays the popover window below the menu bar icon."""
        if self.popover_window is None:
            rect = NSMakeRect(0, 0, 364, 120)
            self.popover_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False
            )

            self.popover_window.setOpaque_(False)
            self.popover_window.setBackgroundColor_(NSColor.clearColor())
            self.popover_window.setLevel_(3)

            content_view = SliderView.alloc().initWithApp_(self)
            self.popover_window.setContentView_(content_view)

        # Calculate position relative to the status item
        button_frame = self.status_item.button().window().frame()
        window_frame = self.popover_window.frame()

        x = button_frame.origin.x + (button_frame.size.width - window_frame.size.width) / 2
        y = button_frame.origin.y - window_frame.size.height - 8

        self.popover_window.setFrameOrigin_((x, y))
        self.popover_window.makeKeyAndOrderFront_(None)

        self.is_visible = True

        # Monitor clicks outside the window to automatically hide the popover
        NSEvent = Cocoa.NSEvent
        mask = Cocoa.NSEventMaskLeftMouseDown | Cocoa.NSEventMaskRightMouseDown
        self.monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, self.clickedOutside_
        )

    def hidePopover(self):
        """Hides the popover window and removes the global click monitor."""
        if self.popover_window:
            self.popover_window.orderOut_(None)
            self.is_visible = False
            if hasattr(self, 'monitor') and self.monitor:
                Cocoa.NSEvent.removeMonitor_(self.monitor)
                self.monitor = None

    def clickedOutside_(self, event):
        """Callback to hide the popover if the user clicks anywhere else on the screen."""
        if self.popover_window:
            point = Cocoa.NSEvent.mouseLocation()
            frame = self.popover_window.frame()
            if not Cocoa.NSPointInRect(point, frame):
                self.hidePopover()

    def quit(self):
        if hasattr(self, "server"):
            if self.server and self.server.is_running():
                self.server.stop()
        LOGGER.info("Terminating application")
        Cocoa.NSApp.terminate_(None)
