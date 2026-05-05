
import objc
from AppKit import (
    NSApplication, NSStatusBar, NSVariableStatusItemLength,
    NSWindow, NSView, NSSlider, NSSliderCell, NSTextField, NSFont,
    NSColor, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSMenu, NSMenuItem, NSBezierPath, NSSize, NSImage,
    NSAttributedString, NSFontAttributeName
)
from Foundation import NSObject, NSMakeRect


class SliderCell(NSSliderCell):
    """
    Subclass of NSSliderCell to capture the mouse release event on the slider.
    """

    def stopTracking_at_inView_mouseIsUp_(self, last_point, stop_point, view, mouse_is_up):
        # Call parent implementation to ensure standard slider behavior
        objc.super(SliderCell, self).stopTracking_at_inView_mouseIsUp_(last_point, stop_point, view, mouse_is_up)

        if mouse_is_up:
            target = view.target()
            if target and hasattr(target, "sliderReleased_"):
                target.sliderReleased_(view)
