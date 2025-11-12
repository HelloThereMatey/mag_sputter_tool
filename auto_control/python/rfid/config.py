"""
RFID Configuration Module

Manages RFID reader settings and serial port configuration.
Provides auto-detection of Pico RFID reader on Windows/Linux.
"""

import platform
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
    def find_rfid_port() -> Optional[str]:
        """
        Auto-detect Pico RFID reader port.
        Prioritizes USB Serial Devices (Pico) over other ports.
        
        Returns:
            Port device string (e.g., "COM5" on Windows, "/dev/ttyACM0" on Linux)
            or None if not found.
        """
        ports = list_ports.comports()
        
        if not ports:
            return None
        
        # On Windows, prefer "USB Serial Device" (Pico)
        if platform.system() == "Windows":
            # First priority: Generic "USB Serial Device"
            for port in ports:
                desc_lower = port.description.lower()
                if "usb serial device" in desc_lower:
                    RFIDConfig._cache_port(port.device)
                    return port.device
            
            # Second priority: Pico-specific
            for port in ports:
                desc_lower = port.description.lower()
                if any(kw in desc_lower for kw in ["pico", "raspberry pi", "rp2040"]):
                    RFIDConfig._cache_port(port.device)
                    return port.device
            
            # Third priority: Other USB serial adapters
            for port in ports:
                desc_lower = port.description.lower()
                if any(kw in desc_lower for kw in ["ch340", "cp210", "ftdi", "prolific"]):
                    RFIDConfig._cache_port(port.device)
                    return port.device
            
            # Fallback: use highest COM number (most likely external device)
            usable = [p for p in ports if "communications port" not in p.description.lower()]
            if usable:
                usable.sort(key=lambda p: int(p.device.replace("COM", "")), reverse=True)
                RFIDConfig._cache_port(usable[0].device)
                return usable[0].device
        
        # On Linux/RPi, prefer /dev/ttyUSB* or /dev/ttyACM*
        else:
            # First: ttyACM (usually Pico on Linux)
            for port in ports:
                if "ttyACM" in port.device:
                    RFIDConfig._cache_port(port.device)
                    return port.device
            
            # Second: ttyUSB
            for port in ports:
                if "ttyUSB" in port.device:
                    RFIDConfig._cache_port(port.device)
                    return port.device
        
        # Fallback: use first available
        if ports:
            RFIDConfig._cache_port(ports[0].device)
            return ports[0].device
        
        return None
    
    @staticmethod
    def try_cached_port() -> Optional[str]:
        """Try to load cached port from previous successful connection."""
        try:
            if RFIDConfig.PORT_CACHE_FILE.exists():
                cached = RFIDConfig.PORT_CACHE_FILE.read_text().strip()
                if cached:
                    # Verify port still exists
                    ports = [p.device for p in list_ports.comports()]
                    if cached in ports:
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
