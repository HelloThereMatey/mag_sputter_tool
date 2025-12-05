#!/bin/bash
# Wrapper script for MFC port detection utility
# Usage: ./detect_ports.sh [--arduino-port PORT] [--dry-run] [--verbose]

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Running MFC port detection..."
python3 detect_mfc_ports.py "$@"
