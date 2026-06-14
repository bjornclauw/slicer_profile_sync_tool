#!/bin/zsh

# Get the directory where this script is located
cd -- "$(dirname "$0")"

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in your PATH."
    exit 1
fi

# Launch the GUI
python3 profilesync_gui.py