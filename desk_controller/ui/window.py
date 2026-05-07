import Cocoa
from AppKit import (
    NSApplication, NSStatusBar, NSVariableStatusItemLength,
    NSWindow, NSView, NSSlider, NSSliderCell, NSTextField, NSFont,
    NSColor, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSMenu, NSMenuItem, NSBezierPath, NSSize, NSImage,
    NSAttributedString, NSFontAttributeName
)
from Foundation import NSObject, NSMakeRect

from constants import LOGGER


def draw_rect(rect):
    """Custom drawing code for the view's background and border."""
    try:
        outer_radius = 18.0
        outer_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, outer_radius, outer_radius)

        bright = NSColor.colorWithCalibratedWhite_alpha_(0.95, 0.5)
        bright.set()
        outer_path.setLineWidth_(0.5)
        outer_path.stroke()

        inset_amount = 0.8
        inner_rect = Cocoa.NSInsetRect(rect, inset_amount, inset_amount)
        inner_radius = max(outer_radius - inset_amount, 7.0)
        inner_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(inner_rect, inner_radius, inner_radius)

        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.1, 0.1, 0.12, 0.9).setFill()
        inner_path.stroke()
        inner_path.fill()
    except Exception as e:
        LOGGER.exception("window.draw_rect() failed: %s", e)
