#!/bin/bash

# Activate the virtual environment
source .venv/bin/activate

# Define a cleanup function
# This function will be called when the script receives an exit signal.
cleanup() {
    echo "-> Shutting down services..."
    # Kill all child processes of this script
    pkill -P $$
    echo "-> Done."
}

# Trap the EXIT signal (e.g., from Ctrl+C) and run the cleanup function
trap cleanup EXIT

# Start services in the background
cloudflared tunnel run auto-ordering &> /dev/null &
python main.py &

# The script will now exit when the background processes are killed by the trap.
wait -n
