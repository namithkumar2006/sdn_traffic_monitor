#!/bin/bash
# run.sh – convenience script to launch the Ryu controller
# Usage: bash run.sh

echo "=============================================="
echo "  SDN Traffic Monitor – Controller Launcher"
echo "=============================================="
echo ""
echo "Starting Ryu controller with traffic_monitor module..."
echo "Press Ctrl+C to stop."
echo ""

# Navigate to the project root regardless of where this script is called from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

ryu-manager controller/traffic_monitor.py \
    --ofp-tcp-listen-port 6633 \
    --verbose
