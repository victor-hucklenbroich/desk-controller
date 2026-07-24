import os
import sys
import ctypes
import subprocess
import traceback
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "desk_controller"))

os.environ["HOME"] = os.path.join(tempfile.gettempdir(), "deskcontroller-screenshots-home")
os.makedirs(os.environ["HOME"], exist_ok=True)

import objc
from AppKit import (
    NSApplication, NSApplicationActivationPolicyRegular, NSWindow, NSColor,
    NSBackingStoreBuffered, NSMakeRect, NSMakeSize, NSMakePoint,
    NSWindowStyleMaskBorderless, NSBitmapImageFileTypePNG, NSBitmapImageRep,
    NSGraphicsContext, NSImage, NSCalibratedRGBColorSpace, NSRectFillUsingOperation,
    NSCompositingOperationSourceAtop, NSCompositingOperationSourceOver,
    NSAttributedString, NSFontAttributeName, NSForegroundColorAttributeName,
    NSZeroRect, NSProgressIndicator,
)
from Foundation import NSObject, NSTimer, NSData

MIN_SDK = 26

SHOTS = {
    "setup":      ("ui.views.setup", "InitialSetupView", (364, 120), "welcome_view.png"),
    "connecting": ("ui.views.connecting", "EstablishingConnectionView", (364, 120), "startup_view.png"),
    "slider":     ("ui.views.slider", "SliderView", (364, 120), "desk_controller_view.png"),
    "nocon":      ("ui.views.no_connection", "NoConnectionView", (364, 120), "connection_error_message.png"),
    "settings":   ("ui.views.settings", "SettingsView", (364, 300), "settings_view.png"),
}

MENUBAR_HEIGHT = 75
MENUBAR_BG = (0.13, 0.13, 0.14)
SETTLE = 0.6
DEADLINE = 120


class FakeApp:
    """Stand-in for MenuBarApp"""
    current_height = 95
    move_in_progress = False
    external_move_active = False

    def openSettings(self):
        pass

    def quit(self):
        pass


class KeyableWindow(NSWindow):
    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return True


def running_image():
    buf = ctypes.create_string_buffer(1024)
    size = ctypes.c_uint32(1024)
    ctypes.CDLL(None)._NSGetExecutablePath(buf, ctypes.byref(size))
    return os.path.realpath(buf.value.decode())


def linked_sdk(path):
    try:
        out = subprocess.run(["xcrun", "vtool", "-show-build", path],
                             capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "sdk":
            return parts[1]
    return None


def require_tahoe_sdk():
    image = running_image()
    sdk = linked_sdk(image)
    if sdk is None:
        sys.exit(f"could not read the linked SDK of {image}")
    if int(sdk.split(".")[0]) < MIN_SDK:
        sys.exit(
            f"{image}\nis linked against SDK {sdk}; screenshots would render with "
            f"legacy chrome.\nUse an interpreter linked against SDK {MIN_SDK}+ "
            f"(e.g. Homebrew's python@3.14) -- see docs/README.md."
        )
    return sdk


def make_view(name, app):
    module_name, cls_name, size, out_name = SHOTS[name]
    module = __import__(module_name, fromlist=[cls_name])
    cls = getattr(module, cls_name)
    return cls.alloc().initWithApp_(app), size, out_name


def window_for(view, size):
    w, h = size
    win = KeyableWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(200, 200, w, h), NSWindowStyleMaskBorderless,
        NSBackingStoreBuffered, False,
    )
    win.setOpaque_(False)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setLevel_(3)
    win.setContentView_(view)
    win.makeKeyAndOrderFront_(None)
    win.makeFirstResponder_(None)
    return win


def decoded_pixels(data):
    rep = NSBitmapImageRep.imageRepWithData_(data)
    if rep is None:
        return None
    return int(rep.pixelsWide()), int(rep.pixelsHigh()), bytes(rep.bitmapData())


def write_png(rep, path):
    png = rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {})
    if path.exists():
        old = NSData.dataWithContentsOfFile_(str(path))
        if old is not None and decoded_pixels(old) == decoded_pixels(png):
            return False
    if not png.writeToFile_atomically_(str(path), True):
        sys.exit(f"failed to write {path}")
    return True


def bitmap(width, height, scale):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, int(width * scale), int(height * scale), 8, 4, True, False,
        NSCalibratedRGBColorSpace, 0, 0,
    )
    rep.setSize_(NSMakeSize(width, height))
    return rep


def freeze_animations(view):
    for sub in view.subviews():
        if isinstance(sub, NSProgressIndicator):
            sub.setDisplayedWhenStopped_(True)
            sub.stopAnimation_(None)
        freeze_animations(sub)


def capture(view, path, scale):
    freeze_animations(view)
    if view.window() is not None:
        view.window().makeFirstResponder_(None)
    bounds = view.bounds()
    view.displayIfNeeded()
    rep = bitmap(bounds.size.width, bounds.size.height, scale)
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)
    view.displayRectIgnoringOpacity_inContext_(bounds, ctx)
    NSGraphicsContext.restoreGraphicsState()
    return rep, write_png(rep, path)


