from __future__ import annotations

from typing import Optional
from PyQt5.QtWidgets import QFrame

def set_interlock_indicator(frame: QFrame, state: Optional[bool]) -> None:
    """Update QFrame circle indicator using dynamic property 'indState'.

    state True  -> 'on' (green)
    state False -> 'off' (red)
    state None  -> 'na' (grey)
    """
    property_value = "na" if state is None else ("on" if state else "off")
    frame.setProperty("indState", property_value)
    frame.style().unpolish(frame)
    frame.style().polish(frame)
    frame.update()
    frame.setProperty("indState", property_value)
    frame.style().unpolish(frame)
    frame.style().polish(frame)
    frame.update()
