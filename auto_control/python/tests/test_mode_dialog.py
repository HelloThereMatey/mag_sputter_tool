#!/usr/bin/env python3
"""
Test script for the updated mode dialog functionality.
"""

import sys
from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget, QLabel

# Support both package and script execution
try:
    from widgets.mode_dialog import ModeSelectionDialog
except ImportError:
    sys.path.append('.')
    from widgets.mode_dialog import ModeSelectionDialog


class TestWindow(QWidget):
    """Simple test window to test the mode dialog."""
    
    def __init__(self):
        super().__init__()
        self.current_mode = "Normal"
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the test UI."""
        self.setWindowTitle("Mode Dialog Test")
        self.setGeometry(100, 100, 300, 200)
        
        layout = QVBoxLayout()
        
        # Current mode display
        self.mode_label = QLabel(f"Current Mode: {self.current_mode}")
        layout.addWidget(self.mode_label)
        
        # Button to open mode dialog
        self.mode_button = QPushButton("Change Mode")
        self.mode_button.clicked.connect(self.show_mode_dialog)
        layout.addWidget(self.mode_button)
        
        self.setLayout(layout)
        
    def show_mode_dialog(self):
        """Show the mode selection dialog."""
        try:
            dialog = ModeSelectionDialog(self.current_mode, self)
            
            if dialog.exec() == ModeSelectionDialog.DialogCode.Accepted:
                new_mode = dialog.get_selected_mode()
                
                if new_mode != self.current_mode:
                    self.current_mode = new_mode
                    self.mode_label.setText(f"Current Mode: {self.current_mode}")
                    print(f"Mode changed to: {self.current_mode}")
                    
        except Exception as e:
            print(f"❌ Error showing mode dialog: {e}")


def main():
    """Main test function."""
    app = QApplication(sys.argv)
    
    # Create test window
    window = TestWindow()
    window.show()
    
    print("Mode Dialog Test")
    print("================")
    print("1. Click 'Change Mode' to open the mode dialog")
    print("2. Try switching to Manual or Override mode")
    print("3. Note that no master password is required")
    print("4. Only mode-specific passwords are needed")
    print()
    print("Test Passwords (for demonstration):")
    print("- Any password 4+ characters will work in simplified mode")
    print()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
