"""About dialog for Sputter Control System."""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class AboutDialog(QDialog):
    """About dialog displaying software information."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Sputter Control System")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Sputter Control System")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel("Version 2.0")
        version_font = QFont()
        version_font.setPointSize(10)
        version_label.setFont(version_font)
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        layout.addSpacing(20)
        
        # About text
        about_text = QTextEdit()
        about_text.setReadOnly(True)
        about_text.setHtml("""
        <p><b>Magnetron Sputtering System Control Software</b></p>
                           
        <p><i>By James Bishop</i></p>
        <p>Github: <a href="https://github.com/HelloThereMatey">https://github.com/HelloThereMatey</a></p>

        <p>This software provides automated control and monitoring for a vacuum magnetron 
        sputtering system. Built on a Raspberry Pi 5 with Arduino Mega 2560 R3 hardware 
        interface, it delivers safe, reliable operation through:</p>
        
        <ul>
        <li><b>Real-time Safety Interlocks:</b> Multi-layer safety system with automatic 
        state detection and procedure validation</li>
        
        <li><b>Automated Procedures:</b> Pre-programmed sequences for pump-down, venting, 
        load-lock operation, and sputtering processes</li>
        
        <li><b>User Authentication:</b> Four-level permission system (Operator, Technician, 
        Master, Administrator) with secure password management</li>
        
        <li><b>Gas Flow Control:</b> Integrated mass flow controller support with recipes 
        and real-time monitoring</li>
        
        <li><b>Data Logging:</b> Built-in logbook for tracking sputter targets, process 
        parameters, and system events</li>
        
        <li><b>Real-time Monitoring:</b> Live pressure readings, sensor states, and system 
        status with graphical trending</li>
        </ul>
        
        <p><b>Hardware Platform:</b></p>
        <ul>
        <li>Raspberry Pi 5 (Ubuntu 24.04 LTS)</li>
        <li>Arduino Mega 2560 R3 (23 relay outputs, 4 digital inputs, 4 analog inputs)</li>
        <li>Custom relay control electronics</li>
        <li>Alicat APEX mass flow controllers</li>
        </ul>
        
        <p><b>Software Stack:</b></p>
        <ul>
        <li>Python 3.10+ with PyQt5 GUI framework</li>
        <li>SQLite database for user accounts and logbook</li>
        <li>Arduino C++ firmware for real-time I/O</li>
        <li>YAML-based configuration and safety rules</li>
        </ul>
        
        <p style="margin-top: 20px;"><i>Developed for research and development in thin film 
        deposition. For technical support, refer to the software manual or contact your 
        system administrator.</i></p>
        
        <p><b>Documentation:</b> See <code>docs/</code> folder for SOP, technical manual, 
        and software documentation.</p>
        <p>Link to repository: <a href="https://github.com/HelloThereMatey/mag_sputter_tool">https://github.com/HelloThereMatey/mag_sputter_tool</a></p>
        """)
        layout.addWidget(about_text)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
