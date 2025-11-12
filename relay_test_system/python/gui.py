"""
PyQt5 GUI for Relay Test System
Provides 16 toggle buttons for controlling relays via Arduino
"""

import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QGridLayout, QPushButton, 
                            QVBoxLayout, QHBoxLayout, QStatusBar, QMenuBar, 
                            QMessageBox, QComboBox, QLabel, QGroupBox, QLCDNumber)
from PyQt5.QtCore import QTimer, pyqtSignal, QThread, Qt
from PyQt5.QtGui import QAction, QFont, QPainter, QColor
from arduino_controller import ArduinoController


class LEDIndicator(QWidget):
    """Custom LED-style indicator widget with precise circular shape."""
    
    def __init__(self, size=20, parent=None):
        super().__init__(parent)
        self.size = size
        self.state = False  # False = red/off, True = green/on
        self.setFixedSize(size, size)
        
    def set_state(self, state: bool):
        """Set the LED state (True=green, False=red)."""
        if self.state != state:
            self.state = state
            self.update()  # Trigger repaint
    
    def paintEvent(self, event):
        """Custom paint event to draw the LED circle."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate circle dimensions with small margin
        margin = 2
        diameter = self.size - (2 * margin)
        
        # Set colors based on state
        if self.state:
            # Green for HIGH/ON
            fill_color = QColor(76, 175, 80)  # Green
            border_color = QColor(56, 142, 60)  # Darker green
        else:
            # Red for LOW/OFF
            fill_color = QColor(244, 67, 54)  # Red
            border_color = QColor(183, 28, 28)  # Darker red
        
        # Draw filled circle
        painter.setBrush(fill_color)
        painter.setPen(border_color)
        painter.drawEllipse(margin, margin, diameter, diameter)


class RelayButton(QPushButton):
    """Custom button for relay control with state tracking."""
    
    def __init__(self, relay_number: int):
        super().__init__()
        self.relay_number = relay_number
        self.relay_state = False
        self.setup_button()
        
    def setup_button(self):
        """Initialize button appearance and properties."""
        self.setText(f"Relay {self.relay_number}\nOFF")
        self.setMinimumSize(120, 80)  # Larger for landscape layout
        self.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.update_appearance()
        
    def set_state(self, state: bool):
        """Update button state and appearance."""
        self.relay_state = state
        self.setText(f"Relay {self.relay_number}\n{'ON' if state else 'OFF'}")
        self.update_appearance()
        
    def update_appearance(self):
        """Update button colors based on state."""
        if self.relay_state:
            # Green for ON
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 2px solid #45a049;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)
        else:
            # Red for OFF
            self.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: 2px solid #da190b;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                }
            """)


class ConnectionWorker(QThread):
    """Worker thread for Arduino connection to prevent GUI freezing."""
    
    connection_result = pyqtSignal(bool, str)
    
    def __init__(self, controller: ArduinoController, port: str = None):
        super().__init__()
        self.controller = controller
        self.port = port
        
    def run(self):
        """Attempt connection in background thread."""
        try:
            print(f"🧵 ConnectionWorker: Starting connection to {self.port}")
            success = self.controller.connect(self.port)
            if success:
                print("🧵 ConnectionWorker: Connection successful")
                self.connection_result.emit(True, "Connected successfully")
            else:
                print("🧵 ConnectionWorker: Connection failed")
                self.connection_result.emit(False, "Failed to connect to Arduino")
        except Exception as e:
            print(f"🧵 ConnectionWorker: Exception occurred - {str(e)}")
            self.connection_result.emit(False, f"Connection error: {str(e)}")


