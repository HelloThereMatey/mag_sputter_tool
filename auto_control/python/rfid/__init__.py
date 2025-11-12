"""
RFID Integration Package for Sputter Control System

Provides RFID card reading capabilities integrated with PyQt5 GUI.
"""

from .config import RFIDConfig
from .reader_thread import RFIDReaderThread

__all__ = ['RFIDConfig', 'RFIDReaderThread']
