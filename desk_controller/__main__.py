from constants import LOGGER
from ui import MenuBarApp
from AppKit import NSApplication


def main():
    """Main entry point for the application."""
    LOGGER.info("Starting application")
    app = NSApplication.sharedApplication()
    menu_app = MenuBarApp.alloc().init()
    LOGGER.info("Entering app.run()")
    app.run()


if __name__ == '__main__':
    main()
