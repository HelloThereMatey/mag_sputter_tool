"""
RFID Reader Thread for PyQt5 Integration

Runs RFID reader in background thread and emits Qt signals when cards are read.
Handles serial communication with Pico RFID reader in a thread-safe manner.
"""

import serial
import threading
import time
from typing import Optional, Callable
from PyQt5.QtCore import QThread, pyqtSignal, Qt

try:
    from .config import RFIDConfig
except ImportError:
    from config import RFIDConfig


class RFIDReaderThread(QThread):
    """
    Background thread for reading RFID cards from Pico.
    Emits Qt signals when cards are detected.
    """
    
    # Qt Signals
    card_detected = pyqtSignal(str)  # Emitted when card ID is read
    device_ready = pyqtSignal()  # Emitted when Pico is identified and ready
    device_lost = pyqtSignal()  # Emitted when device connection is lost
    error_occurred = pyqtSignal(str)  # Emitted when error occurs
    status_changed = pyqtSignal(str)  # General status updates
    
    def __init__(self, port: Optional[str] = None, baudrate: int = RFIDConfig.DEFAULT_BAUDRATE):
        """
        Initialize RFID reader thread.
        
        Args:
            port: Serial port device (e.g., "COM5", "/dev/ttyACM0")
                  If None, will auto-detect
            baudrate: Serial connection speed (default 115200 for Pico)
        """
        super().__init__()
        
        self.port = port
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.running = False
        self.device_ready = False
        self._stop_requested = False
        
        # Debounce: ignore same card read within this time (milliseconds)
        self.debounce_ms = 500
        self.last_card_id = None
        self.last_card_time = 0
    
    def run(self) -> None:
        """Main thread execution loop."""
        try:
            self.running = True
            
            # Find port if not specified
            if self.port is None:
                self.status_changed.emit("🔍 Searching for RFID reader...")
                
                # Try cached port first
                cached_port = RFIDConfig.try_cached_port()
                if cached_port:
                    self.port = cached_port
                    self.status_changed.emit(f"📍 Using cached port: {self.port}")
                else:
                    self.port = RFIDConfig.find_rfid_port()
                
                if self.port is None:
                    self.error_occurred.emit("❌ RFID reader not found. Is Pico connected?")
                    self.running = False
                    return
            
            # Connect to serial port
            self.status_changed.emit(f"🔌 Connecting to {self.port} @ {self.baudrate} baud...")
            
            try:
                self.serial_conn = serial.Serial(
                    self.port,
                    self.baudrate,
                    timeout=1.0
                )
            except serial.SerialException as e:
                self.error_occurred.emit(f"❌ Cannot connect to {self.port}: {e}")
                self.running = False
                return
            
            self.status_changed.emit(f"✓ Connected to {self.port}")
            
            # Wait for device ready message
            self._wait_for_device_ready()
            
            if not self.device_ready and not self._stop_requested:
                self.error_occurred.emit("❌ RFID reader did not respond with ready message")
                self.disconnect()
                self.running = False
                return
            
            # Main read loop
            self._read_loop()
            
        except Exception as e:
            self.error_occurred.emit(f"❌ Thread error: {e}")
        finally:
            self.disconnect()
            self.running = False
    
    def _wait_for_device_ready(self, timeout: float = 5.0) -> None:
        """
        Wait for Pico to send ready message.
        
        Args:
            timeout: Seconds to wait for ready message
        """
        start_time = time.time()
        buffer = ""
        
        while time.time() - start_time < timeout and not self._stop_requested:
            try:
                if self.serial_conn and self.serial_conn.in_waiting:
                    byte = self.serial_conn.read(1)
                    if not byte:
                        continue
                    
                    char = byte.decode('utf-8', errors='ignore')
                    
                    if char == '\n':
                        line = buffer.strip()
                        buffer = ""
                        
                        if RFIDConfig.READY_MESSAGE in line:
                            self.status_changed.emit("✓ RFID reader ready")
                            self.device_ready = True
                            self.device_ready.emit()
                            return
                    else:
                        buffer += char
                
                time.sleep(0.01)  # Small delay to prevent busy-waiting
                
            except Exception as e:
                self.error_occurred.emit(f"Error waiting for device ready: {e}")
                return
        
        if not self.device_ready:
            self.error_occurred.emit("Timeout waiting for RFID reader ready message")
    
    def _read_loop(self) -> None:
        """Main loop for reading RFID card IDs."""
        buffer = ""
        
        while self.running and not self._stop_requested:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    self.device_lost.emit()
                    self.status_changed.emit("❌ Serial connection lost")
                    break
                
                # Read available data
                if self.serial_conn.in_waiting:
                    byte = self.serial_conn.read(1)
                    if not byte:
                        continue
                    
                    char = byte.decode('utf-8', errors='ignore')
                    
                    # Process complete line
                    if char == '\n':
                        line = buffer.strip()
                        buffer = ""
                        
                        # Ignore ready messages and empty lines
                        if not line or RFIDConfig.READY_MESSAGE in line:
                            continue
                        
                        # Card ID should be in format: "08:5C:D1:4C" or similar
                        if self._is_valid_card_id(line):
                            self._process_card_id(line)
                    else:
                        buffer += char
                
                time.sleep(0.01)  # Small delay to prevent busy-waiting
                
            except Exception as e:
                self.error_occurred.emit(f"Error reading from device: {e}")
                self.device_lost.emit()
                break
    
    def _is_valid_card_id(self, line: str) -> bool:
        """
        Check if line appears to be a valid card ID.
        
        Expected format: "08:5C:D1:4C" (hex pairs separated by colons)
        or similar alphanumeric format.
        """
        # Remove whitespace
        line = line.strip()
        
        # Must have some content
        if not line or len(line) < 2:
            return False
        
        # Should not contain common markers
        if any(x in line.lower() for x in ['ready', 'error', 'fail']):
            return False
        
        # Basic validation: allow hex:hex:hex:hex or similar patterns
        # Could be "08:5C:D1:4C" or "08-5C-D1-4C" or similar
        if ':' in line or '-' in line or line.isalnum():
            return True
        
        return False
    
    def _process_card_id(self, card_id: str) -> None:
        """
        Process a detected card ID with debouncing.
        
        Args:
            card_id: The RFID card ID string
        """
        current_time = time.time() * 1000  # Convert to milliseconds
        
        # Debounce: ignore if same card read too soon
        if (card_id == self.last_card_id and
            current_time - self.last_card_time < self.debounce_ms):
            return
        
        # Emit signal with card ID
        self.status_changed.emit(f"🏷️  Card detected: {card_id}")
        self.card_detected.emit(card_id)
        
        # Update tracking
        self.last_card_id = card_id
        self.last_card_time = current_time
    
    def stop(self) -> None:
        """Request thread to stop gracefully."""
        self._stop_requested = True
        self.running = False
        
        # Wait for thread to finish (with timeout)
        self.wait(timeout=3000)  # 3 second timeout
    
    def disconnect(self) -> None:
        """Disconnect from serial port."""
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                self.status_changed.emit("Disconnected from RFID reader")
        except Exception as e:
            self.error_occurred.emit(f"Error disconnecting: {e}")
    
    def is_connected(self) -> bool:
        """Check if currently connected to device."""
        return (self.serial_conn is not None and
                self.serial_conn.is_open and
                self.device_ready)
    
    def set_port(self, port: str) -> None:
        """Change the serial port before starting the thread."""
        if not self.running:
            self.port = port
    
    def set_baudrate(self, baudrate: int) -> None:
        """Change the baudrate before starting the thread."""
        if not self.running:
            self.baudrate = baudrate
