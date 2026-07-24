# Dev tools

## `screenshots.py` — regenerates the README images

Renders each popover/settings view in a window identical to the production
popover and writes the PNGs `README.md` embeds to `docs/screenshots/`, plus a
`menubar.png` composited from the status-bar sprite and its height label.

```bash
.venv-tahoe/bin/python docs/generate_screenshots.py

# Inspect a single view interactively instead of writing files:
.venv-tahoe/bin/python docs/generate_screenshots.py --show slider
```

Views: `slider` · `settings` · `setup` · `nocon` · `connecting`.

CI regenerates these on every release and commits them to the default branch
(see `.github/workflows/release.yml`), so running it by hand is only needed to
preview a UI change locally. A manual `workflow_dispatch` run refreshes the
screenshots without cutting a release.

### Why a special interpreter

macOS 26 (Tahoe) chooses a process's control appearance ("Liquid Glass" vs. the
legacy look) from the **SDK the running executable was linked against**
(`LC_BUILD_VERSION.sdk` in the Mach-O). The shipped app is pinned to the macOS 26
SDK (see `release/pin_sdk.sh`), so rendering the *same* look requires an
interpreter linked against the macOS 26 SDK. `screenshots.py` refuses to run
under anything older rather than silently emitting legacy chrome.

The subtlety: framework builds **re-exec** into
`Resources/Python.app/Contents/MacOS/Python`, so `bin/python` is not the binary
that decides. Check the one that actually runs:

```bash
python3 -c '
import ctypes, os
buf = ctypes.create_string_buffer(1024); size = ctypes.c_uint32(1024)
ctypes.CDLL(None)._NSGetExecutablePath(buf, ctypes.byref(size))
print(os.path.realpath(buf.value.decode()))' | xargs xcrun vtool -show-build
```

- `sdk 26.x` → Tahoe appearance (matches the release)
- `sdk < 26` → legacy appearance — **do not use**

Homebrew's `python@3.14` qualifies. python.org's 3.13 does not, and cannot be
made to: `vtool`-patching its `bin/python3.13` has no effect, because the stub
re-execs the shared framework binary that was never patched.

### Setup (once)

```bash
/opt/homebrew/bin/python3 -m venv .venv-tahoe
.venv-tahoe/bin/pip install pyobjc-framework-Cocoa PyYAML
```

This is a *different* venv from `.venv-build`, which exists to produce a
universal2 release build and is described in `release/README.md`. No single
interpreter satisfies both requirements.

The harness points `HOME` at a scratch directory under `$TMPDIR` so the
config/log bootstrap in `constants.py` never touches your real `~/Library`.
