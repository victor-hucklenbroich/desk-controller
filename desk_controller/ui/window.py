import Cocoa
from AppKit import (
    NSApplication, NSApp, NSStatusBar, NSVariableStatusItemLength,
    NSWindow, NSView, NSSlider, NSSliderCell, NSTextField, NSFont,
    NSColor, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSMenu, NSMenuItem, NSBezierPath, NSSize, NSImage,
    NSAttributedString, NSFontAttributeName,
    NSEventModifierFlagCommand, NSEventModifierFlagOption,
    NSEventModifierFlagShift
)
from Foundation import NSObject, NSMakeRect

from constants import LOGGER


def _add_submenu(parent, title):
    """Attaches a titled submenu to parent and returns it."""
    item = NSMenuItem.alloc().init()
    parent.addItem_(item)
    submenu = NSMenu.alloc().initWithTitle_(title)
    parent.setSubmenu_forItem_(submenu, item)
    return submenu


def _add_item(menu, title, action, key, target=None):
    """Appends a menu item. Leaving the target nil sends the action down the
    responder chain, which is what lets the editing actions reach whichever
    text field currently holds focus."""
    item = menu.addItemWithTitle_action_keyEquivalent_(title, action, key)
    if target is not None:
        item.setTarget_(target)
    return item


def install_main_menu(app):
    """Installs the application menu bar."""
    try:
        main_menu = NSMenu.alloc().init()

        app_menu = _add_submenu(main_menu, "DeskController")
        _add_item(app_menu, "About DeskController", "orderFrontStandardAboutPanel:", "")
        app_menu.addItem_(NSMenuItem.separatorItem())
        _add_item(app_menu, "Hide DeskController", "hide:", "h")
        _add_item(app_menu, "Hide Others", "hideOtherApplications:", "h") \
            .setKeyEquivalentModifierMask_(
                NSEventModifierFlagOption | NSEventModifierFlagCommand
            )
        _add_item(app_menu, "Show All", "unhideAllApplications:", "")
        app_menu.addItem_(NSMenuItem.separatorItem())
        _add_item(app_menu, "Quit DeskController", "quitApp:", "q", target=app)

        edit_menu = _add_submenu(main_menu, "Edit")
        _add_item(edit_menu, "Undo", "undo:", "z")
        _add_item(edit_menu, "Redo", "redo:", "z").setKeyEquivalentModifierMask_(
            NSEventModifierFlagShift | NSEventModifierFlagCommand
        )
        edit_menu.addItem_(NSMenuItem.separatorItem())
        _add_item(edit_menu, "Cut", "cut:", "x")
        _add_item(edit_menu, "Copy", "copy:", "c")
        _add_item(edit_menu, "Paste", "paste:", "v")
        _add_item(edit_menu, "Delete", "delete:", "")
        _add_item(edit_menu, "Select All", "selectAll:", "a")

        window_menu = _add_submenu(main_menu, "Window")
        _add_item(window_menu, "Close", "performClose:", "w")
        _add_item(window_menu, "Minimize", "performMiniaturize:", "m")

        NSApp.setMainMenu_(main_menu)
        LOGGER.debug("Main menu installed")
    except Exception as e:
        LOGGER.exception("window.install_main_menu() failed: %s", e)


def make_settings_button(target, frame):
    """Builds a gear icon button wired to the openSettings action."""
    button = Cocoa.NSButton.alloc().initWithFrame_(frame)
    gear = NSImage.imageWithSystemSymbolName_accessibilityDescription_("gearshape", "Settings")
    if gear is not None:
        button.setImage_(gear)
        button.setImagePosition_(1)  # NSImageOnly
    else:
        button.setTitle_("⚙")
    button.setBezelStyle_(8)

    button.setBordered_(False)
    button.setContentTintColor_(NSColor.secondaryLabelColor())
    button.setFocusRingType_(1)  # NSFocusRingTypeNone
    button.setTarget_(target)
    button.setAction_("openSettings:")
    return button


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
