"""
RFID Configuration Module

Manages RFID reader settings and serial port configuration.
Provides auto-detection of Pico RFID reader on Windows/Linux.
"""

import platform
import time
import serial
from pathlib import Path
from typing import Optional, Tuple, List
from serial.tools import list_ports


class RFIDConfig:
    """RFID reader configuration and detection."""
    
    # Standard settings for Pico RFID reader
    DEFAULT_BAUDRATE = 115200
    READY_MESSAGE = "PICO_RFID_READY"
    CARD_ID_TIMEOUT = 5.0  # Timeout waiting for card ID (seconds)
    
    # Port cache for faster reconnection
    PORT_CACHE_FILE = Path.home() / ".sputter_control" / "rfid_port.txt"
    
    @staticmethod
    def _verify_port(port: str) -> bool:
        """
        Verify that a port has the Pico RFID reader by checking for READY_MESSAGE.
        """
        try:
            # Open port with timeout
            # Opening the port usually resets the Pico (DTR), causing it to send the ready message
            ser = serial.Serial(port, RFIDConfig.DEFAULT_BAUDRATE, timeout=2.0)
            
            # Wait for ready message
            start_time = time.time()
            while time.time() - start_time < 3.0:
                if ser.in_waiting:
                    try:
                        line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if RFIDConfig.READY_MESSAGE in line:
                            ser.close()
                            return True
                    except Exception:
                        pass
                time.sleep(0.1)
            
            ser.close()
        except Exception:
            pass
        return False

    @staticmethod
    def find_rfid_port() -> Optional[str]:
        """
        Auto-detect Pico RFID reader port by verifying READY_MESSAGE.
        Prioritizes USB Serial Devices (Pico) over other ports.
        """
        ports = list_ports.comports()
        if not ports:
            return None
        
        candidates = []
        system = platform.system()
        
        # Filter candidates based on OS to speed up search
        if system == "Windows":
            for p in ports:
                desc = p.description.lower()
                # Prioritize likely candidates
                if "usb serial device" in desc or "pico" in desc or "raspberry pi" in desc:
                    candidates.append(p.device)
                # Also check generic COM ports if they look like USB
                elif "com" in p.device.lower():
                     candidates.append(p.device)
        else:
            # Linux/Mac - Prioritize ttyACM (Pico usually shows as this)
            for p in ports:
                if "ttyACM" in p.device:
                    candidates.append(p.device)
            for p in ports:
                if "ttyUSB" in p.device:
                    candidates.append(p.device)
        
        # If no specific candidates found, try all available ports
        if not candidates:
            candidates = [p.device for p in ports]
            
        # Remove duplicates while preserving order
        candidates = list(dict.fromkeys(candidates))

        # Test candidates
        for port in candidates:
            if RFIDConfig._verify_port(port):
                RFIDConfig._cache_port(port)
                return port
        
        return None
    
    @staticmethod
    def try_cached_port() -> Optional[str]:
        """Try to load cached port and VERIFY it."""
        try:
            if RFIDConfig.PORT_CACHE_FILE.exists():
                cached = RFIDConfig.PORT_CACHE_FILE.read_text().strip()
                if cached:
                    # Verify port still exists in system
                    ports = [p.device for p in list_ports.comports()]
                    if cached in ports:
                        # Verify it's actually the RFID reader
                        if RFIDConfig._verify_port(cached):
                            return cached
        except Exception:
            pass
        return None
    
    @staticmethod
    def _cache_port(port: str) -> None:
        """Save port to cache file."""
        try:
            RFIDConfig.PORT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            RFIDConfig.PORT_CACHE_FILE.write_text(port)
        except Exception:
            pass
    
    @staticmethod
    def clear_port_cache() -> None:
        """Clear cached port (e.g., if port changes)."""
        try:
            if RFIDConfig.PORT_CACHE_FILE.exists():
                RFIDConfig.PORT_CACHE_FILE.unlink()
        except Exception:
            pass
    
    @staticmethod
    def get_available_ports() -> List[Tuple[str, str]]:
        """
        Get list of all available serial ports.
        
        Returns:
            List of (device, description) tuples
        """
        return [(p.device, p.description) for p in list_ports.comports()]
