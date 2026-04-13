#!/bin/bash
# ── rclone GUI Installer ───────────────────────────────────────────────────
# Double-click this file to install rclone GUI into your Applications folder.

set -e

DMG_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="rclone GUI.app"
SOURCE="$DMG_DIR/$APP_NAME"
DEST="/Applications/$APP_NAME"

echo ""
echo "  ⇄  rclone GUI Installer"
echo "  ─────────────────────────────"
echo ""

# ── Copy to Applications ──────────────────────────────────────────────────
if [ -d "$DEST" ]; then
    echo "  Updating existing installation…"
    rm -rf "$DEST"
fi

echo "  Copying to /Applications…"
cp -R "$SOURCE" "$DEST"

# ── Remove quarantine (the key step) ─────────────────────────────────────
echo "  Removing macOS security quarantine…"
xattr -cr "$DEST"

echo ""
echo "  ✓ Done! Opening rclone GUI…"
echo ""

# ── Launch ────────────────────────────────────────────────────────────────
open "$DEST"