def render_menubar(path, scale):
    import constants

    span = constants.MAX_HEIGHT - constants.MIN_HEIGHT
    normalized = (MENUBAR_HEIGHT - constants.MIN_HEIGHT) / span
    icon = constants.ICON_FRAMES[max(0, min(14, round(normalized * 14)))]

    title = NSAttributedString.alloc().initWithString_attributes_(
        f"{MENUBAR_HEIGHT}cm", {
            NSFontAttributeName: constants.MONO_FONT,
            NSForegroundColorAttributeName: NSColor.whiteColor(),
        },
    )
    size = constants.ICON_SIZE
    text_size = title.size()
    pad, gap = 6, 2
    width = pad + size + gap + text_size.width + pad
    height = size

    tinted = NSImage.alloc().initWithSize_(NSMakeSize(size, size))
    tinted.lockFocus()
    icon.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(0, 0, size, size), NSZeroRect, NSCompositingOperationSourceOver, 1.0)
    NSColor.whiteColor().set()
    NSRectFillUsingOperation(NSMakeRect(0, 0, size, size), NSCompositingOperationSourceAtop)
    tinted.unlockFocus()

    rep = bitmap(width, height, scale)
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)
    NSColor.colorWithSRGBRed_green_blue_alpha_(*MENUBAR_BG, 1.0).set()
    NSRectFillUsingOperation(NSMakeRect(0, 0, width, height), NSCompositingOperationSourceOver)
    tinted.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(pad, 0, size, size), NSZeroRect, NSCompositingOperationSourceOver, 1.0)
    title.drawAtPoint_(NSMakePoint(pad + size + gap, (height - text_size.height) / 2))
    NSGraphicsContext.restoreGraphicsState()
    return rep, write_png(rep, path)


def assert_not_blank(rep, path):
    """Guards against a headless session rendering empty or single-colour art."""
    w, h = int(rep.pixelsWide()), int(rep.pixelsHigh())
    seen = set()
    for x in range(0, w, max(1, w // 16)):
        for y in range(0, h, max(1, h // 16)):
            colour = rep.colorAtX_y_(x, y)
            if colour is not None:
                seen.add(tuple(round(c, 3) for c in (
                    colour.redComponent(), colour.greenComponent(),
                    colour.blueComponent(), colour.alphaComponent())))
    if len(seen) < 4:
        sys.exit(f"{path} looks blank ({len(seen)} distinct colours) -- "
                 f"the window server session likely rendered nothing")


def abort():
    traceback.print_exc()
    sys.stderr.flush()
    os._exit(1)


def report(path, rep, changed):
    print(f"{'wrote  ' if changed else 'same   '}{os.path.relpath(path, REPO)} "
          f"({int(rep.pixelsWide())}x{int(rep.pixelsHigh())})", flush=True)


class Runner(NSObject):
    def initWithNames_outDir_scale_(self, names, out_dir, scale):
        self = objc.super(Runner, self).init()
        self.names = names
        self.out_dir = out_dir
        self.scale = scale
        self.index = 0
        self.window = None
        self.pending = None
        return self

    @objc.python_method
    def after(self, delay, selector):
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            delay, self, selector, None, False)

    def step_(self, timer):
        try:
            if self.index >= len(self.names):
                path = self.out_dir / "menubar.png"
                rep, changed = render_menubar(path, self.scale)
                assert_not_blank(rep, path)
                report(path, rep, changed)
                NSApplication.sharedApplication().terminate_(None)
                return

            view, size, out_name = make_view(self.names[self.index], FakeApp())

            freeze_animations(view)
            self.window = window_for(view, size)
            self.pending = (view, out_name)
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            self.after(SETTLE, "grab:")
        except BaseException:
            abort()

    def grab_(self, timer):
        try:
            view, out_name = self.pending
            path = self.out_dir / out_name
            rep, changed = capture(view, path, self.scale)
            assert_not_blank(rep, path)
            report(path, rep, changed)

            self.window.orderOut_(None)
            self.window = None
            self.pending = None
            self.index += 1
            self.after(0.05, "step:")
        except BaseException:
            abort()

    def watchdog_(self, timer):
        print(f"timed out after {DEADLINE}s at view "
              f"{self.index + 1}/{len(self.names)}; no window server session?",
              file=sys.stderr, flush=True)
        os._exit(1)


def main():
    args = sys.argv[1:]

    def take(flag, default):
        if flag in args:
            i = args.index(flag)
            value = args[i + 1]
            del args[i:i + 2]
            return value
        return default

    out_dir = REPO / take("--out-dir", "docs/screenshots")
    scale = int(take("--scale", "2"))
    show = take("--show", None)
    if show and show not in SHOTS:
        raise SystemExit(f"unknown view '{show}'; choose from {', '.join(SHOTS)}")

    sdk = require_tahoe_sdk()
    out_dir.mkdir(parents=True, exist_ok=True)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    global _RUNNER
    if show:
        view, size, _ = make_view(show, FakeApp())
        _RUNNER = window_for(view, size)
        app.activateIgnoringOtherApps_(True)
        print(f"showing '{show}' under SDK {sdk}; ctrl-c to quit", flush=True)
        app.run()
        return

    names = list(SHOTS)
    print(f"rendering {len(names)} views at {scale}x under SDK {sdk}", flush=True)
    _RUNNER = Runner.alloc().initWithNames_outDir_scale_(names, out_dir, scale)
    _RUNNER.after(DEADLINE, "watchdog:")
    _RUNNER.after(0.1, "step:")
    app.run()


if __name__ == "__main__":
    main()
