# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for rclone GUI
# Build with:  pyinstaller rclone-gui.spec

import os
import certifi
block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static',    'static'),
        # Bundle certifi's CA certificate file so HTTPS works inside the packaged app.
        # certifi.where() returns the absolute path to cacert.pem on the build machine.
        (certifi.where(), 'certifi'),
    ],
    hiddenimports=[
        'flask',
        'jinja2',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.routing',
        'werkzeug.exceptions',
        'click',
        'certifi',
        'ssl',
        'AppKit',
        'Foundation',
        'objc',
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
    argv_emulation=False,   # Must be False — True intercepts Apple Events and kills startup
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
    icon='appicon.icns',
    bundle_identifier='com.wcalebparker.rclone-gui',
    info_plist={
        'CFBundleName': 'rclone GUI',
        'CFBundleDisplayName': 'rclone GUI',
        'CFBundleShortVersionString': '1.0.12',
        'CFBundleVersion': '1.0.12',
        'NSHighResolutionCapable': True,
        'LSUIElement': True,          # Background agent — no dock bounce, no window required
        'LSBackgroundOnly': False,
        'LSMinimumSystemVersion': '10.15',
        'NSRequiresAquaSystemAppearance': False,
    },
)
