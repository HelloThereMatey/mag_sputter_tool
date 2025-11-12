"""
Safety package for Sputter Control System.

This package provides safety interlock functionality and condition checking
for the vacuum system operations.
"""

from .safety_controller import SafetyController, SafetyResult

__all__ = ['SafetyController', 'SafetyResult']
