import subprocess
import queue
import subprocess
import threading
import time

import Cocoa
import objc
from AppKit import (
    NSApplication, NSStatusBar, NSVariableStatusItemLength,
    NSWindow, NSView, NSSlider, NSTextField, NSFont,
    NSColor, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSMenu, NSMenuItem
)
from Foundation import NSObject, NSMakeRect

ICON: str = "|‾‾‾|"


class SliderView(NSView):
    def initWithApp_(self, app):
        self = objc.super(SliderView, self).init()
        if self is None:
            return None

        self.app = app  # store reference to MenuBarApp
        frame = NSMakeRect(0, 0, 360, 100)
        self = self.initWithFrame_(frame)
        self.buildUI()

        return self


    def buildUI(self):
        # Slider
        self.slider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(20, 58, 320, 25)
        )
        self.slider.setMinValue_(63)
        self.slider.setMaxValue_(127)
        self.slider.setDoubleValue_(70)
        self.slider.setTarget_(self)
        self.slider.setAction_("sliderChanged:")
        self.addSubview_(self.slider)

        # Min label
        min_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, 38, 50, 16)
        )
        min_label.setStringValue_("60cm")
        min_label.setBezeled_(False)
        min_label.setDrawsBackground_(False)
        min_label.setEditable_(False)
        min_label.setSelectable_(False)
        min_label.setTextColor_(NSColor.grayColor())
        min_label.setFont_(NSFont.systemFontOfSize_(11))
        self.addSubview_(min_label)

        # Max label
        max_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(290, 38, 50, 16)
        )
        max_label.setStringValue_("130cm")
        max_label.setBezeled_(False)
        max_label.setDrawsBackground_(False)
        max_label.setEditable_(False)
        max_label.setSelectable_(False)
        max_label.setTextColor_(NSColor.grayColor())
        max_label.setFont_(NSFont.systemFontOfSize_(11))
        max_label.setAlignment_(2)  # Right align
        self.addSubview_(max_label)

        # Quit button
        quit_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(290, 5, 60, 26))
        quit_button.setTitle_("Quit")
        quit_button.setBezelStyle_(1)  # Rounded
        quit_button.setTarget_(self)
        quit_button.setAction_("quitApp:")
        self.addSubview_(quit_button)

    def sliderChanged_(self, sender):
        value = round(sender.doubleValue())

        # Update menubar title dynamically
        if hasattr(self, "app") and self.app :
            self.app.status_item.button().setTitle_(ICON + "  " + str(value) + "cm")

    def quitApp_(self, sender):
        Cocoa.NSApp.terminate_(None)


class MenuBarApp(NSObject):

    def init(self):
        self = objc.super(MenuBarApp, self).init()
        if self is None:
            return None

        # Create status bar item
        self.status_bar = NSStatusBar.systemStatusBar()
        self.status_item = self.status_bar.statusItemWithLength_(
            NSVariableStatusItemLength
        )

        # Set icon/title
        self.status_item.button().setTitle_(ICON)
        self.status_item.button().setTarget_(self)
        self.status_item.button().setAction_("togglePopover:")

        # Create popover window
        self.popover_window = None
        self.is_visible = False

        return self

    def togglePopover_(self, sender):
        if self.is_visible:
            self.hidePopover()
        else:
            self.showPopover()

    def showPopover(self):
        if self.popover_window is None:
            rect = NSMakeRect(0, 0, 360, 100)
            self.popover_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False
            )

            self.popover_window.setBackgroundColor_(
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.18, 0.18, 0.18, 0.95)
            )
            self.popover_window.setOpaque_(False)
            self.popover_window.setLevel_(3)  # Floating window level

            self.popover_window.contentView().setWantsLayer_(True)
            self.popover_window.contentView().layer().setCornerRadius_(8)

            slider_view = SliderView.alloc().initWithApp_(self)
            self.popover_window.setContentView_(slider_view)

        # Position window below status item
        button_frame = self.status_item.button().window().frame()
        window_frame = self.popover_window.frame()

        x = button_frame.origin.x + (button_frame.size.width - window_frame.size.width) / 2
        y = button_frame.origin.y - window_frame.size.height - 8

        self.popover_window.setFrameOrigin_((x, y))
        self.popover_window.makeKeyAndOrderFront_(None)

        self.is_visible = True

        # Monitor clicks outside window to close it
        NSEvent = Cocoa.NSEvent
        mask = Cocoa.NSEventMaskLeftMouseDown | Cocoa.NSEventMaskRightMouseDown
        self.monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, self.clickedOutside_
        )

    def hidePopover(self):
        if self.popover_window:
            self.popover_window.orderOut_(None)
            self.is_visible = False
            if hasattr(self, 'monitor') and self.monitor:
                Cocoa.NSEvent.removeMonitor_(self.monitor)
                self.monitor = None

    def clickedOutside_(self, event):
        # Check if click was outside window
        if self.popover_window:
            point = Cocoa.NSEvent.mouseLocation()
            frame = self.popover_window.frame()
            if not Cocoa.NSPointInRect(point, frame):
                self.hidePopover()


def main():
    app = NSApplication.sharedApplication()
    menu_app = MenuBarApp.alloc().init()
    app.run()


if __name__ == '__main__':
    main()
