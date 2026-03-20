# app.spec
analysis = Analysis(
    ['desk_controller/__main__.py'],
    pathex=['desk_controller'],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['objc', 'Cocoa', 'AppKit', 'Foundation'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=None)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    [],
    name='DeskController',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='DeskController.app',
    icon='assets/app_icon.icns',
    bundle_identifier='com.victorhucklenbroich.DeskController',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'LSUIElement': 'True'
    },
)
