from enum import Enum

import Cocoa
import objc
from AppKit import (
    NSApplication, NSStatusBar, NSVariableStatusItemLength,
    NSWindow, NSView, NSSlider, NSSliderCell, NSTextField, NSFont,
    NSColor, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSMenu, NSMenuItem, NSBezierPath, NSSize, NSImage,
    NSAttributedString, NSFontAttributeName
)
from Foundation import NSObject, NSMakeRect, NSTimer

from ui.views.connecting import EstablishingConnectionView
from ui.views.setup import InitialSetupView
from ui.views.slider import SliderView
from ui.views.no_connection import NoConnectionView
from ui.views.settings import SettingsView
from ui.timer import _TimerProxy
from control.desk_service import DeskService
from constants import LOGGER
import constants


class KeyableWindow(NSWindow):
    """Borderless NSWindow subclass that can become key (needed for text input)."""
    def canBecomeKeyWindow(self):
        return True
    def canBecomeMainWindow(self):
        return True

class ContentViews(Enum):
    SETUP = 0
    CONNECTING = 1
    SLIDER = 2
    NOCON = 3

class MenuBarApp(NSObject):
    """
    The main application class. Manages the system status bar item,
    the native desk connection lifecycle, and the popover window visibility.
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

            self.current_height = 75  # placeholder until the desk reports its height
            self._spinner_timer = None
            self._spinner_proxy = None
            self._spinner_index = 0
            self.status_item.button().setTarget_(self)
            self.status_item.button().setAction_("togglePopover:")

            self.popover_window = None
            self.settings_window = None
            self.current_content = None
            self.is_visible = False
            self.slider_view = None
            self.move_in_progress = False
            self.move_slider_handle = False
            self.external_move_active = False

            self.desk = DeskService.alloc().init()
            self.desk.setApp(self)
            self.desk.start()
            self.checkAndUpdatePopover()
            LOGGER.debug("Status bar item created, desk service started")

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
            self.popover_window = KeyableWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False
            )

            self.popover_window.setOpaque_(False)
            self.popover_window.setBackgroundColor_(NSColor.clearColor())
            self.popover_window.setLevel_(3)

        self.checkAndUpdatePopover()
        self._renderContentView(self.current_content)

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

    def checkAndUpdatePopover(self):
        """Reflect the current desk connection state in the menu bar and popover."""
        if constants.CONFIG_UUID == constants.PLACEHOLDER_UUID:
            required = ContentViews.SETUP
        elif self.desk.is_dead():
            required = ContentViews.NOCON
        elif self.desk.is_healthy():
            required = ContentViews.SLIDER
        else:
            required = ContentViews.CONNECTING

        if required == self.current_content:
            return

        self.current_content = required
        self._updateStatusItem(required)

        if self.popover_window is not None:
            self._renderContentView(required)

    @objc.python_method
    def _renderContentView(self, state):
        """Builds and installs the popover content view for the given state."""
        self.slider_view = None
        if state == ContentViews.SETUP:
            content_view = InitialSetupView.alloc().initWithApp_(self)
        elif state == ContentViews.NOCON:
            content_view = NoConnectionView.alloc().initWithApp_(self)
        elif state == ContentViews.SLIDER:
            content_view = SliderView.alloc().initWithApp_(self)
            self.slider_view = content_view
        else:
            content_view = EstablishingConnectionView.alloc().initWithApp_(self)
        self.popover_window.setContentView_(content_view)

    @objc.python_method
    def deskHeightChanged(self, height_cm, moving):
        """Height report from the desk service: fires while the app moves the
        desk AND when it is moved externally (physical buttons). Main thread."""
        self.current_height = height_cm

        # Disable the controls while the desk is moved externally
        if not self.move_in_progress and moving != self.external_move_active:
            self.external_move_active = moving
            if self.slider_view is not None:
                self.slider_view.setUIState_(not moving)

        if self.current_content != ContentViews.SLIDER:
            # Status item is showing setup/spinner/warning
            return
        # App-initiated moves only drag the slider handle along when requested
        move_handle = (not self.move_in_progress) or self.move_slider_handle
        slider = self.slider_view.slider if self.slider_view is not None else None
        SliderView.updateUI(
            self.status_item, slider, height_cm,
            slider is not None and move_handle,
        )

    @objc.python_method
    def deskLimitsChanged(self):
        """Desk-derived height limits changed; refresh the slider bounds."""
        if self.slider_view is not None:
            self.slider_view.updateLimits()

    @objc.python_method
    def beginMove(self, target_cm, move_slider_handle):
        """Kicks off a desk move; the UI is re-enabled once the desk reports
        the move has finished."""
        if self.move_in_progress or self.external_move_active:
            return
        self.move_in_progress = True
        self.move_slider_handle = move_slider_handle
        if self.slider_view is not None:
            self.slider_view.setUIState_(False)
        self.desk.move_to_cm(target_cm, self._moveFinished)

    @objc.python_method
    def _moveFinished(self, ok):
        self.move_in_progress = False
        if self.slider_view is not None:
            self.slider_view.setUIState_(True)
        if not ok:
            LOGGER.warning("Desk move did not complete")

    @objc.python_method
    def _deskFrame(self):
        """Returns the desk icon sprite matching the last known height."""
        span = constants.MAX_HEIGHT - constants.MIN_HEIGHT
        normalized = (self.current_height - constants.MIN_HEIGHT) / span
        index = max(0, min(14, round(normalized * 14)))
        return constants.ICON_FRAMES[index]

    @objc.python_method
    def _updateStatusItem(self, state):
        """Updates the menu bar icon/title to reflect the connection state."""
        button = self.status_item.button()
        button.setImage_(self._deskFrame())
        button.setImagePosition_(3)

        if state == ContentViews.CONNECTING:
            self._startStatusSpinner()
            return

        self._stopStatusSpinner()
        if state == ContentViews.NOCON:
            button.setAttributedTitle_(
                NSAttributedString.alloc().initWithString_attributes_(
                    "⚠︎ ", {NSFontAttributeName: constants.MONO_FONT}
                )
            )
        elif state == ContentViews.SETUP:
            button.setImagePosition_(1)
            button.setAttributedTitle_(NSAttributedString.alloc().initWithString_(""))
        else: # SLIDER
            SliderView.updateUI(self.status_item, None, self.current_height, False)

    @objc.python_method
    def _startStatusSpinner(self):
        """Animates a spinner glyph in the menu bar while connecting."""
        if self._spinner_timer is not None:
            return # already spinning
        self._spinner_index = 0
        self._renderSpinnerFrame()
        self._spinner_proxy = _TimerProxy.alloc().initWithCallback_(self._renderSpinnerFrame)
        self._spinner_timer = (
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.15, self._spinner_proxy, "fire:", None, True
            )
        )

    @objc.python_method
    def _renderSpinnerFrame(self):
        button = self.status_item.button()
        frames = constants.SPINNER_FRAMES
        glyph = frames[self._spinner_index % len(frames)]
        self._spinner_index += 1
        button.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                glyph + " ", {NSFontAttributeName: constants.MONO_FONT}
            )
        )

    @objc.python_method
    def _stopStatusSpinner(self):
        if self._spinner_timer is not None:
            self._spinner_timer.invalidate()
            self._spinner_timer = None
        self._spinner_proxy = None

    def openSettings(self):
        """Opens the standalone, centered settings window."""
        self.hidePopover()
        if self.settings_window is None:
            rect = NSMakeRect(0, 0, 364, 300)
            self.settings_window = KeyableWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False
            )
            self.settings_window.setOpaque_(False)
            self.settings_window.setBackgroundColor_(NSColor.clearColor())
            self.settings_window.setLevel_(3)

        # Rebuild the view so the fields reflect the current config.
        self.settings_window.setContentView_(SettingsView.alloc().initWithApp_(self))
        self.settings_window.center()
        Cocoa.NSApp.activateIgnoringOtherApps_(True)
        self.settings_window.makeKeyAndOrderFront_(None)

    def closeSettings(self):
        """Hides the settings window."""
        if self.settings_window:
            self.settings_window.orderOut_(None)

    def quit(self):
        if hasattr(self, "desk") and self.desk is not None:
            self.desk.stop()
        LOGGER.info("Terminating application")
        Cocoa.NSApp.terminate_(None)
