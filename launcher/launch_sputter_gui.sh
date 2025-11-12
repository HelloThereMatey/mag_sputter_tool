#!/bin/bash
# Launcher script for Sputter Control GUI
# Activates conda environment and runs the application

set -e  # Exit on any error

# Change to the script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Sputter Control GUI Launcher ==="
echo "Script directory: $SCRIPT_DIR"

# Function to check if conda is properly initialized
check_conda_init() {
    if [ -f "$HOME/.bashrc" ] && grep -q "conda initialize" "$HOME/.bashrc"; then
        return 0
    elif [ -f "$HOME/.bash_profile" ] && grep -q "conda initialize" "$HOME/.bash_profile"; then
        return 0
    else
        return 1
    fi
}

# Initialize conda properly
init_conda() {
    echo "Initializing conda..."
    
    # Try common conda installation paths
    CONDA_BASE=""
    if command -v conda &> /dev/null; then
        CONDA_BASE=$(conda info --base 2>/dev/null || echo "")
    fi
    
    # Fallback paths for Pi
    if [ -z "$CONDA_BASE" ]; then
        for path in "$HOME/miniconda3" "$HOME/Documents/miniconda3" "$HOME/anaconda3" "/opt/conda" "/usr/local/conda"; do
            if [ -d "$path" ]; then
                CONDA_BASE="$path" 
                break
            fi
        done
    fi
    
    if [ -n "$CONDA_BASE" ] && [ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]; then
        echo "Found conda at: $CONDA_BASE"
        source "$CONDA_BASE/etc/profile.d/conda.sh"
        return 0
    else
        echo "Error: Could not find conda installation"
        return 1
    fi
}

# Activate conda environment
activate_sput_env() {
    echo "Checking for sput environment..."
    
    if conda env list | grep -q "^sput "; then
        echo "Activating sput environment..."
        conda activate sput
        
        # Wait and verify activation
        sleep 2
        
        if [[ "$CONDA_DEFAULT_ENV" == "sput" ]]; then
            echo "? Successfully activated sput environment"
            return 0
        else
            echo "? Failed to activate sput environment"
            return 1
        fi
    else
        echo "Warning: sput environment not found"
        echo "Available environments:"
        conda env list
        return 1
    fi
}

# Main execution
main() {
    # Initialize conda
    if ! init_conda; then
        echo "Failed to initialize conda. Trying with system Python..."
        echo "Make sure conda is installed and initialized."
        export CONDA_DEFAULT_ENV="base"
    else
        # Try to activate sput environment
        if ! activate_sput_env; then
            echo "Continuing with base environment..."
        fi
    fi
    
    sleep 2

    # Show Python info
    echo "Python path: $(which python)"
    echo "Python version: $(python --version 2>&1)"
    echo "Current environment: ${CONDA_DEFAULT_ENV:-system}"
    
    # Hide taskbar if not already hidden
    echo "=== Ensuring taskbar is hidden ==="
    CFG1="$HOME/.config/wf-panel-pi/wf-panel-pi.ini"
    CFG2="$HOME/.config/wf-panel-pi.ini"

    # Pick existing config or create minimal one
    if [ -f "$CFG1" ]; then
      CFG="$CFG1"
    elif [ -f "$CFG2" ]; then
      CFG="$CFG2"
    else
      mkdir -p "$(dirname "$CFG1")"
      printf '[panel]\n' > "$CFG1"
      CFG="$CFG1"
    fi

    # Read current autohide value from [panel]
    current=$(
      awk '
        BEGIN{sec=0; val=""}
        /^[ \t]*\[panel\][ \t]*$/ {sec=1; next}
        /^[ \t]*\[/ {sec=0}
        sec && /^[ \t]*autohide[ \t]*=/ {
          v=$0
          sub(/^[^=]*=/,"",v)
          sub(/^[ \t]*/,"",v)
          sub(/[ \t\r\n]*$/,"",v)
          val=v
        }
        END{ if (val=="") print "unset"; else print val }
      ' "$CFG"
    )

    lc=$(printf '%s' "$current" | tr '[:upper:]' '[:lower:]')
    if [ "$lc" = "true" ] || [ "$lc" = "1" ] || [ "$lc" = "yes" ]; then
      echo "Taskbar is already hidden"
    else
      # Determine number of connected displays; only hide taskbar when exactly 1 display is active
      get_num_displays() {
        # Prefer xrandr (X11)
        if command -v xrandr >/dev/null 2>&1; then
          # Count connected outputs
          cnt=$(xrandr --query 2>/dev/null | grep " connected" | wc -l | tr -d ' ')
          if [ -n "$cnt" ]; then
            echo "$cnt"
            return
          fi
        fi

        # Try wlr-randr (Wayland wlr)
        if command -v wlr-randr >/dev/null 2>&1; then
          cnt=$(wlr-randr -l 2>/dev/null | wc -l | tr -d ' ')
          if [ -n "$cnt" ]; then
            echo "$cnt"
            return
          fi
        fi

        # Try swaymsg (sway/Wayland)
        if command -v swaymsg >/dev/null 2>&1; then
          cnt=$(swaymsg -t get_outputs 2>/dev/null | grep -o '"active"[[:space:]]*:[[:space:]]*true' | wc -l | tr -d ' ')
          if [ -n "$cnt" ]; then
            echo "$cnt"
            return
          fi
        fi

        # Unknown environment - default to 1 (so behavior matches previous script)
        echo "1"
      }

      num_displays=$(get_num_displays)
      echo "Detected displays: $num_displays"
      if [ "$num_displays" -gt 1 ]; then
        echo "Multiple displays detected; skipping taskbar hide."
      else
        echo "Hiding taskbar..."
        # Write updated config to hide taskbar
        tmp="$(mktemp)"
        awk '
          BEGIN { sec=0; replaced=0; saw_panel=0 }
          /^[ \t]*\[panel\][ \t]*$/ { print; sec=1; replaced=0; saw_panel=1; next }
          /^[ \t]*\[/ {
            if (sec && !replaced) print "autohide=true"
            sec=0
            print
            next
          }
          {
            if (sec) {
              if ($0 ~ /^[ \t]*autohide[ \t]*=/) {
                if (!replaced) { print "autohide=true"; replaced=1 }
                next
              }
            }
            print
          }
          END {
            if (sec && !replaced) print "autohide=true"
            if (!saw_panel) {
              print "[panel]"
              print "autohide=true"
            }
          }
        ' "$CFG" > "$tmp"
        mv "$tmp" "$CFG"
        echo "Taskbar hidden"
      fi
    fi

    sleep 1

    # Launch the GUI
    echo "=== Starting Sputter Control GUI ==="
    cd ..
    cd auto_control/python
    echo "Directoy set to: "
    pwd
    sleep 1
    
    if [ -f "main.py" ]; then
        python main.py
    else
        echo "Error: main.py not found in python directory"
        echo "Current directory: $(pwd)"
        echo "Files: $(ls -la)"
    fi
}

# Error handling
trap 'echo "Script interrupted"; exit 1' INT TERM

# Run main function
main

# Keep terminal open if there's an error
if [ $? -ne 0 ]; then
    echo ""
    echo "=== Error occurred ==="
    echo "Press Enter to close..."
    read
else
    echo ""
    echo "=== Application finished ==="
    echo "Press Enter to close..."
    read
fi
