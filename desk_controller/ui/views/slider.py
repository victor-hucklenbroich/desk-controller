import Cocoa
import objc
from AppKit import (
    NSView, NSSlider, NSSliderCell, NSColor,
    NSAttributedString, NSFontAttributeName,
)
from Foundation import NSObject, NSMakeRect

import constants
from constants import LOGGER
from ui import window
from ui import theme


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
    Handles the UI layout and button interactions. Height changes (from app
    commands or external movements) arrive through the app's height events,
    so all indicators reflect what the desk actually reports.
    """

    def initWithApp_(self, app):
        self = objc.super(SliderView, self).init()
        if self is None:
            return None

        self.app = app
        frame = NSMakeRect(0, 0, theme.POPOVER_WIDTH, theme.POPOVER_HEIGHT)
        self = self.initWithFrame_(frame)
        self.buildUI()

        if app.move_in_progress or app.external_move_active:
            self.setUIState_(False)

        return self

    def buildUI(self):
        """Initializes and positions all UI elements within the popover."""
        pad = theme.PAD
        width = theme.POPOVER_WIDTH
        inner = width - 2 * pad

        # Caption
        self.addSubview_(theme.label(
            "Desk height", NSMakeRect(pad, 160, inner, 14),
            size=11, color=NSColor.secondaryLabelColor(),
        ))
        self.value_label = theme.label(
            self._formatHeight(self.app.current_height),
            NSMakeRect(pad, 130, inner, 32),
            size=26, weight=theme.WEIGHT_SEMIBOLD,
        )
        self.addSubview_(self.value_label)

        # Height slider
        self.slider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(pad, 105, inner, 20)
        )
        custom_cell = SliderCell.alloc().init()
        self.slider.setCell_(custom_cell)
        self.slider.setMinValue_(constants.MIN_HEIGHT)
        self.slider.setMaxValue_(constants.MAX_HEIGHT)
        self.slider.setDoubleValue_(self.app.current_height)
        self.slider.setTarget_(self)
        self.slider.setAction_("sliderChanged:")
        self.addSubview_(self.slider)

        # Min / max range captions beneath the slider ends
        self.min_label = theme.label(
            f"{constants.MIN_HEIGHT:.0f} cm", NSMakeRect(pad, 89, 80, 14),
            size=11, color=NSColor.tertiaryLabelColor(), align=theme.ALIGN_LEFT,
        )
        self.addSubview_(self.min_label)
        self.max_label = theme.label(
            f"{constants.MAX_HEIGHT:.0f} cm", NSMakeRect(width - pad - 80, 89, 80, 14),
            size=11, color=NSColor.tertiaryLabelColor(), align=theme.ALIGN_RIGHT,
        )
        self.addSubview_(self.max_label)

        # Sit / Stand preset buttons
        gap = 12
        button_w = (inner - gap) / 2
        self.sit_button = Cocoa.NSButton.alloc().initWithFrame_(
            NSMakeRect(pad, 42, button_w, 34)
        )
        self.sit_button.setTitle_("Sit")
        self.sit_button.setBezelStyle_(2)
        self.sit_button.setTarget_(self)
        self.sit_button.setAction_("shortcutSit:")
        self.addSubview_(self.sit_button)

        self.stand_button = Cocoa.NSButton.alloc().initWithFrame_(
            NSMakeRect(pad + button_w + gap, 42, button_w, 34)
        )
        self.stand_button.setTitle_("Stand")
        self.stand_button.setBezelStyle_(2)
        self.stand_button.setTarget_(self)
        self.stand_button.setAction_("shortcutStand:")
        self.addSubview_(self.stand_button)

        # Footer: version, settings and quit
        self.addSubview_(theme.label(
            constants.VERSION, NSMakeRect(pad, 13, 120, 16),
            size=11, color=NSColor.tertiaryLabelColor(),
        ))
        self.addSubview_(window.make_settings_button(
            self, NSMakeRect(width - pad - 54, 11, 24, 24)
        ))
        self.addSubview_(window.make_quit_button(
            self, NSMakeRect(width - pad - 24, 11, 24, 24)
        ))

    @objc.python_method
    def _formatHeight(self, cm):
        return f"{int(round(cm))} cm"

    def refreshHeight_(self, cm):
        """Updates the live height readout shown above the slider."""
        self.value_label.setStringValue_(self._formatHeight(cm))

    def openSettings_(self, sender):
        """Opens the settings window."""
        LOGGER.debug("Settings button pressed")
        self.app.openSettings()

    @staticmethod
    @objc.python_method
    def updateUI(status_item, slider, height_value, move_slider_handle, update_text=True):
        """Function to update all dynamic UI elements."""
        # height display update
        if update_text:
            attr_title = NSAttributedString.alloc().initWithString_attributes_(
                f"{height_value:>4}cm ", {NSFontAttributeName: constants.MONO_FONT}
            )
            status_item.button().setAttributedTitle_(attr_title)

        # icon sprite update
        normalized = (height_value - constants.MIN_HEIGHT) / (constants.MAX_HEIGHT - constants.MIN_HEIGHT)
        frame_index = max(0, min(14, round(normalized * 14)))
        status_item.button().setImage_(constants.ICON_FRAMES[frame_index])

        # slider update
        if move_slider_handle:
            slider.setDoubleValue_(height_value)

    def setUIState_(self, enabled):
        """Enables or disables UI elements to prevent user input during transitions."""
        self.slider.setEnabled_(enabled)
        self.sit_button.setEnabled_(enabled)
        self.stand_button.setEnabled_(enabled)

    @objc.python_method
    def updateLimits(self):
        """Applies the current desk-derived height limits to slider and labels."""
        self.slider.setMinValue_(constants.MIN_HEIGHT)
        self.slider.setMaxValue_(constants.MAX_HEIGHT)
        self.min_label.setStringValue_(f"{constants.MIN_HEIGHT:.0f} cm")
        self.max_label.setStringValue_(f"{constants.MAX_HEIGHT:.0f} cm")

    def sliderChanged_(self, sender):
        """Action for slider movements (empty, action is triggered upon release)."""
        pass

    def sliderReleased_(self, sender):
        """Triggered when user releases the slider thumb via CustomSliderCell."""
        target = round(self.slider.doubleValue())
        # The user placed the handle at the target already; don't drag it along.
        self.app.beginMove(target, False)

    def shortcutSit_(self, sender):
        """Action for Sit button."""
        LOGGER.debug("Sit shortcut button pressed")
        self.app.beginMove(constants.CONFIG_SIT, True)

    def shortcutStand_(self, sender):
        """Action for Stand button."""
        LOGGER.debug("Stand shortcut button pressed")
        self.app.beginMove(constants.CONFIG_STAND, True)

    def quitApp_(self, sender):
        """Shuts down the desk connection and exits the application."""
        LOGGER.debug("Quit button pressed")
        self.app.quit()
