from __future__ import annotations

import os
import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SerialConfig:
    baud: int = 9600
    arduino_port: Optional[str] = None  # Hardcoded Arduino port
    rfid_port: Optional[str] = None  # Hardcoded RFID port
    preferred_ports: List[str] = None  # Fallback ports (deprecated)


@dataclass
class AppConfig:
    serial: SerialConfig
    relays: Dict[str, int]
    inputs_labels: List[str]
    analog_channels: List[Dict[str, float]]
    # Order of Arduino pins used by firmware for RELAY_1..N (1-based index)
    relay_pins: List[int]
    # Gas control configuration (optional)
    gas_control: Optional[Dict] = None


DEFAULT_CONFIG: AppConfig | None = None


def load_config(path: Optional[str] = None) -> AppConfig:
    """Load YAML config (sput.yml)."""
    if path is None:
        # default to project root auto_control/sput.yml
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, "sput.yml")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    serial = data.get("serial", {})
    serial_cfg = SerialConfig(
        baud=int(serial.get("baud", 9600)),
        arduino_port=serial.get("arduino_port"),
        rfid_port=serial.get("rfid_port"),
        preferred_ports=list(serial.get("preferred_ports", []) or []),
    )

    relays = {str(k): int(v) for k, v in (data.get("relays", {}) or {}).items()}

    inputs = data.get("inputs", {})
    inputs_labels = list(inputs.get("digital_labels", ["Door", "Water", "Rod"]))

    analog = data.get("analog", {})
    analog_channels = list(analog.get("channels", [
        {"label": "AI1", "scale": 1.0, "offset": 0.0},
        {"label": "AI2", "scale": 1.0, "offset": 0.0},
        {"label": "AI3", "scale": 1.0, "offset": 0.0},
        {"label": "AI4", "scale": 1.0, "offset": 0.0},
    ]))

    # Default firmware mapping for Arduino Mega (matching relay_controller.ino and sput.yml)
    default_relay_pins = [
        22,  # Mains power (relay 1) - CRITICAL SAFETY
        23, 24, 25, 26, 36, 28, 29,
        30, 31, 32, 33, 34, 35, 27, 37,
        38, 39, 40, 41,
        44,  # Scroll pump (relay 21)
        46,  # Spare relay (relay 22)
        48   # Spare relay (relay 23)
    ]
    relay_pins = list(data.get("relay_pins", default_relay_pins))

    # Load gas control configuration if present
    gas_control = data.get("gas_control", None)

    cfg = AppConfig(
        serial=serial_cfg,
        relays=relays,
        inputs_labels=inputs_labels,
        analog_channels=analog_channels,
        relay_pins=relay_pins,
        gas_control=gas_control,
    )

    global DEFAULT_CONFIG
    DEFAULT_CONFIG = cfg
    return cfg
