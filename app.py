import queue
import subprocess
import threading
import time
import logging
import os

import Cocoa
import objc
from AppKit import (
    NSApplication, NSStatusBar, NSVariableStatusItemLength,
    NSWindow, NSView, NSSlider, NSSliderCell, NSTextField, NSFont,
    NSColor, NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
    NSMenu, NSMenuItem, NSBezierPath
)
from Foundation import NSObject, NSMakeRect

# Set up logging to file
log_dir = os.path.expanduser("~/Library/Logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "DeskController.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

ICON: str = "|‾‾‾|"
LINAK: str = "/opt/homebrew/anaconda3/bin/linak-controller"


class BackgroundProcess:
    def __init__(self, process):
        self.process = process
        self.active = True
        logger.info(f"BackgroundProcess created with PID: {process.pid}")

    def is_running(self):
        return self.process.poll() is None

    def stop(self):
        if self.is_running():
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.active = False


class ProcessManager:
    def __init__(self, command, timeout=2.0):
        self.command = command
        self.timeout = timeout
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        self.output_queue = queue.Queue()
        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()

    def _read_output(self):
        try:
            for line in self.process.stdout:
                self.output_queue.put(line.rstrip())
        except Exception as e:
            logger.error(f"Error reading output: {e}")
            self.output_queue.put(f"[Error reading output: {e}]")

    def execute(self, command):
        if self.process.poll() is not None:
            raise RuntimeError("Process has terminated")

        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            raise RuntimeError("Process has terminated")

        # Collect all output until timeout
        output = []
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                line = self.output_queue.get(timeout=0.1)
                output.append(line)
                start_time = time.time()
            except queue.Empty:
                pass

        return output

    def execute_background(self, command):
        cmd_list = command.split() if isinstance(command, str) else command

        bg_process = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )

        return BackgroundProcess(bg_process)

    def close(self):
        try:
            self.process.terminate()
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @staticmethod
    def start_background_server(command):
        cmd_list = command.split() if isinstance(command, str) else command

        bg_process = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )
        return BackgroundProcess(bg_process)


class CustomSliderCell(NSSliderCell):
    def stopTracking_at_inView_mouseIsUp_(self, last_point, stop_point, view, mouse_is_up):
        objc.super(CustomSliderCell, self).stopTracking_at_inView_mouseIsUp_(last_point, stop_point, view, mouse_is_up)
        if mouse_is_up:
            target = view.target()
            if target and hasattr(target, "sliderReleased_"):
                target.sliderReleased_(view)


class PopoverContentView(NSView):
    def initWithApp_(self, app):
        self = objc.super(PopoverContentView, self).init()
        if self is None:
            return None

        self.app = app
        frame = NSMakeRect(0, 0, 360, 100)
        self = self.initWithFrame_(frame)
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(12)
        self.buildUI()

        return self

    def buildUI(self):
        # Slider
        self.slider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(20, 58, 320, 25)
        )
        custom_cell = CustomSliderCell.alloc().init()
        self.slider.setCell_(custom_cell)
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
        max_label.setAlignment_(2)
        self.addSubview_(max_label)

        # Quit button
        quit_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(290, 5, 60, 26))
        quit_button.setTitle_("Quit")
        quit_button.setBezelStyle_(1)
        quit_button.setTarget_(self)
        quit_button.setAction_("quitApp:")
        self.addSubview_(quit_button)

    def drawRect_(self, rect):
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            rect, 18, 18
        )
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.18, 0.18, 0.18, 0.95).setFill()
        path.fill()

    def sliderChanged_(self, sender):
        value = round(sender.doubleValue())
        if hasattr(self, "app") and self.app:
            self.app.status_item.button().setTitle_(ICON + "  " + str(value) + "cm")

    def sliderReleased_(self, sender):
        value = round(self.slider.doubleValue())
        cmd: str = LINAK + " --forward --move-to " + str(value * 10)
        logger.info(f"Executing command: {cmd}")
        try:
            with ProcessManager(['bash']) as pm:
                result = pm.execute(cmd)
                logger.info(f"Command result: {result}")
        except Exception as e:
            logger.error(f"Error executing command: {e}")

    def quitApp_(self, sender):
        logger.info("Quit button pressed")
        if hasattr(self, "app") and hasattr(self.app, "server"):
            server = self.app.server
            if server and server.is_running():
                server.stop()
        Cocoa.NSApp.terminate_(None)


class MenuBarApp(NSObject):
    def init(self):
        logger.info("Initializing MenuBarApp")
        self = objc.super(MenuBarApp, self).init()
        if self is None:
            return None

        try:
            # Create status bar item
            self.status_bar = NSStatusBar.systemStatusBar()
            self.status_item = self.status_bar.statusItemWithLength_(
                NSVariableStatusItemLength
            )

            # Set icon/title
            self.status_item.button().setTitle_(ICON)
            self.status_item.button().setTarget_(self)
            self.status_item.button().setAction_("togglePopover:")

            logger.info("Status bar item created")

            # Start linak-controller server
            logger.info("Starting linak-controller server")
            self.server = ProcessManager.start_background_server(LINAK + " --server")
            logger.info(f"Server started, running: {self.server.is_running()}")

            # Create popover window
            self.popover_window = None
            self.is_visible = False

            logger.info("MenuBarApp initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing MenuBarApp: {e}", exc_info=True)

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

            self.popover_window.setOpaque_(False)
            self.popover_window.setBackgroundColor_(NSColor.clearColor())
            self.popover_window.setLevel_(3)

            content_view = PopoverContentView.alloc().initWithApp_(self)
            self.popover_window.setContentView_(content_view)

        button_frame = self.status_item.button().window().frame()
        window_frame = self.popover_window.frame()

        x = button_frame.origin.x + (button_frame.size.width - window_frame.size.width) / 2
        y = button_frame.origin.y - window_frame.size.height - 8

        self.popover_window.setFrameOrigin_((x, y))
        self.popover_window.makeKeyAndOrderFront_(None)

        self.is_visible = True

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
        if self.popover_window:
            point = Cocoa.NSEvent.mouseLocation()
            frame = self.popover_window.frame()
            if not Cocoa.NSPointInRect(point, frame):
                self.hidePopover()


def main():
    logger.info("Starting application")
    app = NSApplication.sharedApplication()
    menu_app = MenuBarApp.alloc().init()
    logger.info("Entering app.run()")
    app.run()


if __name__ == '__main__':
    main()
