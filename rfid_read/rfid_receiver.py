#!/usr/bin/env python3
"""
RFID Card Receiver for Raspberry Pi 5 / Windows PC
Listens on serial port for RFID card IDs from Pico and integrates with tool control.

IMPORTANT: Port detection uses PICO_RFID_READY message verification!
  - Script tests all available serial ports
  - Waits for "PICO_RFID_READY:v1.0" message to confirm correct device
  - Aborts if no PICO ready message found within 3 seconds
  - This ensures correct port is used (e.g., /dev/ttyACM1 on RPi5, not USB0)

Hardware:
  - Pi5/PC serial port connected to Pico USB serial
  - Windows: COM ports (auto-detected or specified)
  - Linux/Pi5: /dev/ttyACM* or /dev/ttyUSB* (auto-detected, ACM preferred)
  - Baud rate: 115200

Usage:
  python3 rfid_receiver.py                    # Auto-detect port (tests all)
  python3 rfid_receiver.py /dev/ttyACM1       # Linux: specify port manually
  python3 rfid_receiver.py COM5 115200        # Windows: specify port and baud

Dependencies:
  pip install pyserial

Example integration:
  - When a card is read, you can log it, authenticate users, control tool access, etc.
  - Modify the on_card_read() callback to integrate with your control system.
"""

import serial
import time
import sys
import platform
import os
from datetime import datetime
from pathlib import Path
from serial.tools import list_ports


# Port cache file location
PORT_CACHE_FILE = Path(__file__).parent / ".rfid_port_cache.txt"


def save_port_cache(port):
    """Save the detected port to cache file for faster startup next time."""
    try:
        with open(PORT_CACHE_FILE, "w") as f:
            f.write(port.strip())
        print(f"💾 Cached port to {PORT_CACHE_FILE.name}")
    except Exception as e:
        print(f"⚠️  Warning: Could not save port cache: {e}")


def load_port_cache():
    """Load previously detected port from cache file if it exists."""
    if PORT_CACHE_FILE.exists():
        try:
            with open(PORT_CACHE_FILE, "r") as f:
                port = f.read().strip()
                if port:
                    print(f"📁 Loaded cached port: {port}")
                    return port
        except Exception as e:
            print(f"⚠️  Warning: Could not load port cache: {e}")
    return None


def verify_cached_port(port):
    """
    Verify that a cached port still has the Pico by checking for PICO_RFID_READY message.
    Returns True if port is valid, False otherwise.
    """
    print(f"✓ Testing cached port: {port}...", end=" ", flush=True)
    try:
        test_ser = serial.Serial(port, 115200, timeout=10.0)
        
        start_time = time.time()
        buffer = ""
        
        while time.time() - start_time < 10.0:
            if test_ser.in_waiting:
                chunk = test_ser.read(test_ser.in_waiting).decode('utf-8', errors='ignore')
                buffer += chunk
                
                if "PICO_RFID_READY" in buffer:
                    print("✓ FOUND!")
                    test_ser.close()
                    return True
            
            time.sleep(0.05)
        
        test_ser.close()
        print("✗ (no PICO_RFID_READY)")
        return False
        
    except (serial.SerialException, OSError) as e:
        print(f"✗ (error: {str(e)[:30]})")
        return False


