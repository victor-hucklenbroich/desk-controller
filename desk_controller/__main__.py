import os
import traceback


_fallback_log = os.path.expanduser("~/Library/Logs/DeskController_error.log")

try:
    from AppKit import NSApplication

    def main():
        # init AppKit runtime before importing dependent modules
        app = NSApplication.sharedApplication()
        from constants import LOGGER
        from desk_controller.ui.app import MenuBarApp
        LOGGER.info("Starting application")
        menu_app = MenuBarApp.alloc().init()
        app.run()

    if __name__ == '__main__':
        main()

except Exception:
    with open(_fallback_log, "w") as f:
        f.write(traceback.format_exc())
