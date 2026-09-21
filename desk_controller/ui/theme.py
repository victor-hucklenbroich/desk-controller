"""Design tokens and small AppKit factory helpers for the DeskController UI.

Centralises the popover geometry, typography, colours and the boilerplate for
building non-editable labels so the individual views stay declarative. Colours
are the dynamic system colours (``labelColor`` and friends) so every view tracks
the light/dark appearance and picks up vibrancy on top of the Liquid Glass
background instead of the old hard-coded whites.
"""

from AppKit import NSColor, NSFont, NSTextField
from Foundation import NSMakeRect


# Popover geometry
POPOVER_WIDTH = 340
POPOVER_HEIGHT = 188
POPOVER_RADIUS = 22.0
PAD = 18

# Text alignment
ALIGN_LEFT = 0
ALIGN_CENTER = 1
ALIGN_RIGHT = 2

# Font weights
WEIGHT_REGULAR = 0.0
WEIGHT_MEDIUM = 0.23
WEIGHT_SEMIBOLD = 0.3
WEIGHT_BOLD = 0.4


def font(size, weight=None):
    """A system font at ``size`` points, optionally at a specific weight."""
    if weight is None:
        return NSFont.systemFontOfSize_(size)
    return NSFont.systemFontOfSize_weight_(size, weight)


def label(text, frame, size=13, color=None, weight=None, align=ALIGN_LEFT):
    """Builds a static (non-editable, transparent) text label.

    ``color`` defaults to ``labelColor`` so the text is legible over the glass
    in both light and dark appearances.
    """
    field = NSTextField.alloc().initWithFrame_(frame)
    field.setStringValue_(text)
    field.setBezeled_(False)
    field.setDrawsBackground_(False)
    field.setEditable_(False)
    field.setSelectable_(False)
    field.setFont_(font(size, weight))
    field.setTextColor_(color if color is not None else NSColor.labelColor())
    field.setAlignment_(align)
    return field
