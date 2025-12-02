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
        self._device_is_ready = False  # Renamed to avoid conflict with signal
        self._stop_requested = False
        self._stop_event = threading.Event()  # Event for immediate thread wake-up
        self.auto_reconnect = True  # Enable auto-reconnection by default
        self.reconnect_delay = 3.0  # Seconds between reconnection attempts
        
        # Debounce: ignore same card read within this time (milliseconds)
        self.debounce_ms = 500
        self.last_card_id = None
        self.last_card_time = 0
    
    def run(self) -> None:
        """Main thread execution loop with auto-reconnection support."""
        self.running = True
        
        while self.running and not self._stop_requested:
            try:
                # Attempt connection
                if not self._connect_to_device():
                    if not self.auto_reconnect or self._stop_requested:
                        break
                    
                    # Wait before retry (interruptible by stop event)
                    self.status_changed.emit(f"🔄 Retrying in {self.reconnect_delay}s...")
                    if self._stop_event.wait(self.reconnect_delay):
                        # Event was set (stop requested)
                        break
                    continue
                
                # Main read loop
                self._read_loop()
                
                # If we exit read loop naturally, check if we should reconnect
                if not self.auto_reconnect or self._stop_requested:
                    break
                    
                # Connection lost - attempt reconnect (interruptible by stop event)
                self.status_changed.emit(f"🔄 Reconnecting in {self.reconnect_delay}s...")
                if self._stop_event.wait(self.reconnect_delay):
                    # Event was set (stop requested)
                    break
                
            except Exception as e:
                self.error_occurred.emit(f"❌ Thread error: {e}")
                
                if not self.auto_reconnect or self._stop_requested:
                    break
                    
                # Wait before retry (interruptible by stop event)
                if self._stop_event.wait(self.reconnect_delay):
                    # Event was set (stop requested)
                    break
        
        # Final cleanup
        self.disconnect()
        self.running = False
    
    def _connect_to_device(self) -> bool:
        """
        Attempt to connect to RFID reader.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._device_is_ready = False
            
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
                    return False
            
            # Connect to serial port
            self.status_changed.emit(f"🔌 Connecting to {self.port} @ {self.baudrate} baud...")
            
            try:
                self.serial_conn = serial.Serial(
                    self.port,
                    self.baudrate,
                    timeout=1.0
                )
                # Force DTR toggle to reset Pico and get READY message
                self.serial_conn.dtr = False
                time.sleep(0.1)
                self.serial_conn.dtr = True
                
            except serial.SerialException as e:
                self.error_occurred.emit(f"❌ Cannot connect to {self.port}: {e}")
                self.port = None  # Clear port so it will re-detect next time
                return False
            
            self.status_changed.emit(f"✓ Connected to {self.port}")
            
            # Wait for device ready message
            self._wait_for_device_ready()
            
            if not self._device_is_ready:
                # If we timed out waiting for ready, but we have a valid connection
                # and the port was likely auto-detected/cached correctly, we should PROCEED.
                # The device might just be already running or missed the reset.
                if not self._stop_requested:
                    print(f"⚠️ RFID Warning: 'PICO_RFID_READY' not received from {self.port}. Assuming device is active.")
                    self.status_changed.emit("✓ RFID ready (no startup msg)")
                    self._device_is_ready = True
                    self.device_ready.emit()
                    return True
                
                self.disconnect()
                self.port = None  # Clear port for re-detection
                return False
            
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"❌ Connection error: {e}")
            return False
    
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
                            self._device_is_ready = True
                            self.device_ready.emit()
                            return
                    else:
                        buffer += char
                
                time.sleep(0.01)  # Small delay to prevent busy-waiting
                
            except Exception as e:
                self.error_occurred.emit(f"Error waiting for device ready: {e}")
                return
        
        if not self._device_is_ready:
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
        
        # Signal the stop event to immediately wake thread from any sleep
        self._stop_event.set()
        
        # Wait for thread to finish (with timeout) - let run() do its cleanup
        if not self.wait(3000):  # 3 second timeout
            # The run() loop should have called disconnect() already
            # but ensure it's done
            self.disconnect()
    
    def disconnect(self) -> None:
        """Disconnect from serial port and cleanup."""
        try:
            if self.serial_conn:
                if self.serial_conn.is_open:
                    self.serial_conn.close()
                    # Only emit status if this was a clean shutdown (not an error)
                    if self._device_is_ready and not self._stop_requested:
                        self.status_changed.emit("📴 RFID reader disconnected")
                
                # Delete the serial connection object
                del self.serial_conn
                self.serial_conn = None
                
            # Reset state flags
            self._device_is_ready = False
            
        except Exception as e:
            # Don't emit signal if stop was requested (normal shutdown)
            if not self._stop_requested:
                self.error_occurred.emit(f"Error disconnecting: {e}")
    
    def is_connected(self) -> bool:
        """Check if currently connected to device."""
        return (self.serial_conn is not None and
                self.serial_conn.is_open and
                self._device_is_ready)
    
    def set_port(self, port: str) -> None:
        """Change the serial port before starting the thread."""
        if not self.running:
            self.port = port
    
    def set_baudrate(self, baudrate: int) -> None:
        """Change the baudrate before starting the thread."""
        if not self.running:
            self.baudrate = baudrate
