#!/bin/bash
# Find Labwc/Waybar panel configuration files
# Run this to identify where your taskbar settings are stored

echo "🔍 Searching for Labwc panel/taskbar configuration files..."
echo ""

# Search common locations
echo "Files in ~/.config/lxpanel/:"
find ~/.config/lxpanel -type f 2>/dev/null | head -20

echo ""
echo "Files in ~/.config/waybar/:"
find ~/.config/waybar -type f 2>/dev/null | head -20

echo ""
echo "Files in ~/.config/labwc/:"
find ~/.config/labwc -type f 2>/dev/null | head -20

echo ""
echo "Files in ~/.config with 'panel' in name:"
find ~/.config -type f -iname "*panel*" 2>/dev/null

echo ""
echo "Files in ~/.config with 'bar' in name:"
find ~/.config -type f -iname "*bar*" 2>/dev/null

echo ""
echo "Looking for recently modified config files..."
find ~/.config -type f -mtime -7 2>/dev/null | grep -E "(panel|bar|output|screen)" | head -20

echo ""
echo "Current lxpanel process info:"
ps aux | grep -E "lxpanel|waybar|panel" | grep -v grep

echo ""
echo "Done! Review files above to find your taskbar configuration."
