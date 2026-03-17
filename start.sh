#!/bin/bash

# Assistant Launcher
# Usage: ./start.sh

# Get the absolute path of the script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "[*] Cleaning up existing processes on ports 3000 and 8000..."
lsof -ti :3000,8000 | xargs kill -9 2>/dev/null || echo "[*] Ports are already clear."

# Ensure Python dependencies for the runner are met (requests)
if ! python3 -c "import requests" &> /dev/null; then
    echo "[!] Installing missing dependencies for the launcher..."
    pip install requests &> /dev/null
fi

# Run the Python monitoring script
python3 run.py
