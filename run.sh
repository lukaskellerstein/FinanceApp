#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Set DISPLAY for X11 forwarding (if needed)
if [ -z "$DISPLAY" ]; then
    export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
    echo "Set DISPLAY to: $DISPLAY"
fi

# Run the application
echo "Starting Finance App..."
python -m finance_app.main
