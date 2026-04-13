#!/bin/bash
# Double-click this file to launch rclone GUI

cd "$(dirname "$0")"

# Check for Python 3
if ! command -v python3 &>/dev/null; then
  osascript -e 'display alert "Python 3 not found" message "Please install Python 3 from python.org or via Homebrew: brew install python3"'
  exit 1
fi

# Install Flask if needed
if ! python3 -c "import flask" 2>/dev/null; then
  echo "Installing Flask..."
  pip3 install flask --quiet
fi

# Launch
echo "Starting rclone GUI at http://localhost:5001"
python3 app.py