class AutoConnectionWorker(QThread):
    """Worker thread for automatic Arduino detection and connection."""
    
    connection_result = pyqtSignal(bool, str, str)  # success, message, port
    
    def __init__(self, controller: ArduinoController):
        super().__init__()
        self.controller = controller
        
    def run(self):
        """Attempt auto-connection in background thread."""
        try:
            print("🧵 AutoConnectionWorker: Starting auto-connection")
            success = self.controller.auto_connect()
            if success:
                port = self.controller.serial_port.port if self.controller.serial_port else ""
                print(f"🧵 AutoConnectionWorker: Auto-connection successful to {port}")
                self.connection_result.emit(True, "Auto-connected successfully", port)
            else:
                print("🧵 AutoConnectionWorker: Auto-connection failed")
                self.connection_result.emit(False, "No Arduino found", "")
        except Exception as e:
            print(f"🧵 AutoConnectionWorker: Exception occurred - {str(e)}")
            self.connection_result.emit(False, f"Auto-connection error: {str(e)}", "")


class RelayTestWindow(QMainWindow):
    """Main window for relay test application."""
    
    def __init__(self):
        super().__init__()
        self.arduino_controller = ArduinoController()
        self.relay_buttons = {}
        self.digital_indicators = {}
        self.analog_displays = {}
        self.status_timer = QTimer()
        self.input_timer = QTimer()
        self.connection_worker = None
        
        self.setup_ui()
        self.setup_connections()
        self.setup_status_timer()
        self.setup_input_timer()
        
        # Auto-connect to Arduino on startup
        QTimer.singleShot(1000, self.auto_connect_arduino)  # Delay 1 second after GUI loads
        
    def setup_ui(self):
        """Initialize the user interface optimized for 1280x800 landscape screen."""
        self.setWindowTitle("Relay Test System - Magnetron Sputtering Control")
        
        # Set to fullscreen or maximize for RPi5
        self.setGeometry(0, 0, 1280, 800)
        self.showMaximized()  # This will fill the screen
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout for landscape orientation
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Left side - Relay controls (take up about 60% of width)
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        left_widget.setMaximumWidth(int(1280 * 0.6))  # 60% of screen width
        
        # Connection control section (compact)
        connection_group = self.create_connection_section()
        left_layout.addWidget(connection_group)
        
        # Relay control section (main focus)
        relay_group = self.create_relay_section()
        left_layout.addWidget(relay_group)
        
        # Control buttons section (compact)
        control_group = self.create_control_section()
        left_layout.addWidget(control_group)
        
        # Right side - Input monitoring and status (40% of width)
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        right_widget.setMinimumWidth(int(1280 * 0.35))  # 35% of screen width
        
        # Input monitoring section (analog voltages, digital inputs)
        input_group = self.create_input_section()
        right_layout.addWidget(input_group)
        
        # Add some spacing at bottom
        right_layout.addStretch()
        
        # Add left and right to main layout
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget)
        
        # Status bar
        self.create_status_bar()
        
        # Initial status update
        self.update_connection_status(False)
        
    def create_menu_bar(self):
        """Create application menu bar."""
        menubar = self.menuBar()
        
        # Connection menu
        connection_menu = menubar.addMenu("Connection")
        
        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self.connect_arduino)
        connection_menu.addAction(connect_action)
        
        disconnect_action = QAction("Disconnect", self)
        disconnect_action.triggered.connect(self.disconnect_arduino)
        connection_menu.addAction(disconnect_action)
        
        connection_menu.addSeparator()
        
        refresh_ports_action = QAction("Refresh Ports", self)
        refresh_ports_action.triggered.connect(self.refresh_ports)
        connection_menu.addAction(refresh_ports_action)
        
        # Control menu
        control_menu = menubar.addMenu("Control")
        
        all_off_action = QAction("All Relays OFF", self)
        all_off_action.triggered.connect(self.all_relays_off)
        control_menu.addAction(all_off_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_connection_section(self):
        """Create connection control section."""
        group = QGroupBox("Arduino Connection")
        layout = QHBoxLayout()
        
        # Port selection
        layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)
        layout.addWidget(self.port_combo)
        
        # Connect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_arduino)
        layout.addWidget(self.connect_button)
        
        # Disconnect button
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_arduino)
        self.disconnect_button.setEnabled(False)
        layout.addWidget(self.disconnect_button)
        
        # Refresh ports button
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_ports)
        layout.addWidget(refresh_button)
        
        layout.addStretch()
        group.setLayout(layout)
        
        # Initial port refresh
        self.refresh_ports()
        
        return group
        
    def create_relay_section(self):
        """Create relay control button grid optimized for landscape layout."""
        group = QGroupBox("Relay Controls")
        grid_layout = QGridLayout()
        
        num_relays = 20
        num_cols = 5  # 5 columns for better landscape use
        num_rows = 4  # 4 rows
        
        for i in range(num_relays):
            relay_num = i + 1
            button = RelayButton(relay_num)
            button.clicked.connect(lambda checked, num=relay_num: self.on_relay_button_clicked(num))
            
            # Calculate position in 5x4 grid
            row = i // num_cols
            col = i % num_cols
            
            # Make buttons larger for landscape layout
            button.setMinimumSize(120, 80)
            button.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            
            grid_layout.addWidget(button, row, col)
            self.relay_buttons[relay_num] = button
            
        # Set spacing between buttons
        grid_layout.setSpacing(10)
        group.setLayout(grid_layout)
        return group
        
    def create_input_section(self):
        """Create input monitoring section optimized for right panel in landscape layout."""
        group = QGroupBox("Input Monitoring")
        main_layout = QVBoxLayout()  # Vertical layout for right panel
        
        # Digital Inputs section
        digital_group = QGroupBox("Digital Inputs")
        digital_layout = QGridLayout()
        
        self.digital_indicators = {}
        for i in range(4):
            input_num = i + 1
            # Label
            label = QLabel(f"Digital Input {input_num}:")
            label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            digital_layout.addWidget(label, i, 0)
            
            # Status indicator (LED-like) - larger for landscape
            indicator = LEDIndicator(size=32)  # Larger 32px diameter circle
            indicator.set_state(False)  # Start with red/off state
            digital_layout.addWidget(indicator, i, 1)
            
            # Status text
            status_label = QLabel("LOW")
            status_label.setFont(QFont("Arial", 10))
            digital_layout.addWidget(status_label, i, 2)
            
            self.digital_indicators[input_num] = {'led': indicator, 'label': status_label}
            
        digital_group.setLayout(digital_layout)
        main_layout.addWidget(digital_group)
        
        # Analog Inputs section
        analog_group = QGroupBox("Analog Voltage Readings")
        analog_layout = QGridLayout()
        
        self.analog_displays = {}
        for i in range(4):
            input_num = i + 1
            # Label
            label = QLabel(f"Analog Input {input_num}:")
            label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            analog_layout.addWidget(label, i, 0)
            
            # Voltage display - larger for landscape
            display = QLCDNumber(5)  # 5 digits for more precision
            display.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
            display.setStyleSheet("""
                QLCDNumber {
                    background-color: black;
                    color: cyan;
                    border: 2px solid gray;
                    border-radius: 5px;
                    min-height: 40px;
                    font-size: 14px;
                }
            """)
            display.display("0.000")
            analog_layout.addWidget(display, i, 1)
            
            # Unit label
            unit_label = QLabel("V")
            unit_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            analog_layout.addWidget(unit_label, i, 2)
            
            self.analog_displays[input_num] = display
            
        analog_group.setLayout(analog_layout)
        main_layout.addWidget(analog_group)
        
        # Add connection status section
        status_group = QGroupBox("Connection Status")
        status_layout = QVBoxLayout()
        
        self.connection_status_label = QLabel("Disconnected")
        self.connection_status_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.connection_status_label.setStyleSheet("color: red;")
        status_layout.addWidget(self.connection_status_label)
        
        self.port_label = QLabel("Port: None")
        self.port_label.setFont(QFont("Arial", 10))
        status_layout.addWidget(self.port_label)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        group.setLayout(main_layout)
        return group
        
    def create_control_section(self):
        """Create control buttons section."""
        group = QGroupBox("System Controls")
        layout = QHBoxLayout()
        
        # All OFF button
        all_off_button = QPushButton("ALL RELAYS OFF")
        all_off_button.setStyleSheet("""
            QPushButton {
                background-color: #ff5722;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #e64a19;
            }
        """)
        all_off_button.clicked.connect(self.all_relays_off)
        layout.addWidget(all_off_button)
        
        layout.addStretch()
        
        # Status refresh button
        refresh_status_button = QPushButton("Refresh Status")
        refresh_status_button.clicked.connect(self.refresh_relay_status)
        layout.addWidget(refresh_status_button)
        
        group.setLayout(layout)
        return group
        
    def create_status_bar(self):
        """Create status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
    def setup_connections(self):
        """Setup signal connections."""
        pass
        
    def setup_status_timer(self):
        """Setup timer for periodic status updates."""
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
        
    def setup_input_timer(self):
        """Setup timer for periodic input monitoring updates."""
        self.input_timer.timeout.connect(self.update_inputs)
        self.input_timer.start(500)  # Update every 500ms for faster input response
        
    def refresh_ports(self):
        """Refresh available COM ports."""
        self.port_combo.clear()
        ports = self.arduino_controller.get_available_ports()
        
        if ports:
            for port_name, description in ports:
                self.port_combo.addItem(f"{port_name} - {description}", port_name)
        else:
            self.port_combo.addItem("No ports available", None)
            
    def auto_connect_arduino(self):
        """Automatically connect to Arduino on startup."""
        print("\n🚀 GUI: Starting automatic Arduino connection...")
        
        if self.arduino_controller.is_arduino_connected():
            print("ℹ️  Arduino already connected")
            return
        
        # Disable connect button during auto-connection
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Auto-connecting...")
        
        # Update status
        self.status_bar.showMessage("Searching for Arduino...")
        
        # Start auto-connection in background thread
        self.connection_worker = AutoConnectionWorker(self.arduino_controller)
        self.connection_worker.connection_result.connect(self.on_auto_connection_result)
        self.connection_worker.start()
        
    def on_auto_connection_result(self, success: bool, message: str, port: str = ""):
        """Handle auto-connection result."""
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Connect")
        
        if success:
            print(f"🎉 GUI: Auto-connection successful to {port}!")
            self.update_connection_status(True)
            self.refresh_relay_status()
            
            # Update port combo to show connected port
            self.refresh_ports()
            for i in range(self.port_combo.count()):
                if self.port_combo.itemData(i) == port:
                    self.port_combo.setCurrentIndex(i)
                    break
            
            self.status_bar.showMessage(f"Auto-connected to Arduino on {port}")
        else:
            print(f"💥 GUI: Auto-connection failed - {message}")
            self.update_connection_status(False)
            self.status_bar.showMessage("Arduino not found - manual connection required")
            # Don't show error dialog for auto-connection failure, just update status
            
    def connect_arduino(self):
        """Connect to Arduino."""
        if self.arduino_controller.is_arduino_connected():
            print("ℹ️  Arduino already connected")
            return
            
        selected_port = self.port_combo.currentData()
        if selected_port is None:
            print("❌ No valid port selected")
            QMessageBox.warning(self, "Warning", "No valid port selected")
            return
            
        print(f"\n🎯 GUI: Initiating connection to {selected_port}")
        
        # Disable connect button during connection attempt
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Connecting...")
        
        # Start connection in background thread
        self.connection_worker = ConnectionWorker(self.arduino_controller, selected_port)
        self.connection_worker.connection_result.connect(self.on_connection_result)
        self.connection_worker.start()
        
    def on_connection_result(self, success: bool, message: str):
        """Handle connection result from worker thread."""
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Connect")
        
        if success:
            print("🎉 GUI: Connection successful!")
            self.update_connection_status(True)
            self.refresh_relay_status()
            QMessageBox.information(self, "Success", message)
        else:
            print(f"💥 GUI: Connection failed - {message}")
            self.update_connection_status(False)
            QMessageBox.warning(self, "Connection Failed", message)
            
    def disconnect_arduino(self):
        """Disconnect from Arduino."""
        self.arduino_controller.disconnect()
        self.update_connection_status(False)
        
        # Reset all button states
        for button in self.relay_buttons.values():
            button.set_state(False)
            
    def on_relay_button_clicked(self, relay_number: int):
        """Handle relay button click."""
        if not self.arduino_controller.is_arduino_connected():
            QMessageBox.warning(self, "Warning", "Arduino not connected")
            return
            
        button = self.relay_buttons[relay_number]
        new_state = not button.relay_state
        
        # Send command to Arduino
        success = self.arduino_controller.set_relay(relay_number, new_state)
        
        if success:
            button.set_state(new_state)
        else:
            QMessageBox.warning(self, "Error", f"Failed to control relay {relay_number}")
            
    def all_relays_off(self):
        """Turn off all relays."""
        if not self.arduino_controller.is_arduino_connected():
            QMessageBox.warning(self, "Warning", "Arduino not connected")
            return
            
        success = self.arduino_controller.all_relays_off()
        
        if success:
            # Update all button states
            for button in self.relay_buttons.values():
                button.set_state(False)
        else:
            QMessageBox.warning(self, "Error", "Failed to turn off all relays")
            
    def refresh_relay_status(self):
        """Refresh relay status from Arduino."""
        if not self.arduino_controller.is_arduino_connected():
            return
            
        states = self.arduino_controller.get_status()
        if states:
            for i, state in enumerate(states):
                relay_num = i + 1
                if relay_num in self.relay_buttons:
                    self.relay_buttons[relay_num].set_state(state)
                    
    def update_status(self):
        """Periodic status update."""
        connected = self.arduino_controller.is_arduino_connected()
        self.update_connection_status(connected)
        
    def update_inputs(self):
        """Update input monitoring displays."""
        if not self.arduino_controller.is_arduino_connected():
            return
        
        try:
            # Update digital inputs
            digital_states = self.arduino_controller.get_digital_inputs()
            if digital_states is not None:
                for i, state in enumerate(digital_states):
                    input_num = i + 1
                    if input_num in self.digital_indicators:
                        indicator_dict = self.digital_indicators[input_num]
                        indicator_dict['led'].set_state(state)  # True=green/HIGH, False=red/LOW
                        indicator_dict['label'].setText("HIGH" if state else "LOW")
            
            # Update analog inputs
            analog_voltages = self.arduino_controller.get_analog_voltages()
            if analog_voltages is not None:
                for i, voltage in enumerate(analog_voltages):
                    input_num = i + 1
                    if input_num in self.analog_displays:
                        display = self.analog_displays[input_num]
                        display.display(f"{voltage:.3f}")  # 3 decimal places for 5-digit display
                        
        except Exception as e:
            print(f"Error updating inputs: {e}")
        
    def update_connection_status(self, connected: bool):
        """Update connection status display."""
        if connected:
            self.status_bar.showMessage("Arduino Connected")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            
            # Update status section in right panel
            self.connection_status_label.setText("Connected")
            self.connection_status_label.setStyleSheet("color: green;")
            if hasattr(self.arduino_controller, 'serial_port') and self.arduino_controller.serial_port:
                self.port_label.setText(f"Port: {self.arduino_controller.serial_port.port}")
            
            # Enable relay buttons
            for button in self.relay_buttons.values():
                button.setEnabled(True)
        else:
            self.status_bar.showMessage("Arduino Disconnected")
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            
            # Update status section in right panel
            self.connection_status_label.setText("Disconnected")
            self.connection_status_label.setStyleSheet("color: red;")
            self.port_label.setText("Port: None")
            
            # Disable relay buttons
            for button in self.relay_buttons.values():
                button.setEnabled(False)
                button.set_state(False)
                
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, "About Relay Test System", 
                         "Relay Test System v1.0\n\n"
                         "Part of Magnetron Sputtering System Control Upgrade\n"
                         "Controls 20 relays via Arduino Mega 2560\n\n"
                         "Features:\n"
                         "- 20 individual relay controls\n"
                         "- Real-time status monitoring\n"
                         "- Emergency all-off function\n"
                         "- Automatic Arduino detection")
                         
    def closeEvent(self, event):
        """Handle application close event."""
        if self.arduino_controller.is_arduino_connected():
            # Turn off all relays before closing
            self.arduino_controller.all_relays_off()
            self.arduino_controller.disconnect()
        event.accept()
