#!/bin/bash

# Get the directory where this script is located
PARENT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$PARENT_DIR"

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

python3 profilesync_gui.py