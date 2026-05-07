import threading
import time

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

import constants
from constants import LOGGER
from control.process import Controller
from desk_controller.constants import CONFIG_SIT, CONFIG_STAND
from ui import window


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


class SliderView(NSView):
    """
    The main UI view for the desk controller popover.
    Handles the UI layout, button interactions, and the asynchronous movement transitions.
    """

    def initWithApp_(self, app):
        self = objc.super(SliderView, self).init()
        if self is None:
            return None

        self.app = app
        self.current_height = 75  # current desk state for animation logic
        frame = NSMakeRect(0, 0, 364, 120)
        self = self.initWithFrame_(frame)
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(12)
        self.buildUI()

        return self

    def buildUI(self):
        """Initializes and positions all UI elements within the popover."""
        self.slider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(22, 64, 320, 25)
        )
        custom_cell = SliderCell.alloc().init()
        self.slider.setCell_(custom_cell)
        self.slider.setMinValue_(constants.MIN_HEIGHT)
        self.slider.setMaxValue_(constants.MAX_HEIGHT)
        self.slider.setDoubleValue_(75)
        self.slider.setTarget_(self)
        self.slider.setAction_("sliderChanged:")
        self.addSubview_(self.slider)

        # Labels for min/max height range
        min_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(12, 90, 50, 16)
        )
        min_label.setStringValue_("60cm")
        min_label.setBezeled_(False)
        min_label.setDrawsBackground_(False)
        min_label.setEditable_(False)
        min_label.setSelectable_(False)
        min_label.setTextColor_(NSColor.whiteColor())
        min_label.setFont_(NSFont.systemFontOfSize_(12))
        min_label.setAlignment_(2)
        self.addSubview_(min_label)

        max_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(292, 90, 50, 16)
        )
        max_label.setStringValue_("130cm")
        max_label.setBezeled_(False)
        max_label.setDrawsBackground_(False)
        max_label.setEditable_(False)
        max_label.setSelectable_(False)
        max_label.setTextColor_(NSColor.whiteColor())
        max_label.setFont_(NSFont.systemFontOfSize_(12))
        max_label.setAlignment_(2)
        self.addSubview_(max_label)

        # Version label
        version_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(4, 8, 90, 16)
        )
        version_label.setStringValue_(constants.VERSION)
        version_label.setBezeled_(False)
        version_label.setDrawsBackground_(False)
        version_label.setEditable_(False)
        version_label.setSelectable_(False)
        version_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.5))
        version_label.setFont_(NSFont.systemFontOfSize_(12))
        version_label.setAlignment_(2)
        self.addSubview_(version_label)

        # Shortcut buttons for preset heights
        self.sit_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(22, 38, 163, 25))
        self.sit_button.setTitle_("Sit")
        self.sit_button.setBezelStyle_(2)
        self.sit_button.setTarget_(self)
        self.sit_button.setAction_("shortcutSit:")
        self.addSubview_(self.sit_button)

        self.stand_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(182, 38, 158, 25))
        self.stand_button.setTitle_("Stand")
        self.stand_button.setBezelStyle_(2)
        self.stand_button.setTarget_(self)
        self.stand_button.setAction_("shortcutStand:")
        self.addSubview_(self.stand_button)

        # App Quit button
        quit_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(295, 5, 57, 27))
        quit_button.setTitle_("Quit")
        quit_button.setBezelStyle_(8)
        quit_button.setTarget_(self)
        quit_button.setAction_("quitApp:")
        self.addSubview_(quit_button)

    def drawRect_(self, rect):
        window.draw_rect(rect)

    @staticmethod
    @objc.python_method
    def updateUI(status_item, slider, height_value, move_slider_handle, ):
        """Function to update all dynamic UI elements."""
        # height display update
        attr_title = NSAttributedString.alloc().initWithString_attributes_(
            f"{height_value:>4}cm", {NSFontAttributeName: constants.MONO_FONT}
        )
        status_item.button().setAttributedTitle_(attr_title)

        # icon sprite update
        normalized = (height_value - constants.MIN_HEIGHT) / (constants.MAX_HEIGHT - constants.MIN_HEIGHT)
        sprite_index = max(0, min(14, round(normalized * 14)))
        status_item.button().setImage_(constants.ICON_SPRITES[sprite_index])

        # slider update
        if move_slider_handle:
            slider.setDoubleValue_(height_value)

    @objc.python_method
    def startTransition_(self, target_value, move_slider_handle=False):
        """
        Coordinates the multi-step desk movement process:
        1. Disables UI to prevent command overlapping.
        2. Dispatches physical move command to a background thread.
        3. Waits for hardware/comms delay.
        4. Animates the height indicators (slider, icon, height display).
        5. Re-enables UI once the physical move is confirmed finished.
        """

        def transition_task():
            # Disable interaction on the main thread
            self.performSelectorOnMainThread_withObject_waitUntilDone_("setUIState:", False, True)

            cmd = constants.MOVE_CMD + str(target_value * 10)
            desk_thread = threading.Thread(target=Controller.execute_command, args=(cmd,), daemon=True)
            desk_thread.start()

            time.sleep(1.5)

            # Visual animation loop
            start_val = self.current_height
            step = 1.0 if target_value > start_val else -1.0
            temp_val = start_val

            while round(temp_val) != target_value:
                temp_val += step
                update_data = {"val": temp_val, "move_slider": move_slider_handle}
                # Safely update UI from background thread
                self.performSelectorOnMainThread_withObject_waitUntilDone_("syncTransitionUI:", update_data, False)
                time.sleep(0.25)  # Speed of visual height updates

            desk_thread.join()

            self.current_height = target_value
            self.performSelectorOnMainThread_withObject_waitUntilDone_("setUIState:", True, False)

        threading.Thread(target=transition_task, daemon=True).start()

    def syncTransitionUI_(self, data):
        """Objective-C selector to update UI elements on the Main Thread."""
        val = round(data["val"])
        SliderView.updateUI(self.app.status_item, self.slider, val, data["move_slider"])

    def setUIState_(self, enabled):
        """Enables or disables UI elements to prevent user input during transitions."""
        self.slider.setEnabled_(enabled)
        self.sit_button.setEnabled_(enabled)
        self.stand_button.setEnabled_(enabled)

    def sliderChanged_(self, sender):
        """Action for slider movements (empty, action is triggered upon release)."""
        pass

    def sliderReleased_(self, sender):
        """Triggered when user releases the slider thumb via CustomSliderCell."""
        target = round(self.slider.doubleValue())
        self.startTransition_(target, move_slider_handle=False)

    def shortcutSit_(self, sender):
        """Action for Sit button."""
        LOGGER.debug("Sit shortcut button pressed")
        self.startTransition_(CONFIG_SIT, move_slider_handle=True)

    def shortcutStand_(self, sender):
        """Action for Stand button."""
        LOGGER.debug("Stand shortcut button pressed")
        self.startTransition_(CONFIG_STAND, move_slider_handle=True)

    def quitApp_(self, sender):
        """Shuts down the controller server and exits the application."""
        LOGGER.debug("Quit button pressed")
        self.app.quit()
