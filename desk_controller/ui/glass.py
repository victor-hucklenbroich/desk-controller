"""Liquid Glass container for the popover.

macOS 26/Tahoe introduced ``NSGlassEffectView`` — the AppKit view that renders
the real "Liquid Glass" material (a translucent, light-refracting panel with a
specular edge) used across the redesigned menu-bar widgets. We look it up at
runtime so the app still builds and runs on older SDKs, where we fall back to a
frosted ``NSVisualEffectView`` popover material that gives a comparable
translucent look.
"""

import objc
from AppKit import (
    NSView, NSVisualEffectView, NSViewWidthSizable, NSViewHeightSizable,
    NSVisualEffectMaterialPopover, NSVisualEffectStateActive,
    NSVisualEffectBlendingModeBehindWindow,
)
from Foundation import NSMakeRect

from constants import LOGGER

# Resolve the Liquid Glass class import on older systems
try:
    _GLASS_CLASS = objc.lookUpClass("NSGlassEffectView")
except Exception:
    _GLASS_CLASS = None


def supports_liquid_glass():
    """True when the host provides the real ``NSGlassEffectView`` material."""
    return _GLASS_CLASS is not None


def make_container(width, height, radius):
    """Returns a translucent, rounded container view sized ``width`` x ``height``.

    On macOS 26+ this is a genuine Liquid Glass ``NSGlassEffectView``; otherwise
    a frosted popover-material ``NSVisualEffectView`` clipped to ``radius``.
    """
    frame = NSMakeRect(0, 0, width, height)

    if _GLASS_CLASS is not None:
        glass = _GLASS_CLASS.alloc().initWithFrame_(frame)
        glass.setCornerRadius_(radius)
        return glass

    LOGGER.info("NSGlassEffectView unavailable; using frosted material fallback")
    effect = NSVisualEffectView.alloc().initWithFrame_(frame)
    effect.setMaterial_(NSVisualEffectMaterialPopover)
    effect.setState_(NSVisualEffectStateActive)
    effect.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
    effect.setWantsLayer_(True)
    effect.layer().setCornerRadius_(radius)
    effect.layer().setMasksToBounds_(True)
    return effect


def set_content(container, content):
    """Installs ``content`` inside ``container`` so it fills the glass panel.

    ``NSGlassEffectView`` hosts a single ``contentView``; the fallback view just
    takes the content as a pinned subview.
    """
    content.setFrame_(container.bounds())
    content.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
    if _GLASS_CLASS is not None and container.respondsToSelector_("setContentView:"):
        container.setContentView_(content)
    else:
        container.addSubview_(content)
    return container
