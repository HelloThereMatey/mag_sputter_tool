"""
Main application entry point for Relay Test System
Magnetron Sputtering System Control Upgrade Project
"""

import sys
import os

# Fix PyQt5 platform plugin issue on Windows
if sys.platform == "win32":
    try:
        import PyQt5
        plugin_path = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
        if os.path.exists(plugin_path):
            os.environ['QT_PLUGIN_PATH'] = plugin_path
            print(f"Set QT_PLUGIN_PATH to: {plugin_path}")
        # Also set the Qt5 bin directory in PATH for DLLs
        bin_path = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "bin")
        if os.path.exists(bin_path):
            os.environ['PATH'] = bin_path + ';' + os.environ.get('PATH', '')
            print(f"Added to PATH: {bin_path}")
    except Exception:
        pass

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from gui import RelayTestWindow


def main():
    """Main application entry point."""
    # Enable high DPI scaling before creating QApplication (Qt6 way)
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Relay Test System")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("Magnetron Sputtering Control")
    
    
    # Create and show main window
    print("🖥️  Creating main window...")
    main_window = RelayTestWindow()
    main_window.show()
    
    print("🚀 Application started - Auto-connecting to Arduino...")
    
    # Handle application exit
    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        exit_code = 0
    finally:
        # Ensure proper cleanup
        if hasattr(main_window, 'arduino_controller'):
            if main_window.arduino_controller.is_arduino_connected():
                print("Disconnecting Arduino...")
                main_window.arduino_controller.all_relays_off()
                main_window.arduino_controller.disconnect()
        print("Application closed")
        
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
