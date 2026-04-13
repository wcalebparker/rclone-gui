#!/bin/bash
# ── rclone GUI build script ────────────────────────────────────────────────
# Builds a .dmg installer for the current version.
# Usage: bash build.sh
# Output: dist/rclone-GUI-v<version>.dmg

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ── Read version from app.py ──────────────────────────────
VERSION=$(grep 'APP_VERSION' app.py | head -1 | sed 's/.*"\(.*\)".*/\1/')
echo "▶ Building rclone GUI v$VERSION"

# ── Find Python ───────────────────────────────────────────
PYTHON=""
for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    [ -x "$p" ] && { PYTHON="$p"; break; }
done
[ -z "$PYTHON" ] && { echo "✗ Python 3 not found"; exit 1; }
echo "  Python: $PYTHON"

# ── Find pyinstaller ──────────────────────────────────────
PYINSTALLER="$($PYTHON -m site --user-base)/bin/pyinstaller"
[ ! -x "$PYINSTALLER" ] && PYINSTALLER="$(which pyinstaller 2>/dev/null || true)"
[ -z "$PYINSTALLER" ] && { echo "✗ pyinstaller not found. Run: pip3 install pyinstaller"; exit 1; }
echo "  PyInstaller: $PYINSTALLER"

# ── Install dependencies ──────────────────────────────────
echo "▶ Installing Python dependencies…"
"$PYTHON" -m pip install -r requirements.txt --quiet 2>/dev/null \
    || "$PYTHON" -m pip install -r requirements.txt --quiet --break-system-packages 2>/dev/null

# ── Clean previous build ──────────────────────────────────
rm -rf build dist

# ── Run PyInstaller ───────────────────────────────────────
echo "▶ Running PyInstaller…"
"$PYINSTALLER" rclone-gui.spec --noconfirm

# ── Patch the .app launcher ───────────────────────────────
# PyInstaller builds the server binary but we want the .app to:
# 1. Launch the bundled server in the background
# 2. Open the browser
# We replace the auto-generated launcher with a custom AppleScript wrapper.
APP_PATH="dist/rclone GUI.app"
MACOS_DIR="$APP_PATH/Contents/MacOS"

echo "▶ Patching app launcher…"
cat > /tmp/rclone_gui_launcher.applescript << 'APPLESCRIPT'
on run
    set appDir to do shell script "dirname " & quoted form of (POSIX path of (path to me))
    set serverBin to appDir & "/rclone-gui-server"
    do shell script "nohup " & quoted form of serverBin & " > /tmp/rclone-gui.log 2>&1 &"
    -- wait for server to be ready (up to 15s)
    repeat 30 times
        try
            do shell script "curl -s http://localhost:5001 > /dev/null"
            exit repeat
        end try
        delay 0.5
    end repeat
    open location "http://localhost:5001"
end run
APPLESCRIPT

osacompile -o "$APP_PATH" /tmp/rclone_gui_launcher.applescript 2>/dev/null || true
rm /tmp/rclone_gui_launcher.applescript

# ── Update version in Info.plist ─────────────────────────
PLIST="$APP_PATH/Contents/Info.plist"
if [ -f "$PLIST" ]; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST" 2>/dev/null || true
fi

# ── Create DMG ───────────────────────────────────────────
echo "▶ Creating DMG…"
mkdir -p dist/dmg_staging
cp -R "$APP_PATH" dist/dmg_staging/

DMG_NAME="rclone-GUI-v${VERSION}.dmg"

create-dmg \
    --volname "rclone GUI" \
    --volicon "$APP_PATH/Contents/Resources/applet.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "rclone GUI.app" 175 190 \
    --hide-extension "rclone GUI.app" \
    --app-drop-link 425 190 \
    --no-internet-enable \
    "dist/$DMG_NAME" \
    "dist/dmg_staging/" 2>/dev/null \
    || cp -R "$APP_PATH" "dist/$DMG_NAME.app" && hdiutil create -volname "rclone GUI" -srcfolder "dist/dmg_staging" -ov -format UDZO "dist/$DMG_NAME"

rm -rf dist/dmg_staging

echo ""
echo "✓ Done! Output: dist/$DMG_NAME"
echo ""
echo "To publish a release:"
echo "  git tag v$VERSION && git push origin v$VERSION"
echo "  gh release create v$VERSION dist/$DMG_NAME --title \"rclone GUI v$VERSION\" --notes-file CHANGELOG.md"
