# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for rclone GUI
# Build with:  pyinstaller rclone-gui.spec

import os
block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static',    'static'),
    ],
    hiddenimports=[
        'flask',
        'jinja2',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.routing',
        'werkzeug.exceptions',
        'click',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='rclone GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=True,    # macOS: handle Apple Events (open/quit)
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='rclone GUI',
)

app = BUNDLE(
    coll,
    name='rclone GUI.app',
    icon=None,
    bundle_identifier='com.wcalebparker.rclone-gui',
    info_plist={
        'CFBundleName': 'rclone GUI',
        'CFBundleDisplayName': 'rclone GUI',
        'CFBundleShortVersionString': '1.0.3',
        'CFBundleVersion': '1.0.3',
        'NSHighResolutionCapable': True,
        'LSBackgroundOnly': False,
        'LSMinimumSystemVersion': '10.15',
        'NSRequiresAquaSystemAppearance': False,
    },
)
