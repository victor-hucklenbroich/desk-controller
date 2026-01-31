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

# --- Logging Configuration ---
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

# --- Constants ---
ICON: str = "|‾‾‾|"
VERSION: str = "1.0.0"
LINAK: str = "/opt/homebrew/anaconda3/bin/linak-controller"
MOVE_CMD: str = LINAK + " --forward --move-to "


class BackgroundProcess:
    """
    A wrapper around a subprocess.Popen object to manage its lifecycle
    and provide a clean way to terminate background tasks like the server.
    """

    def __init__(self, process):
        self.process = process
        self.active = True
        logger.info(f"BackgroundProcess created with PID: {process.pid}")

    def is_running(self):
        """Checks if the process is still active."""
        return self.process.poll() is None

    def stop(self):
        """Gracefully terminates the process, falling back to kill if necessary."""
        if self.is_running():
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.active = False


class ProcessManager:
    """
    Handles communication with shell processes. Uses a dedicated reader thread
    to prevent the application from hanging while waiting for command output.
    """

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
        # Thread to drain stdout and prevent buffer bloat
        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()

    def _read_output(self):
        """Continuously reads lines from the process stdout and puts them in a queue."""
        try:
            for line in self.process.stdout:
                self.output_queue.put(line.rstrip())
        except Exception as e:
            logger.error(f"Error reading output: {e}")
            self.output_queue.put(f"[Error reading output: {e}]")

    def send(self, command):
        """Sends a string command to the process stdin and waits for output until timeout."""
        if self.process.poll() is not None:
            raise RuntimeError("Process has terminated")

        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            raise RuntimeError("Process has terminated")

        output = []
        start_time = time.time()

        # Gather output lines until the queue is empty or timeout is reached
        while time.time() - start_time < self.timeout:
            try:
                line = self.output_queue.get(timeout=0.1)
                output.append(line)
                start_time = time.time()
            except queue.Empty:
                pass

        return output

    def execute_background(self, command):
        """Starts a process in the background without waiting for its completion."""
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
        """Closes process pipes and terminates the process."""
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
        """Static helper to initialize the linak-controller server process."""
        cmd_list = command.split() if isinstance(command, str) else command

        bg_process = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True
        )
        return BackgroundProcess(bg_process)

    @staticmethod
    def execute(cmd: str):
        """
        Static helper to run a one-off command through a bash shell.
        Logs the result and handles exceptions.
        """
        logger.info(f"Executing command: {cmd}")
        try:
            with ProcessManager(['bash']) as pm:
                result = pm.send(cmd)
                logger.info(f"Command result: {result}")
        except Exception as e:
            logger.error(f"Error executing command: {e}")


class CustomSliderCell(NSSliderCell):
    """
    Subclass of NSSliderCell to capture the 'mouse up' event on the slider.
    This allows us to trigger the desk movement only when the user finishes dragging.
    """

    def stopTracking_at_inView_mouseIsUp_(self, last_point, stop_point, view, mouse_is_up):
        # Call parent implementation to ensure standard slider behavior
        objc.super(CustomSliderCell, self).stopTracking_at_inView_mouseIsUp_(last_point, stop_point, view, mouse_is_up)

        # Trigger our custom release action if the mouse was actually released
        if mouse_is_up:
            target = view.target()
            if target and hasattr(target, "sliderReleased_"):
                target.sliderReleased_(view)


class PopoverContentView(NSView):
    """
    The main UI view for the desk controller popover.
    Handles the UI layout, button interactions, and the asynchronous movement transitions.
    """

    def initWithApp_(self, app):
        self = objc.super(PopoverContentView, self).init()
        if self is None:
            return None

        self.app = app
        self.current_height = 75  # Tracks current desk state for animation logic
        frame = NSMakeRect(0, 0, 364, 120)
        self = self.initWithFrame_(frame)
        self.setWantsLayer_(True)
        self.layer().setCornerRadius_(12)
        self.buildUI()

        return self

    def buildUI(self):
        """Initializes and positions all UI elements within the popover."""
        # Slider for manual height selection
        self.slider = NSSlider.alloc().initWithFrame_(
            NSMakeRect(22, 64, 320, 25)
        )
        custom_cell = CustomSliderCell.alloc().init()
        self.slider.setCell_(custom_cell)
        self.slider.setMinValue_(63)
        self.slider.setMaxValue_(127)
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

        # Name label
        name_label = NSTextField.alloc().initWithFrame_(
            NSMakeRect(4, 8, 145, 16)
        )
        name_label.setStringValue_(f"DeskController {VERSION}")
        name_label.setBezeled_(False)
        name_label.setDrawsBackground_(False)
        name_label.setEditable_(False)
        name_label.setSelectable_(False)
        name_label.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(1, 0.5))
        name_label.setFont_(NSFont.systemFontOfSize_(12))
        name_label.setAlignment_(2)
        self.addSubview_(name_label)

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
        quit_button = Cocoa.NSButton.alloc().initWithFrame_(NSMakeRect(275, 5, 57, 27))
        quit_button.setTitle_("Quit")
        quit_button.setBezelStyle_(8)
        quit_button.setTarget_(self)
        quit_button.setAction_("quitApp:")
        self.addSubview_(quit_button)

    def drawRect_(self, rect):
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
            logger.exception("drawRect_ failed: %s", e)

    @objc.python_method
    def startTransition_(self, target_value, move_slider_handle=False):
        """
        Coordinates the multi-step desk movement process:
        1. Disables UI to prevent command overlapping.
        2. Dispatches physical move command to a background thread.
        3. Waits for hardware/comms delay (1.5s).
        4. Animates the height indicators (menu bar text and optionally slider).
        5. Re-enables UI once the physical move is confirmed finished.
        """

        def transition_task():
            # Disable interaction on the main thread
            self.performSelectorOnMainThread_withObject_waitUntilDone_("setUIState:", False, True)

            # Start physical desk movement immediately
            cmd = MOVE_CMD + str(target_value * 10)
            desk_thread = threading.Thread(target=ProcessManager.execute, args=(cmd,), daemon=True)
            desk_thread.start()

            # Buffer for linak-controller to initialize and desk to begin moving
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

            # Wait for the shell process to actually finish before re-enabling UI
            desk_thread.join()

            self.current_height = target_value
            self.performSelectorOnMainThread_withObject_waitUntilDone_("setUIState:", True, False)

        threading.Thread(target=transition_task, daemon=True).start()

    def syncTransitionUI_(self, data):
        """Objective-C selector to update UI elements on the Main Thread."""
        val = round(data["val"])
        self.app.status_item.button().setTitle_(f"{ICON}  {val}cm")
        if data["move_slider"]:
            self.slider.setDoubleValue_(val)

    def setUIState_(self, enabled):
        """Enables or disables UI elements to prevent user input during transitions."""
        self.slider.setEnabled_(enabled)
        self.sit_button.setEnabled_(enabled)
        self.stand_button.setEnabled_(enabled)

    def sliderChanged_(self, sender):
        """Action for slider movements (empty, used for live feedback if needed)."""
        pass

    def sliderReleased_(self, sender):
        """Triggered when user releases the slider thumb via CustomSliderCell."""
        target = round(self.slider.doubleValue())
        self.startTransition_(target, move_slider_handle=False)

    def shortcutSit_(self, sender):
        """Action for Sit button preset."""
        logger.info("Sit shortcut button pressed")
        target = 75
        self.startTransition_(target, move_slider_handle=True)

    def shortcutStand_(self, sender):
        """Action for Stand button preset."""
        logger.info("Stand shortcut button pressed")
        target = 120
        self.startTransition_(target, move_slider_handle=True)

    def quitApp_(self, sender):
        """Gracefully shuts down the controller server and exits the application."""
        logger.info("Quit button pressed")
        if hasattr(self, "app") and hasattr(self.app, "server"):
            server = self.app.server
            if server and server.is_running():
                server.stop()
        Cocoa.NSApp.terminate_(None)


