#!/bin/bash
# rclone GUI background launcher — called by the .app, never run directly by users

PROJECT="/Users/caleb/Documents/rclone app project"

# ── Already running? Just open the browser ────────────────
if lsof -ti:5001 >/dev/null 2>&1; then
    open "http://localhost:5001"
    exit 0
fi

# ── Find Python 3 ─────────────────────────────────────────
PYTHON=""
for p in \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /usr/bin/python3
do
    [ -x "$p" ] && { PYTHON="$p"; break; }
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display alert "Python 3 not found" message "Please install Python 3 from python.org or via Homebrew: brew install python3"'
    exit 1
fi

# ── Install Flask if needed ────────────────────────────────
if ! "$PYTHON" -c "import flask" 2>/dev/null; then
    "$PYTHON" -m pip install flask --quiet 2>/dev/null \
        || "$PYTHON" -m pip install flask --quiet --break-system-packages 2>/dev/null
fi

# ── Start Flask ────────────────────────────────────────────
cd "$PROJECT"
"$PYTHON" app.py &
SERVER_PID=$!

# ── Wait until the server responds (up to 15s) ────────────
for i in $(seq 1 30); do
    if curl -s http://localhost:5001 >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# ── Open the browser ──────────────────────────────────────
open "http://localhost:5001"

# ── Stay alive so the server keeps running ────────────────
wait $SERVER_PID
