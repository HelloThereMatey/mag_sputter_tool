# MAG_SPUTTER_TOOL

**Version 1.0** - Automated Control System for Magnetron Sputtering

A complete hardware and software control system for DC/RF magnetron sputtering deposition, built on low-cost open-source platforms (Raspberry Pi 5 + Arduino Mega 2560 R3).

![System Status](https://img.shields.io/badge/status-production-green)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red)
![Python](https://img.shields.io/badge/python-3.10-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## 🎯 Overview

This project provides a modern replacement for aging LabVIEW-based vacuum sputter control systems. It delivers:

- **Automated vacuum procedures** (pump-down, venting, load-lock operation, sputtering)
- **Real-time safety interlocks** with configurable YAML-based safety rules
- **Multi-level user authentication** (Admin, Operator, Technician)
- **Mass flow controller integration** for process gas management (Alicat APEX)
- **Live pressure monitoring** with data logging and visualization
- **Manual and override modes** for maintenance and troubleshooting
- **Touch-screen optimized GUI** built with PyQt5

The system controls **23 relay outputs** (pumps, valves, gas lines, shutters) and monitors **4 digital inputs** (safety interlocks) and **4 analog inputs** (pressure gauges, turbo spin speed).

---

## 🏗️ System Architecture

### Hardware Platform

#### Control Electronics
- **Host Computer**: Raspberry Pi 5 (8GB RAM recommended)
- **I/O Controller**: Arduino Mega 2560 R3
- **Communication**: USB serial (9600 baud)
- **Relay Interface**: 16-channel relay modules (12V DC coil)
- **Power**: 12V/5V DC power supplies for relays and logic

#### Vacuum System Components
- **Main Chamber**: High-vacuum chamber with turbomolecular pump and scroll pump
- **Load-Lock**: Secondary chamber for sample loading without breaking main vacuum
- **Pressure Monitoring**: 
  - 2× Pirani gauges (load-lock and chamber rough vacuum)
  - 1× Ion gauge (high vacuum measurement)
  - 1× Turbo spin speed monitor
- **Safety Interlocks**:
  - Door closure switch (safety)
  - Water flow switch (cooling verification)
  - Load-lock rod home position switch
  - Spare input (reserved)

#### Process Gas System
- **Mass Flow Controllers**: Alicat APEX (RS-232 serial)
- **Process Gases**: Argon, Nitrogen, Oxygen (configurable)
- **Flow Range**: Typically 0-200 sccm per channel

---

### Software Architecture

#### Application Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    PyQt5 GUI (app.py)                       │
│  Touch-optimized interface, automated procedures, plotting  │
└───────────────────┬─────────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┬─────────────────┐
    │               │               │                 │
┌───▼────┐   ┌──────▼──────┐  ┌────▼─────┐   ┌──────▼──────┐
│ Safety │   │   Arduino   │  │   Gas    │   │   Security  │
│ System │   │ Controller  │  │  Control │   │   Manager   │
└────────┘   └─────────────┘  └──────────┘   └─────────────┘
    │               │               │                 │
    │        ┌──────▼──────┐        │                 │
    │        │   Serial    │        │                 │
    │        │ 9600 baud   │        │                 │
    │        └──────┬──────┘        │                 │
    │               │               │                 │
    │        ┌──────▼──────────┐    │                 │
    │        │  Arduino Mega   │    │                 │
    │        │  Relay Firmware │    │                 │
    │        └─────────────────┘    │                 │
    │                               │                 │
    └───────────────────────────────┴─────────────────┘
                          │
              ┌───────────▼───────────┐
              │  Configuration Files  │
              │  (YAML-based rules)   │
              └───────────────────────┘
```

#### Core Modules

**1. Main Application (`python/app.py`)**
- PyQt5 GUI with timer-based state monitoring (700ms refresh)
- Background procedure execution via QThreadPool
- Real-time pressure and sensor display
- Mode management (Normal/Manual/Override)

**2. Arduino Controller (`python/arduino_controller.py`)**
- Thread-safe serial communication
- Relay state management (23 relays)
- Digital input reading (4 interlocks)
- Analog input reading (4 pressure sensors)
- Automatic reconnection logic

**3. Safety System (`python/safety/`)**
- **`safety_controller.py`**: Central safety evaluator
  - YAML-based condition evaluation (OR/AND logic)
  - System state auto-detection (vented, rough pump, turbo pump, sputter)
  - Button enable/disable logic
  - Confirmation dialogs for risky operations
- **`safety_conditions.yml`**: Safety rules database
  - Emergency stop conditions
  - Pressure thresholds
  - Relay dependency checks
  - Interlock requirements

**4. Automated Procedures (`python/auto_procedures.py`)**
- `pump_down()`: Multi-stage pump sequence
- `vent_system()`: Safe chamber venting
- `load_unload()`: Load-lock sample transfer
- `sputter()`: Sputtering mode activation
- Real-time feedback and cancellation support

**5. Gas Control (`python/gas_control/`)**
- **`subprocess_controller.py`**: MFC driver (subprocess-based for serial stability)
- **`recipes.py`**: Gas flow presets
- **`safety_integration.py`**: Gas flow safety checks
- **`config.yml`**: MFC serial ports and gas types

**6. Security (`python/security/`)**
- **`password_manager.py`**: bcrypt password hashing
- **`user_account_manager.py`**: Role-based access control
- **`reset_passwords.py`**: Emergency admin tools

**7. UI Widgets (`python/widgets/`)**
- Status indicators
- MFC setpoint dialog
- Mode selection dialog
- Real-time data plotter
- Password setup dialog
- Analog recorder (CSV data logging)

#### Arduino Firmware (`relay_controller/relay_controller.ino`)

**Responsibilities:**
- Hardware-level relay control (pins 22-41, 44, 46, 48)
- Digital input monitoring with pull-ups (pins 45, 47, 49, 51)
- Analog input reading (A1-A4: Load-lock, Chamber, Ion gauge, Turbo)
- Serial protocol implementation
- Safety interlocks (hardware-enforced)

**Command Protocol:**
- Commands: `RELAY_X_ON`, `RELAY_X_OFF` (X = 1-23)
- Queries: `GET_RELAY_STATUS`, `GET_DIGITAL_INPUTS`, `GET_ANALOG_INPUTS`
- Responses: `OK`, `ERROR`, data arrays

---

## 📁 Repository Structure

```
auto_control/
├── python/                          # Main application code
│   ├── app.py                       # PyQt5 GUI application
│   ├── main.py                      # Entry point
│   ├── config.py                    # Configuration loader
│   ├── arduino_controller.py        # Serial communication
│   ├── auto_procedures.py           # Automated sequences
│   ├── safety/                      # Safety interlock system
│   │   ├── safety_controller.py     # Safety logic engine
│   │   └── safety_conditions.yml    # Safety rules (YAML)
│   ├── security/                    # User authentication
│   │   ├── password_manager.py
│   │   └── user_account_manager.py
│   ├── gas_control/                 # Mass flow controllers
│   │   ├── subprocess_controller.py
│   │   ├── recipes.py
│   │   └── config.yml
│   ├── widgets/                     # PyQt5 UI components
│   │   ├── indicators.py
│   │   ├── mfc_dialog.py
│   │   ├── mode_dialog.py
│   │   ├── plotter_widget.py
│   │   └── analog_recorder.py
│   └── tests/                       # Unit tests
├── relay_controller/                # Arduino firmware
│   └── relay_controller.ino         # Arduino Mega sketch
├── docs/                            # Documentation
│   ├── TECHNICAL_MANUAL.md          # Hardware pin assignments
│   ├── software_manual.md           # Software architecture
│   ├── SOP_new.md                   # Standard operating procedure
│   ├── SECURITY_README.md           # User account management
│   └── pics/                        # Hardware photos
├── sput.yml                         # Runtime configuration
├── vacuum_system_gui.ui             # Qt Designer UI file
└── README.md                        # This file

gas_control_all/                     # MFC development & testing
launcher/                            # Desktop launcher scripts
relay_test_system/                   # Hardware testing utilities
```

---

## 🚀 Quick Start

### Prerequisites

- Raspberry Pi 5 (or compatible Linux system)
- Python 3.10+
- Arduino Mega 2560 R3 with firmware uploaded
- PyQt5, pyserial, PyYAML, alicat, cryptography

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/HelloThereMatey/MAG_SPUTTER_TOOL.git
   cd MAG_SPUTTER_TOOL/auto_control
   ```

2. **Create conda environment** (recommended)
   ```bash
   conda env create -f sput.yml
   conda activate sput
   ```

3. **Upload Arduino firmware**
   - Open `relay_controller/relay_controller.ino` in Arduino IDE
   - Select board: Arduino Mega 2560
   - Upload to Arduino

4. **Configure system**
   - Edit `sput.yml` for relay pin assignments
   - Edit `python/safety/safety_conditions.yml` for safety rules
   - Edit `python/gas_control/config.yml` for MFC serial ports

5. **Launch application**
   ```bash
   cd python
   python main.py
   ```

### First-Time Setup

- **Password Setup**: On first launch, create admin password
- **Mode Selection**: Choose Normal/Manual/Override mode
- **Port Configuration**: Verify Arduino auto-detects on correct serial port

---

## 🔒 Operation Modes

### Normal Mode (Production)
- Automated procedures only (PUMP, VENT, SPUTTER, etc.)
- Full safety checks enforced
- Manual controls disabled

### Manual Mode (Maintenance)
- All buttons enabled (automated + manual)
- Full safety checks enforced
- Confirmation dialogs active

### Override Mode ⚠️ (Emergency Only)
- All controls unrestricted
- **ALL SAFETY CHECKS BYPASSED**
- Use only for recovery/troubleshooting
- Requires admin authentication

---

## 📊 Key Features

### Automated Procedures
- **Pump-Down**: Multi-stage vacuum sequence (rough → medium → high vacuum)
- **Vent**: Safe chamber venting with interlock verification
- **Load/Unload**: Automated load-lock sample transfer
- **Sputter**: Sputtering mode activation (ion gauge + gas flow)

### Safety System
- YAML-based safety rules (no code changes required)
- Real-time system state detection
- Pressure threshold monitoring
- Digital interlock verification (door, water, rod position)
- Automatic emergency shutdown

### Data Logging
- Real-time pressure plotting
- CSV data export (analog recorder)
- Session logbook integration
- Timestamped event logging

### Gas Flow Management
- Multi-channel MFC control (Alicat APEX)
- Recipe-based flow presets
- Real-time flow monitoring
- Safety interlocks (pressure-dependent gas flow)

---

## 🔧 Configuration

### Hardware Configuration (`sput.yml`)

```yaml
serial:
  baud: 9600
  preferred_ports: [/dev/ttyACM0, /dev/ttyUSB3]

relays:
  btnPumpTurbo: 37
  btnValveTurboGate: 27
  btnValveRough: 25
  btnIonGauge: 35
  # ... (23 total relays)

analog_inputs:
  A1: loadlock_pirani
  A2: chamber_pirani
  A3: ion_gauge
  A4: turbo_spin_speed

pressure_thresholds:
  high_vacuum: 1.0e-5
  medium_vacuum: 1.0e-2
  rough_vacuum: 1.0
```

### Safety Rules (`python/safety/safety_conditions.yml`)

```yaml
safety_conditions:
  emergency_stop:
    - condition: door_open
      message: "Emergency: Chamber door opened!"
    - condition: water_flow_stopped
      message: "Emergency: Cooling water flow lost!"

button_conditions:
  btnPumpTurbo:
    enable_if:
      - pressure < 1e-2  # Chamber must be rough pumped
      - relay_rough_valve == ON
```

---

## 📖 Documentation

- **[TECHNICAL_MANUAL.md](docs/TECHNICAL_MANUAL.md)**: Hardware pin assignments, relay configuration
- **[software_manual.md](docs/software_manual.md)**: Software architecture, module details
- **[SOP_new.md](docs/SOP_new.md)**: Standard operating procedure (user guide)
- **[SECURITY_README.md](docs/SECURITY_README.md)**: User account management

---

## 🧪 Testing

### Hardware Testing
```bash
cd relay_test_system/python
python platform_test.py  # Verify relay control
python port_tester.py    # Test serial communication
```

### Software Testing
```bash
cd auto_control/python/tests
pytest test_arduino_relay.py
pytest test_mode_dialog.py
```

---

## 🛠️ Hardware Pinout Reference

### Arduino Mega 2560 R3

| Pin Range | Function | Description |
|-----------|----------|-------------|
| 22-41, 44, 46, 48 | Relay Outputs | 23 relay control pins |
| 45, 47, 49, 51 | Digital Inputs | Safety interlocks (pulled high, active low) |
| A1-A4 | Analog Inputs | Pressure sensors + turbo speed |

**Critical Pins:**
- **Pin 22**: Mains power safety relay (CRITICAL)
- **Pin 37**: Turbo pump control
- **Pin 35**: Ion gauge activation
- **Pin 44**: Scroll pump solid-state relay

---

## 🤝 Contributing

This project is open-source. Contributions welcome for:
- Additional safety features
- UI improvements
- Documentation enhancements
- Bug fixes

---

## 📝 License

MIT License - See LICENSE file for details

---

## 👤 Author

**HelloThereMatey**

For questions, issues, or feature requests, please open an issue on GitHub.

---

## 🙏 Acknowledgments

Built for the Materials Science research community as a modern, open-source alternative to proprietary vacuum control systems.

**Technology Stack:**
- Python 3.10
- PyQt5
- Arduino (C++)
- Raspberry Pi OS
- Alicat MFC Protocol

---

## ⚠️ Safety Disclaimer

This system controls high-vacuum equipment, high-voltage power supplies, and pressurized gas systems. Improper use can cause equipment damage, personal injury, or death.

- **Training required** before operation
- **Follow all safety protocols** in SOP documentation
- **Test safety interlocks** regularly
- **Never bypass safety systems** except in documented emergency procedures

**The authors assume no liability for damages resulting from use of this software.**
