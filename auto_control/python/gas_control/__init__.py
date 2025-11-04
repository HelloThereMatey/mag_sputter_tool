"""Gas flow control module for Alicat APEX MFC integration.

This module provides comprehensive gas flow control for the sputter control system,
supporting Ar, O2, and N2 mass flow controllers with thread-safe operations,
safety integration, and GUI components.

Classes:
    GasFlowController: Main controller for managing multiple MFCs
    MFCChannel: Individual MFC channel representation
    GasRecipe: Gas mixture recipe management
    
Functions:
    create_gas_controller: Factory function for controller creation
"""

from .controller import GasFlowController, MFCChannel
from .recipes import GasRecipe, RecipeManager
from .safety_integration import GasFlowSafetyIntegration

__version__ = "1.0.0"
__all__ = [
    "GasFlowController",
    "MFCChannel", 
    "GasRecipe",
    "RecipeManager",
    "GasFlowSafetyIntegration",
    "create_gas_controller"
]

def create_gas_controller(config_dict: dict, safety_controller=None):
    """Factory function to create a GasFlowController instance.
    
    Args:
        config_dict: Configuration dictionary from sput.yml
        safety_controller: Optional SafetyController instance for integration
        
    Returns:
        GasFlowController: Configured gas flow controller instance
    """
    return GasFlowController(config_dict, safety_controller)