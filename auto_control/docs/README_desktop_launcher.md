# Sputter Control GUI Launcher

This directory contains the desktop launcher files for the Sputter Control GUI on Raspberry Pi.

## Files
- `launch_sputter_gui.sh` - Bash script that activates conda environment and launches the GUI
- `SpatterControl.desktop` - Desktop entry file for the Raspbian desktop
- `sputter_icon.png` - Application icon (you'll need to add this)

## Installation on Raspberry Pi

1. **Make the launcher script executable:**
   ```bash
   chmod +x /home/pi/Documents/Code/sputter_control/auto_control/launch_sputter_gui.sh
   ```

2. **Add an icon (optional but recommended):**
   - Place a PNG icon file at: `/home/pi/Documents/Code/sputter_control/auto_control/sputter_icon.png`
   - Recommended size: 64x64 or 128x128 pixels
   - You can use any vacuum/science/control related icon

3. **Install the desktop file:**
   ```bash
   # Copy to desktop for immediate access
   cp /home/pi/Documents/Code/sputter_control/auto_control/SpatterControl.desktop ~/Desktop/
   chmod +x ~/Desktop/SpatterControl.desktop
   
   # Or copy to applications menu
   cp /home/pi/Documents/Code/sputter_control/auto_control/SpatterControl.desktop ~/.local/share/applications/
   chmod +x ~/.local/share/applications/SpatterControl.desktop
   ```

4. **Update desktop database (for applications menu):**
   ```bash
   update-desktop-database ~/.local/share/applications/
   ```

## Usage
- Double-click the desktop icon to launch
- The script will automatically activate your conda environment if available
- Terminal window will show startup messages and stay open for debugging

## Customization
- Edit the `.desktop` file to change the icon path, name, or categories
- Modify the launcher script to add environment variables or change startup behavior
- Add `Terminal=false` in the .desktop file if you don't want to see the terminal window
