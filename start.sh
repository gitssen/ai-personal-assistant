#!/bin/bash

# Assistant Launcher
# Usage: ./start.sh

# Get the absolute path of the script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Ensure Python dependencies for the runner are met (requests)
if ! python3 -c "import requests" &> /dev/null; then
    echo "[!] Installing missing dependencies for the launcher..."
    pip install requests &> /dev/null
fi

# Run the Python monitoring script
python3 run.py