class MenuBarApp(NSObject):
    """
    The main application class. Manages the system status bar item,
    the background server lifecycle, and the popover window visibility.
    """

    def init(self):
        logger.info("Initializing MenuBarApp")
        self = objc.super(MenuBarApp, self).init()
        if self is None:
            return None

        try:
            # Setup the macOS Status Bar Item
            self.status_bar = NSStatusBar.systemStatusBar()
            self.status_item = self.status_bar.statusItemWithLength_(
                NSVariableStatusItemLength
            )

            self.status_item.button().setTitle_(ICON + " 75cm")
            self.status_item.button().setTarget_(self)
            self.status_item.button().setAction_("togglePopover:")

            logger.info("Status bar item created")

            # Initialize the background linak-controller server
            logger.info("Starting linak-controller server")
            self.server = ProcessManager.start_background_server(LINAK + " --server")
            logger.info(f"Server started, running: {self.server.is_running()}")

            self.popover_window = None
            self.is_visible = False

            logger.info("MenuBarApp initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing MenuBarApp: {e}", exc_info=True)

        return self

    def togglePopover_(self, sender):
        """Shows or hides the custom popover window."""
        if self.is_visible:
            self.hidePopover()
        else:
            self.showPopover()

    def showPopover(self):
        """Creates (if necessary) and displays the popover window below the menu bar icon."""
        if self.popover_window is None:
            rect = NSMakeRect(0, 0, 364, 120)
            self.popover_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False
            )

            self.popover_window.setOpaque_(False)
            self.popover_window.setBackgroundColor_(NSColor.clearColor())
            self.popover_window.setLevel_(3)  # Ensure it appears above other windows

            content_view = PopoverContentView.alloc().initWithApp_(self)
            self.popover_window.setContentView_(content_view)

        # Calculate position relative to the status item
        button_frame = self.status_item.button().window().frame()
        window_frame = self.popover_window.frame()

        x = button_frame.origin.x + (button_frame.size.width - window_frame.size.width) / 2
        y = button_frame.origin.y - window_frame.size.height - 8

        self.popover_window.setFrameOrigin_((x, y))
        self.popover_window.makeKeyAndOrderFront_(None)

        self.is_visible = True

        # Monitor clicks outside the window to automatically hide the popover
        NSEvent = Cocoa.NSEvent
        mask = Cocoa.NSEventMaskLeftMouseDown | Cocoa.NSEventMaskRightMouseDown
        self.monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            mask, self.clickedOutside_
        )

    def hidePopover(self):
        """Hides the popover window and removes the global click monitor."""
        if self.popover_window:
            self.popover_window.orderOut_(None)
            self.is_visible = False
            if hasattr(self, 'monitor') and self.monitor:
                Cocoa.NSEvent.removeMonitor_(self.monitor)
                self.monitor = None

    def clickedOutside_(self, event):
        """Callback to hide the popover if the user clicks anywhere else on the screen."""
        if self.popover_window:
            point = Cocoa.NSEvent.mouseLocation()
            frame = self.popover_window.frame()
            if not Cocoa.NSPointInRect(point, frame):
                self.hidePopover()


def main():
    """Main entry point for the application."""
    logger.info("Starting application")
    app = NSApplication.sharedApplication()
    menu_app = MenuBarApp.alloc().init()
    logger.info("Entering app.run()")
    app.run()


if __name__ == '__main__':
    main()