def find_serial_port():
    """
    Auto-detect available serial ports on Windows/Linux.
    Tests each port to find the one with PICO_RFID_READY message.
    On RPi, prioritizes /dev/ttyACM* ports (native USB CDC).
    """
    ports = list_ports.comports()
    
    if not ports:
        print("✗ No serial ports found!")
        return None
    
    print("Available serial ports:")
    for port in ports:
        print(f"  {port.device} - {port.description}")
    
    # Determine platform and get candidate ports
    system = platform.system()
    candidates = []
    
    if system == "Windows":
        # Windows: try all non-system COM ports, prefer higher numbers
        system_ports = ["communications port", "intel", "management technology"]
        for port in ports:
            desc_lower = port.description.lower()
            if not any(sys_port in desc_lower for sys_port in system_ports):
                candidates.append(port.device)
        # Sort by COM number (reverse)
        candidates.sort(key=lambda p: int(p.device.replace("COM", "")), reverse=True)
    
    elif system in ["Linux", "Darwin"]:  # Linux or macOS
        # Priority 1: /dev/ttyACM* (native USB CDC - what Pico uses)
        acm_ports = [p.device for p in ports if "ttyACM" in p.device]
        # Priority 2: /dev/ttyUSB*
        usb_ports = [p.device for p in ports if "ttyUSB" in p.device]
        # Priority 3: other USB serial ports
        other_ports = [p.device for p in ports if "USB" in p.description or "usb" in p.description]
        
        candidates = acm_ports + usb_ports + other_ports
    
    else:
        # Fallback: try all ports
        candidates = [p.device for p in ports]
    
    if not candidates:
        print("\n✗ No suitable serial ports found")
        return None
    
    print(f"\n🔍 Testing {len(candidates)} port(s) for PICO_RFID_READY message...")
    print("   (This may take a few seconds)\n")
    
    # Test each candidate port for PICO_RFID_READY message
    for port_device in candidates:
        print(f"  Testing: {port_device}...", end=" ", flush=True)
        
        try:
            test_ser = serial.Serial(port_device, 115200, timeout=10.0)
            
            # Wait up to 10 seconds for PICO_RFID_READY message
            start_time = time.time()
            buffer = ""
            found_pico = False
            
            while time.time() - start_time < 10.0:
                if test_ser.in_waiting:
                    chunk = test_ser.read(test_ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += chunk
                    
                    # Check for PICO_RFID_READY in buffer
                    if "PICO_RFID_READY" in buffer:
                        print("✓ FOUND!")
                        test_ser.close()
                        save_port_cache(port_device)  # Cache the port for next time
                        return port_device
                
                time.sleep(0.05)
            
            test_ser.close()
            print("✗ (no PICO_RFID_READY)")
            
        except (serial.SerialException, OSError) as e:
            print(f"✗ (error: {str(e)[:30]})")
    
    print("\n✗ PICO_RFID_READY message not found on any port!")
    print("   Make sure:")
    print("   1. Pico is connected via USB")
    print("   2. Pico has RFID firmware uploaded (main.py)")
    print("   3. Firmware sends 'PICO_RFID_READY:v1.0' on startup")
    
    return None


class RFIDReceiver:
    def __init__(self, port, baud_rate):
        self.port = port
        self.baud_rate = baud_rate
        self.running = False
        self.ser = None
        self.device_identified = False
        
    def connect(self):
        """Open serial connection to Pico and verify PICO_RFID_READY message"""
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=1)
            print(f"✓ Connected to {self.port} at {self.baud_rate} baud")
            
            # Wait for PICO_RFID_READY message to confirm correct port
            print(f"🔍 Waiting for PICO_RFID_READY message to confirm device...")
            
            start_time = time.time()
            buffer = ""
            timeout = 11.0  # 11 seconds to get ready message
            
            while time.time() - start_time < timeout:
                if self.ser.in_waiting:
                    chunk = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += chunk
                    
                    # Look for PICO_RFID_READY in buffer
                    if "PICO_RFID_READY" in buffer:
                        # Extract version if present
                        for line in buffer.split('\n'):
                            if "PICO_RFID_READY" in line:
                                print(f"✓ Device confirmed: {line.strip()}\n")
                                self.device_identified = True
                                self.running = True
                                return True
                
                time.sleep(0.05)
            
            # Timeout - no PICO_RFID_READY received
            print(f"✗ TIMEOUT: No PICO_RFID_READY message received after {timeout}s")
            print(f"   This port ({self.port}) does not have the Pico RFID reader!")
            self.ser.close()
            return False
            
        except serial.SerialException as e:
            print(f"✗ Failed to connect to {self.port}: {e}")
            return False
    
    def on_card_read(self, card_id):
        """
        Callback when a new card is read.
        Integrate your tool control logic here.
        
        Args:
            card_id (str): Unique card ID from RFID tag (e.g., "08:5C:D1:4C")
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 🏷️  Card read: {card_id}")
        
        # TODO: Implement your integration here
        # Examples:
        #   - Check against authorized cards database
        #   - Log usage to file/database
        #   - Send signal to Arduino/tool control system
        #   - Grant/deny access based on card ID
        #   - Track time-in and time-out
        pass
    
    def run(self):
        """Main loop: read from serial and process card IDs"""
        # Connect and verify device
        if not self.connect():
            print("✗ Aborting: Could not connect to PICO RFID reader")
            return
        
        print("="*70)
        print("RFID Card Receiver - LISTENING FOR CARDS")
        print("="*70)
        print(f"Port: {self.port} | Baud: {self.baud_rate}")
        print("Listening for RFID cards from Pico...")
        print("Press Ctrl+C to exit\n")
        
        buffer = ""
        
        try:
            while self.running:
                if self.ser.in_waiting:
                    # Read available data
                    chunk = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += chunk
                    
                    # Process complete lines (delimited by \n)
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        
                        if not line:  # Skip empty lines
                            continue
                        
                        # Skip periodic ready messages (once we've confirmed device)
                        if "PICO_RFID_READY" in line and self.device_identified:
                            continue
                        
                        # Process as card ID
                        print(f"{line}")
                        self.on_card_read(line)
                
                time.sleep(0.01)  # Prevent busy-waiting
        
        except KeyboardInterrupt:
            print("\n\n✓ Shutdown requested by user")
        except serial.SerialException as e:
            print(f"\n✗ Serial error: {e}")
        except Exception as e:
            print(f"\n✗ Unexpected error: {e}")
        finally:
            self.disconnect()
    
    def disconnect(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.running = False
        print("✓ Serial connection closed")


def main():
    print("="*70)
    print("RFID Card Receiver for Sputter Control System")
    print(f"Platform: {platform.system()}")
    print("="*70 + "\n")
    
    # Parse command line arguments
    port = None
    baud = 115200
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
        if len(sys.argv) > 2:
            try:
                baud = int(sys.argv[2])
            except ValueError:
                print(f"✗ Invalid baud rate: {sys.argv[2]}")
                sys.exit(1)
        
        print(f"🔧 Using specified port: {port}\n")
    else:
        # First, try to use cached port from previous run
        cached_port = load_port_cache()
        if cached_port:
            if verify_cached_port(cached_port):
                port = cached_port
                print()  # Blank line for readability
            else:
                print("⚠️  Cached port no longer valid, running full port detection...\n")
        
        # If no valid cached port, do full auto-detection
        if not port:
            port = find_serial_port()
    
    if not port:
        print("\n✗ Could not find RFID reader device\n")
        print("Usage:")
        print("  python3 rfid_receiver.py                    # Auto-detect port")
        print("  python3 rfid_receiver.py /dev/ttyACM1       # Specify port (Linux/RPi)")
        print("  python3 rfid_receiver.py COM5 115200        # Specify port and baud (Windows)\n")
        print("Troubleshooting:")
        print("  1. Verify Pico is connected via USB")
        print("  2. Check Pico firmware has main.py with RFID code")
        print("  3. Ensure firmware sends 'PICO_RFID_READY:v1.0' on startup")
        print("  4. Try manually specifying the port\n")
        sys.exit(1)
    
    receiver = RFIDReceiver(port, baud)
    receiver.run()


if __name__ == "__main__":
    main()

