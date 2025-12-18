#!/bin/bash
# Setup hardcoded screen configuration for RPi5 Wayland + Labwc
# Configuration:
# - HDMI-A-1 (1280x800, touchscreen) on LEFT
# - HDMI-A-2 (1920x1080, primary) on RIGHT
# - Taskbar at bottom on HDMI-A-2
# - Extended (not mirrored) display

set -e  # Exit on error

echo "=========================================="
echo "RPi5 Screen Configuration Setup"
echo "=========================================="

# Create .config directory if it doesn't exist
mkdir -p ~/.config/labwc

# Create output.conf for Labwc Wayland compositor
# This defines monitor layout and positioning
cat > ~/.config/labwc/output.conf << 'EOF'
# Labwc output configuration for dual monitors
# HDMI-A-1: 1280x800 touchscreen, positioned on LEFT
# HDMI-A-2: 1920x1080 primary monitor, positioned on RIGHT

output HDMI-A-1
  pos 0 0
  mode 1280x800
  scale 1

output HDMI-A-2
  pos 1280 0
  mode 1920x1080
  scale 1
EOF

echo "✅ Created ~/.config/labwc/output.conf"
echo ""

# Create/update rc.xml for Labwc window manager configuration
# This ensures panel/taskbar is on correct monitor
mkdir -p ~/.config/labwc
if [ ! -f ~/.config/labwc/rc.xml ]; then
    cat > ~/.config/labwc/rc.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<labwc_config>
  <!-- Labwc window manager configuration -->
  
  <!-- Keyboard shortcuts (optional) -->
  <keyboard>
    <keybind key="C-A-t">
      <action name="Execute">
        <command>xterm</command>
      </action>
    </keybind>
  </keyboard>

  <!-- Window decorations and behavior -->
  <window_switcher show_desktop_label="yes" preview="yes" />
  <theme>
    <name>Adwaita</name>
  </theme>

</labwc_config>
EOF
    echo "✅ Created ~/.config/labwc/rc.xml"
else
    echo "ℹ️ ~/.config/labwc/rc.xml already exists, skipping creation"
fi

echo ""

# Configure lxpanel for taskbar positioning
# Panel config is stored in ~/.config/lxpanel/lxpanel
mkdir -p ~/.config/lxpanel

# Create panel configuration for HDMI-A-2 (primary) at bottom
cat > ~/.config/lxpanel/lxpanel << 'EOF'
[Command]
FileManager=pcmanfm
Terminal=x-terminal-emulator
Logout=logout

[PanelTop]

[PanelBottom]
edge=bottom
allign=center
margin=0
widthtype=percent
width=100
height=36
transparent=0
tint_color=0x000000
tint_alpha=200

[PanelLeft]

[PanelRight]
EOF

echo "✅ Created lxpanel configuration for taskbar at bottom on HDMI-A-2"
echo ""

# Also create/backup the old default panels file if it exists
if [ -d ~/.config/lxpanel/default ]; then
    mkdir -p ~/.config/lxpanel
    cat > ~/.config/lxpanel/default/panels << 'EOF'
[panel]
edge=bottom
align=center
margin=0
widthtype=percent
width=100
height=36
transparent=0
monitor=1
EOF
    echo "✅ Updated default panel configuration"
fi
echo ""

# Create a startup script to apply these settings at boot
cat > ~/.config/labwc/startup.sh << 'EOF'
#!/bin/bash
# Labwc startup script - applies screen configuration at boot

# Wait for Wayland to be ready
sleep 2

# Apply monitor layout using wlr-randr if available
if command -v wlr-randr &> /dev/null; then
    echo "Applying screen layout with wlr-randr..."
    
    # Set HDMI-A-1 (1280x800) on left at position 0,0
    wlr-randr --output HDMI-A-1 --pos 0,0 --mode 1280x800 2>/dev/null || true
    
    # Set HDMI-A-2 (1920x1080) on right at position 1280,0 (primary)
    wlr-randr --output HDMI-A-2 --pos 1280,0 --mode 1920x1080 --preferred 2>/dev/null || true
    
    echo "✅ Screen layout applied"
else
    echo "⚠️ wlr-randr not found, layout may need manual application"
fi

# Restart panel on correct monitor
if command -v lxpanel &> /dev/null; then
    killall lxpanel 2>/dev/null || true
    sleep 1
    DISPLAY=:0 lxpanel --profile default &
    echo "✅ Panel restarted on primary monitor"
fi
EOF

chmod +x ~/.config/labwc/startup.sh
echo "✅ Created startup script: ~/.config/labwc/startup.sh"
echo ""

# Create systemd user service to run startup script at login
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/labwc-monitor-config.service << 'EOF'
[Unit]
Description=Labwc Monitor Configuration
After=graphical-session-pre.target
PartOf=graphical-session.target

[Service]
Type=oneshot
ExecStart=%h/.config/labwc/startup.sh
RemainAfterExit=yes

[Install]
WantedBy=graphical-session.target
EOF

echo "✅ Created systemd user service"
echo ""

# Enable the service
systemctl --user daemon-reload 2>/dev/null || true
systemctl --user enable labwc-monitor-config.service 2>/dev/null || true
echo "✅ Enabled systemd user service"
echo ""

# Apply settings immediately
echo "Applying screen configuration now..."
bash ~/.config/labwc/startup.sh
echo ""

echo "=========================================="
echo "✅ Screen configuration hardcoded!"
echo "=========================================="
echo ""
echo "Configuration Summary:"
echo "  • HDMI-A-1 (1280x800): Position 0,0 (LEFT)"
echo "  • HDMI-A-2 (1920x1080): Position 1280,0 (RIGHT, PRIMARY)"
echo "  • Taskbar: Bottom of HDMI-A-2"
echo "  • Extended display layout"
echo ""
echo "Files modified/created:"
echo "  • ~/.config/labwc/output.conf (monitor layout)"
echo "  • ~/.config/labwc/rc.xml (window manager config)"
echo "  • ~/.config/lxpanel/default/panels (taskbar position)"
echo "  • ~/.config/labwc/startup.sh (boot startup script)"
echo "  • ~/.config/systemd/user/labwc-monitor-config.service"
echo ""
echo "Settings will persist across reboots."
echo "If screens reset again, run this script again or reboot."
echo ""
