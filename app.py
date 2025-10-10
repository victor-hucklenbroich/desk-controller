import Cocoa
import objc
from Foundation import NSObject, NSMakeRect
from AppKit import (
    NSApplication, NSStatusBar, NSVariableStatusItemLength,
    NSWindow, NSView, NSSlider, NSTextField, NSFont,
    NSColor, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSMenu, NSMenuItem
)


class SliderView(NSView):
    """Custom view containing the slider and labels"""

    def init(self):
        self = objc.super(SliderView, self).init()
        if self is None:
            return None

        frame = NSMakeRect(0, 0, 360, 100)
        self = self.initWithFrame_(frame)

        # Height label
        self.height_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, 60, 320, 24)
        )
        self.height_label.setStringValue_("Height: 1.54m")
        self.height_label.setBezeled_(False)
        self.height_label.setDrawsBackground_(False)
        self.height_label.setEditable_(False)
        self.height_label.setSelectable_(False)
        self.height_label.setTextColor_(NSColor.whiteColor())
        self.height_label.setFont_(NSFont.systemFontOfSize_(14))
        self.addSubview_(self.height_label)

        # Slider
        self.slider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(20, 30, 320, 25)
        )
        self.slider.setMinValue_(0.5)
        self.slider.setMaxValue_(2.5)
        self.slider.setDoubleValue_(1.54)
        self.slider.setTarget_(self)
        self.slider.setAction_("sliderChanged:")
        self.addSubview_(self.slider)

        # Min label
        min_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(20, 8, 50, 16)
        )
        min_label.setStringValue_("0.5m")
        min_label.setBezeled_(False)
        min_label.setDrawsBackground_(False)
        min_label.setEditable_(False)
        min_label.setSelectable_(False)
        min_label.setTextColor_(NSColor.grayColor())
        min_label.setFont_(NSFont.systemFontOfSize_(11))
        self.addSubview_(min_label)

        # Max label
        max_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(290, 8, 50, 16)
        )
        max_label.setStringValue_("2.5m")
        max_label.setBezeled_(False)
        max_label.setDrawsBackground_(False)
        max_label.setEditable_(False)
        max_label.setSelectable_(False)
        max_label.setTextColor_(NSColor.grayColor())
        max_label.setFont_(NSFont.systemFontOfSize_(11))
        max_label.setAlignment_(2)  # Right align
        self.addSubview_(max_label)

        # Quit button
        quit_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(280, 60, 60, 26))
        quit_button.setTitle_("Quit")
        quit_button.setBezelStyle_(1)  # Rounded
        quit_button.setTarget_(self)
        quit_button.setAction_("quitApp:")
        self.addSubview_(quit_button)

        return self

    def sliderChanged_(self, sender):
        value = sender.doubleValue()
        self.height_label.setStringValue_(f"Height: {value:.2f}m")

    def quitApp_(self, sender):
        Cocoa.NSApp.terminate_(None)


class MenuBarApp(NSObject):
    """Main menu bar application"""

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
        self.status_item.button().setTitle_("📏")
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
            # Create window
            rect = NSMakeRect(0, 0, 360, 100)
            self.popover_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False
            )

            # Configure window
            self.popover_window.setBackgroundColor_(
                NSColor.colorWithCalibratedRed_green_blue_alpha_(0.18, 0.18, 0.18, 0.95)
            )
            self.popover_window.setOpaque_(False)
            self.popover_window.setLevel_(3)  # Floating window level

            # Add rounded corners
            self.popover_window.contentView().setWantsLayer_(True)
            self.popover_window.contentView().layer().setCornerRadius_(8)

            # Create and add slider view
            slider_view = SliderView.alloc().init()
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
        # Check if click was outside our window
        if self.popover_window:
            point = Cocoa.NSEvent.mouseLocation()
            frame = self.popover_window.frame()
            if not Cocoa.NSPointInRect(point, frame):
                self.hidePopover()


def main():
    app = NSApplication.sharedApplication()

    # Create menu bar app
    menu_app = MenuBarApp.alloc().init()

    # Add a quit menu as fallback (right-click or Option+click)
    menu = NSMenu.alloc().init()
    quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Quit", "terminate:", "q"
    )
    menu.addItem_(quit_item)

    # Run app
    app.run()


if __name__ == '__main__':
    main()
