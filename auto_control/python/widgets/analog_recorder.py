"""Analog input recorder for saving sensor data to CSV files.

This module provides a dialog and background recording functionality for
saving analog input readings to CSV files without the overhead of plotting.
"""

from typing import Optional
from pathlib import Path
from datetime import datetime
import csv

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QFileDialog, QLineEdit, QMessageBox)
from PyQt5.QtCore import QTimer, Qt


class AnalogRecorderDialog(QDialog):
    """Dialog for configuring analog input recording to CSV."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Record Analog Inputs")
        self.setModal(True)
        self.setFixedSize(500, 200)
        
        self.selected_file = None
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Record Analog Inputs to CSV")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # File selection
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Save to:"))
        
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Click Browse to select file...")
        self.file_edit.setReadOnly(True)
        file_layout.addWidget(self.file_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        
        layout.addLayout(file_layout)
        
        # Info label
        info_label = QLabel(
            "• Recordings saved every 30 seconds\n"
            "• 30 rows per write (1 second intervals)\n"
            "• 4 analog channels recorded\n"
            "• Timestamps from system time"
        )
        info_label.setStyleSheet("color: #555; font-size: 10pt;")
        layout.addWidget(info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self.start_btn = QPushButton("Start Recording")
        self.start_btn.setEnabled(False)
        self.start_btn.setDefault(True)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.start_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.start_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _browse_file(self):
        """Open file dialog to select CSV file location."""
        default_filename = f"analog_inputs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select CSV File",
            str(Path.home() / default_filename),
            "CSV Files (*.csv);;All Files (*.*)"
        )
        
        if file_path:
            # Ensure .csv extension
            if not file_path.endswith('.csv'):
                file_path += '.csv'
            
            self.selected_file = file_path
            self.file_edit.setText(file_path)
            self.start_btn.setEnabled(True)
    
    def get_file_path(self) -> Optional[str]:
        """Get the selected file path if dialog was accepted."""
        if self.result() == QDialog.Accepted:
            return self.selected_file
        return None


class AnalogRecorder:
    """Background recorder for analog inputs to CSV file.
    
    Records 4 analog channels at 1 second intervals, buffering 30 samples
    in RAM and flushing to CSV every 30 seconds.
    
    IMPORTANT: Timers MUST have a parent Qt object to ensure they run in the 
    correct thread and are properly cleaned up.
    """
    
    def __init__(self, file_path: str, read_fn, parent_window):
        """Initialize recorder.
        
        Args:
            file_path: Path to CSV file for recording
            read_fn: Callable that returns list of 4 voltage values (floats)
            parent_window: REQUIRED parent window - must be a QObject for proper timer ownership
        """
        if parent_window is None:
            raise ValueError("AnalogRecorder requires a parent QObject for proper timer management")
        
        self.file_path = Path(file_path)
        self.read_fn = read_fn
        self.parent = parent_window
        
        # Recording state
        self.is_recording = False
        self.buffer = []  # Buffer for 30 samples
        self.file_exists = self.file_path.exists()
        
        # Timer for 1-second sampling - MUST have parent for proper thread affinity
        self.sample_timer = QTimer(parent_window)
        self.sample_timer.setInterval(1000)  # 1 second
        self.sample_timer.timeout.connect(self._record_sample)
        
        # Timer for 30-second flush - MUST have parent for proper thread affinity
        self.flush_timer = QTimer(parent_window)
        self.flush_timer.setInterval(30000)  # 30 seconds
        self.flush_timer.timeout.connect(self._flush_buffer)
        
        print(f"📊 Analog recorder initialized for file: {self.file_path}")
    
    def start(self):
        """Start recording analog inputs."""
        if self.is_recording:
            print("⚠️ Recorder already running")
            return
        
        self.is_recording = True
        self.buffer = []
        
        # Write header if this is a new file
        if not self.file_exists:
            self._write_header()
        
        # Start timers
        self.sample_timer.start()
        self.flush_timer.start()
        
        print(f"▶️ Recording started to: {self.file_path}")
        # Don't show message box here - it blocks the GUI thread
        # The recorder window will show status instead
    
    def stop(self):
        """Stop recording and flush remaining data."""
        if not self.is_recording:
            print(f"ℹ️ Recorder already stopped")
            return
        
        print(f"⏹️ Stopping recorder for: {self.file_path}")
        self.is_recording = False
        
        # Stop timers first
        try:
            self.sample_timer.stop()
            self.sample_timer.disconnect()  # Disconnect all signals
        except Exception as e:
            print(f"⚠️ Error stopping sample timer: {e}")
        
        try:
            self.flush_timer.stop()
            self.flush_timer.disconnect()  # Disconnect all signals
        except Exception as e:
            print(f"⚠️ Error stopping flush timer: {e}")
        
        # Flush any remaining data in buffer
        if self.buffer:
            self._flush_buffer()
        
        print(f"✅ Recording stopped: {self.file_path}")
    
    def _write_header(self):
        """Write CSV header to file."""
        try:
            with open(self.file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Analog_0_V', 'Analog_1_V', 'Analog_2_V', 'Analog_3_V'])
            self.file_exists = True
            print(f"✅ CSV header written to {self.file_path}")
        except Exception as e:
            print(f"❌ Error writing CSV header: {e}")
            # Don't show message box here - it would block the GUI
            # Just log and stop recording
            self.stop()
    
    def _record_sample(self):
        """Record a single sample of analog inputs."""
        if not self.is_recording:
            return
        
        try:
            # Get analog voltages from read function
            analog_voltages = self.read_fn()
            
            if analog_voltages is None or len(analog_voltages) < 4:
                print("⚠️ Failed to read analog voltages")
                return
            
            # Create timestamp and data row (voltages are already floats)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row = [timestamp] + [float(v) for v in analog_voltages[:4]]
            
            # Add to buffer
            self.buffer.append(row)
            
        except Exception as e:
            print(f"❌ Error recording sample: {e}")
    
    def _flush_buffer(self):
        """Flush buffered samples to CSV file."""
        if not self.buffer:
            print("ℹ️ No data to flush")
            return
        
        try:
            # Append buffer to CSV
            with open(self.file_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(self.buffer)
            
            print(f"💾 Flushed {len(self.buffer)} samples to {self.file_path}")
            
            # Clear buffer
            self.buffer = []
            
        except Exception as e:
            print(f"❌ Error flushing buffer to CSV: {e}")
            # Don't show message box - it would block the GUI
            # Just log the error and stop recording
            self.stop()
    
    def is_active(self) -> bool:
        """Check if recorder is currently recording."""
        return self.is_recording


class AnalogRecorderWindow(QDialog):
    """Window for controlling analog input recording.
    
    CRITICAL: This window must properly manage the recorder lifecycle
    to prevent timers from interfering with the main GUI.
    """
    
    def __init__(self, file_path: str, read_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analog Input Recorder")
        self.setModal(False)
        self.setFixedSize(450, 250)
        
        # Flag to track if we've already cleaned up
        self._cleanup_done = False
        
        # Create recorder - pass self (this window) as parent for proper timer ownership
        self.recorder = AnalogRecorder(file_path, read_fn, self)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Recording Analog Inputs")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # File path
        file_label = QLabel(f"File: {file_path}")
        file_label.setWordWrap(True)
        file_label.setStyleSheet("color: #555; font-size: 10pt;")
        layout.addWidget(file_label)
        
        # Status
        self.status_label = QLabel("● Recording in progress...")
        self.status_label.setStyleSheet("color: #27ae60; font-size: 12pt; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Info
        info_label = QLabel(
            "• Data saved every 30 seconds\n"
            "• 1 second sampling interval\n"
            "• Close this window to stop recording"
        )
        info_label.setStyleSheet("color: #555; font-size: 10pt;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # Stop button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.stop_btn = QPushButton("Stop Recording")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.stop_btn.clicked.connect(self._stop_recording)
        button_layout.addWidget(self.stop_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Start recording (use QTimer to start after event loop is running)
        QTimer.singleShot(100, self.recorder.start)
    
    def _stop_recording(self):
        """Stop recording and close window."""
        print("🛑 Stop button clicked")
        self._do_cleanup()
        
        # Update UI
        self.status_label.setText("⏹ Recording stopped")
        self.status_label.setStyleSheet("color: #e74c3c; font-size: 12pt; font-weight: bold;")
        self.stop_btn.setEnabled(False)
        
        # Close window after short delay
        QTimer.singleShot(100, self.close)
    
    def _do_cleanup(self):
        """Perform cleanup of recorder resources."""
        if self._cleanup_done:
            print("ℹ️ Cleanup already done, skipping")
            return
        
        print("🧹 Performing recorder cleanup")
        self._cleanup_done = True
        
        # Stop recorder
        try:
            if hasattr(self, 'recorder') and self.recorder.is_active():
                self.recorder.stop()
        except Exception as e:
            print(f"⚠️ Error stopping recorder: {e}")
    
    def closeEvent(self, event):
        """Ensure recorder is stopped when window is closed."""
        print("🚪 Recorder window closeEvent triggered")
        self._do_cleanup()
        
        # Accept the close event
        event.accept()
        print("✅ Recorder window close event accepted")
