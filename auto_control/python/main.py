from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure package imports work when run as `python main.py`
if __package__ is None or __package__ == "":
    # add parent of this file (auto_control/python) and its parent (auto_control) to sys.path
    here = Path(__file__).resolve()
    sys.path.append(str(here.parent))
    sys.path.append(str(here.parent.parent))

# Windows plugin path fix similar to relay_test_system
if sys.platform == "win32":
    try:
        import PyQt5  # type: ignore
        plugin_path = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
        if os.path.exists(plugin_path):
            os.environ['QT_PLUGIN_PATH'] = plugin_path
        bin_path = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "bin")
        if os.path.exists(bin_path):
            os.environ['PATH'] = bin_path + ';' + os.environ.get('PATH', '')
    except Exception:
        pass

try:
    from .app import run  # type: ignore
except ImportError:
    # fallback when executed directly without package context
    from app import run  # type: ignore


if __name__ == "__main__":
    sys.exit(run())
