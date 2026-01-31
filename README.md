# DeskController

**Version:** 1.0.0  
**Author:** Victor Hucklenbroich

A lightweight macOS menu bar application for controlling Linak-based standing desks. DeskController provides a visual interface for linak-controller interactions, allowing bluetooth desk height control.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)
![Python](https://img.shields.io/badge/python-3.x-blue.svg)

## Dependencies

This application is built on top of [linak-controller](https://github.com/rhyst/linak-controller), an open-source project for controlling Linak standing desk controllers via Bluetooth.

### Requirements

- macOS
- Python 3.x
- PyObjC (for macOS native UI)
- Homebrew (recommended for linak-controller installation)
- linak-controller installed at `/opt/homebrew/anaconda3/bin/linak-controller`

## Installation

1. **Install linak-controller**:
   ```bash
   # Follow instructions at https://github.com/rhyst/linak-controller
   pip install linak-controller
   ```


2. **Clone this repository**:
   ```bash
   git clone https://github.com/yourusername/DeskController.git
   cd DeskController
   ```

3. **Install Python dependencies**:
   ```bash
   pip install pyobjc-core pyobjc-framework-Cocoa
   ```
4. **Build the application** (using PyInstaller):
   ```bash
   ./build_app
   ```
   
   The built application will be available in the `dist/` directory.

5. **Run the application**:
   - Copy `DeskController.app` from `dist/` to your Applications folder
   - Launch DeskController

## Usage

1. **Show popover**: Click the DeskController icon in your menu bar
2. **Adjust Height**: 
   - Drag the slider to your desired height and release
   - Click "Sit" for 75cm preset
   - Click "Stand" for 120cm preset
3. **Monitor**: Current desk height is displayed in the menu bar (e.g., `|‾‾‾| 75cm`)
4. **Quit**: Click the "Quit" button in the popover

## Configuration

The application expects linak-controller to be installed at:
```
/opt/homebrew/anaconda3/bin/linak-controller
```

To change this path, modify the `LINAK` constant in the source code:
```python
LINAK: str = "/your/custom/path/to/linak-controller"
```
The linak-controller `config.yaml` also needs to be configured with the correct UUID.

## Logging

Logs are written to:
```
~/Library/Logs/DeskController.log
```

This includes command execution, status, and errors.

## Acknowledgments

- Built with [linak-controller](https://github.com/rhyst/linak-controller) by [rhyst](https://github.com/rhyst)

