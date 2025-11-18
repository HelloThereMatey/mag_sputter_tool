#!/bin/bash
# Wrapper script for User Account Management CLI
# Makes it easier to run from anywhere

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/manage_users.py"

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ Error: manage_users.py not found at $PYTHON_SCRIPT"
    exit 1
fi

# Run Python script with all arguments
python3 "$PYTHON_SCRIPT" "$@"
