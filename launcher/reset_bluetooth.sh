#!/bin/bash

# Bluetooth Reset and Reconnection Script
# Usage: ./bluetooth_reset.sh [MAC_ADDRESS]
# Example: ./bluetooth_reset.sh AA:BB:CC:DD:EE:FF

set -e  # Exit on any error

MAC_ADDRESS="${1:-}"

if [ -z "$MAC_ADDRESS" ]; then
    echo "❌ Usage: $0 <MAC_ADDRESS>"
    echo "Example: $0 AA:BB:CC:DD:EE:FF"
    exit 1
fi

echo "🔄 Starting Bluetooth reset and reconnection procedure..."
echo "Target device: $MAC_ADDRESS"

# Step 1: Stop Bluetooth service
echo "Step 1: Stopping Bluetooth service..."
sudo systemctl stop bluetooth
sleep 2
echo "✅ Bluetooth service stopped"

# Step 2: Clear Bluetooth cache and state
echo "Step 2: Clearing Bluetooth cache..."
sudo rm -rf /var/lib/bluetooth/*
sleep 1
echo "✅ Bluetooth cache cleared"

# Step 3: Start Bluetooth service
echo "Step 3: Starting Bluetooth service..."
sudo systemctl start bluetooth
sleep 3
echo "✅ Bluetooth service restarted"

# Step 4: Power cycle the Bluetooth adapter
echo "Step 4: Power cycling Bluetooth adapter..."
sudo hciconfig hci0 down
sleep 2
sudo hciconfig hci0 up
sleep 2
echo "✅ Bluetooth adapter power cycled"

# Step 5: Verify adapter is up
echo "Step 5: Verifying adapter status..."
ADAPTER_STATUS=$(hciconfig hci0 | grep -i "up" | wc -l)
if [ "$ADAPTER_STATUS" -eq 0 ]; then
    echo "❌ ERROR: Bluetooth adapter failed to come up!"
    exit 1
fi
echo "✅ Adapter is UP and ready"

# Step 6: Attempt to reconnect to the device
echo "Step 6: Attempting to reconnect to device $MAC_ADDRESS..."
echo "⏳ Waiting for device to be discoverable (make sure device is in pairing mode)..."

# Give device time to respond (scan for 10 seconds)
timeout 15 bluetoothctl scan on &
SCAN_PID=$!
sleep 10

# Stop scanning
kill $SCAN_PID 2>/dev/null || true
sleep 2

# Step 7: Try to connect
echo "Step 7: Attempting connection to $MAC_ADDRESS..."
if bluetoothctl connect "$MAC_ADDRESS" 2>&1 | grep -q "Connection successful"; then
    echo "✅ Successfully connected to $MAC_ADDRESS!"
    
    # Verify connection
    sleep 2
    DEVICE_INFO=$(bluetoothctl info "$MAC_ADDRESS" 2>/dev/null || echo "")
    
    if echo "$DEVICE_INFO" | grep -q "Connected: yes"; then
        echo "✅ Connection verified!"
        echo ""
        echo "Device information:"
        bluetoothctl info "$MAC_ADDRESS"
        exit 0
    else
        echo "⚠️ Connection was accepted but verification shows disconnected"
        echo "Try the following manual steps:"
        echo "1. Enter bluetoothctl: bluetoothctl"
        echo "2. Trust the device: trust $MAC_ADDRESS"
        echo "3. Connect: connect $MAC_ADDRESS"
        echo "4. If prompted on device, approve the pairing"
        exit 1
    fi
else
    echo "⚠️ Connection attempt did not succeed automatically"
    echo ""
    echo "The device may need to be manually re-paired. Try one of these approaches:"
    echo ""
    echo "Option A: Manual reconnect (if already paired):"
    echo "  bluetoothctl"
    echo "  > connect $MAC_ADDRESS"
    echo ""
    echo "Option B: Full re-pair (if Option A fails):"
    echo "  bluetoothctl"
    echo "  > remove $MAC_ADDRESS"
    echo "  > scan on"
    echo "  (Press pairing button on your device now)"
    echo "  > pair $MAC_ADDRESS"
    echo "  > connect $MAC_ADDRESS"
    echo "  > trust $MAC_ADDRESS"
    exit 1
fi