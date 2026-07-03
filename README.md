# DeskController Menu Bar App

**Version:** v1.2.0

DeskController is a lightweight macOS menu bar application for controlling Linak-based standing desks. DeskController talks to the desk directly over Bluetooth (BLE) and keeps a persistent connection in the background.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)
![Python](https://img.shields.io/badge/python-3.x-blue.svg)

### Requirements

- macOS 14 Sonoma or later
- [Homebrew](https://brew.sh)
- A Linak-based desk already paired to your Mac via Bluetooth

DeskController is distributed as a signed, notarized, fully self-contained app bundle through a Homebrew cask.


### Compatibility

DeskController ships as a universal binary and runs natively on both Apple Silicon and Intel Macs. It is primarily tested on Apple Silicon Macs with macOS Tahoe and an Ikea Idasen. 

DeskController's Bluetooth communication layer is based on [linak-controller](https://github.com/rhyst/linak-controller), an open-source project for controlling Linak standing desk controllers via Bluetooth.

 Compatible Desks reported by linak-controller:
- Ikea Idasen
- iMovr Lander
- Linak DPG1C
- Linak DPG1M

## Quick Start

1. **Install via Homebrew**:

   ```bash
   brew install --cask victor-hucklenbroich/tap/desk-controller
   ```

   This installs DeskController into `/Applications`.

2. **Launch the App**:

   Open `/Applications/DeskController.app`, or run:

   ```bash
   open -a DeskController
   ```

3. **Enter your desks UUID**:

![image](./assets/screenshots/welcome_view.png) ![image](./assets/screenshots/startup_view.png) 

4. **Control your desk!**

![image](./assets/screenshots/desk_controller_view.png) 

### Build from source

Developers can build locally instead of using the cask:

```bash
git clone https://github.com/victor-hucklenbroich/desk-controller.git
cd desk-controller
pip install pyinstaller -r requirements.txt
pyinstaller app.spec
```

This builds an app for your machine's architecture. Release builds are universal2, reproducing one requires a universal2 Python (e.g. from python.org) and a pure-Python PyYAML:

```bash
PYYAML_FORCE_LIBYAML=0 pip install --no-binary PyYAML pyinstaller -r requirements.txt
DC_TARGET_ARCH=universal2 pyinstaller app.spec
```


## Troubleshooting
If something goes wrong during installation, check the output of `brew install` to find the issue. A likely culprit is a missing or outdated Homebrew installation.

![image](./assets/screenshots/connection_error_message.png)

If the DeskController App is not launching properly there is a prelaunch error log available at `~/Library/Logs/DeskController_error.log`. Most common issues are a wrong desk UUID, a missing Bluetooth permission for DeskController (System Settings → Privacy & Security → Bluetooth), or the Bluetooth connection between your Mac and desk. The desk UUID and presets are stored in the config file at `~/Library/Application Support/DeskController/config.yaml`. Also make sure the UUID is correct, and you can connect to your desk via Bluetooth. If you are still facing issues, check the runtime logs located at `~/Library/Logs/DeskController.log`.

## Uninstall

Remove DeskController with Homebrew:

```bash
brew uninstall --cask desk-controller
```

To also delete its configuration and logs, add `--zap`:

```bash
brew uninstall --zap --cask desk-controller
```

## Acknowledgements

- The Bluetooth communication layer is adapted from [linak-controller](https://github.com/rhyst/linak-controller) by [rhyst](https://github.com/rhyst)
