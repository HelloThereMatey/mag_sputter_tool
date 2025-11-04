"""Gas recipe management for the sputter control system.

This module provides gas mixture recipe functionality, allowing for
predefined gas flow combinations and automatic recipe execution.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

# Support both package and script execution
try:
    from .controller import GasFlowController, MFCReading  # type: ignore
except ImportError:
    from controller import GasFlowController, MFCReading  # type: ignore


@dataclass
class GasStep:
    """A single step in a gas recipe."""
    name: str
    duration: float  # seconds
    flows: Dict[str, float]  # channel_name -> flow_rate
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GasStep':
        """Create from dictionary."""
        return cls(**data)


@dataclass  
class GasRecipe:
    """A complete gas recipe with multiple steps."""
    name: str
    description: str
    steps: List[GasStep]
    total_duration: Optional[float] = None
    created_by: str = ""
    created_at: Optional[float] = None
    
    def __post_init__(self):
        """Calculate total duration if not provided."""
        if self.total_duration is None:
            self.total_duration = sum(step.duration for step in self.steps)
        if self.created_at is None:
            self.created_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'steps': [step.to_dict() for step in self.steps],
            'total_duration': self.total_duration,
            'created_by': self.created_by,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GasRecipe':
        """Create from dictionary."""
        steps = [GasStep.from_dict(step_data) for step_data in data.get('steps', [])]
        return cls(
            name=data['name'],
            description=data.get('description', ''),
            steps=steps,
            total_duration=data.get('total_duration'),
            created_by=data.get('created_by', ''),
            created_at=data.get('created_at')
        )
    
    def validate(self, available_channels: List[str]) -> Tuple[bool, List[str]]:
        """Validate recipe against available channels.
        
        Args:
            available_channels: List of available channel names
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if not self.name:
            errors.append("Recipe name is required")
        
        if not self.steps:
            errors.append("Recipe must have at least one step")
        
        for i, step in enumerate(self.steps):
            if not step.name:
                errors.append(f"Step {i+1} name is required")
            
            if step.duration <= 0:
                errors.append(f"Step {i+1} duration must be positive")
            
            for channel, flow in step.flows.items():
                if channel not in available_channels:
                    errors.append(f"Step {i+1}: Unknown channel '{channel}'")
                
                if flow < 0:
                    errors.append(f"Step {i+1}: Negative flow rate for {channel}")
        
        return len(errors) == 0, errors


class RecipeExecutor:
    """Executes gas recipes on a GasFlowController."""
    
    def __init__(self, gas_controller: GasFlowController):
        """Initialize recipe executor.
        
        Args:
            gas_controller: The gas flow controller to execute recipes on
        """
        self.gas_controller = gas_controller
        self.logger = logging.getLogger(__name__)
        
        # Execution state
        self.current_recipe: Optional[GasRecipe] = None
        self.current_step: int = 0
        self.step_start_time: Optional[float] = None
        self.is_executing = False
        self.is_paused = False
        
        # Callbacks
        self._step_callbacks: List[callable] = []
        self._completion_callbacks: List[callable] = []
        self._error_callbacks: List[callable] = []
    
    def execute_recipe(self, recipe: GasRecipe) -> bool:
        """Start executing a gas recipe.
        
        Args:
            recipe: The recipe to execute
            
        Returns:
            bool: True if execution started successfully
        """
        if self.is_executing:
            self.logger.error("Cannot start recipe: execution already in progress")
            return False
        
        # Validate recipe
        available_channels = list(self.gas_controller.channels.keys())
        is_valid, errors = recipe.validate(available_channels)
        if not is_valid:
            self.logger.error(f"Recipe validation failed: {errors}")
            return False
        
        # Start execution
        try:
            self.current_recipe = recipe
            self.current_step = 0
            self.step_start_time = None
            self.is_executing = True
            self.is_paused = False
            
            self.logger.info(f"Starting recipe execution: {recipe.name}")
            return self._execute_current_step()
            
        except Exception as e:
            self.logger.error(f"Failed to start recipe execution: {e}")
            self._cleanup_execution()
            return False
    
    def _execute_current_step(self) -> bool:
        """Execute the current step of the recipe."""
        if not self.current_recipe or self.current_step >= len(self.current_recipe.steps):
            self._complete_execution()
            return True
        
        step = self.current_recipe.steps[self.current_step]
        
        try:
            self.logger.info(f"Executing step {self.current_step + 1}: {step.name}")
            
            # Set flow rates for all channels in this step
            success = True
            for channel, flow_rate in step.flows.items():
                if not self.gas_controller.set_flow_rate(channel, flow_rate):
                    success = False
                    self.logger.error(f"Failed to set flow rate for {channel}")
            
            if not success:
                self._error_execution("Failed to set flow rates")
                return False
            
            # Record step start time
            self.step_start_time = time.time()
            
            # Notify callbacks
            for callback in self._step_callbacks:
                try:
                    callback(self.current_step, step)
                except Exception as e:
                    self.logger.error(f"Error in step callback: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing step: {e}")
            self._error_execution(str(e))
            return False
    
    def update_execution(self) -> bool:
        """Update recipe execution (call periodically).
        
        Returns:
            bool: True if execution continues, False if completed or error
        """
        if not self.is_executing or self.is_paused:
            return self.is_executing
        
        if not self.current_recipe or not self.step_start_time:
            return False
        
        # Check if current step is complete
        step = self.current_recipe.steps[self.current_step]
        elapsed_time = time.time() - self.step_start_time
        
        if elapsed_time >= step.duration:
            # Move to next step
            self.current_step += 1
            self.step_start_time = None
            
            if self.current_step >= len(self.current_recipe.steps):
                # Recipe complete
                self._complete_execution()
                return False
            else:
                # Execute next step
                return self._execute_current_step()
        
        return True
    
    def pause_execution(self) -> bool:
        """Pause recipe execution."""
        if not self.is_executing:
            return False
        
        self.is_paused = True
        self.logger.info("Recipe execution paused")
        return True
    
    def resume_execution(self) -> bool:
        """Resume paused recipe execution."""
        if not self.is_executing or not self.is_paused:
            return False
        
        self.is_paused = False
        self.logger.info("Recipe execution resumed")
        return True
    
    def stop_execution(self) -> bool:
        """Stop recipe execution and set all flows to zero."""
        if not self.is_executing:
            return False
        
        self.logger.info("Stopping recipe execution")
        
        # Stop all flows
        self.gas_controller.stop_all_flows()
        
        self._cleanup_execution()
        return True
    
    def _complete_execution(self) -> None:
        """Handle completion of recipe execution."""
        self.logger.info(f"Recipe execution completed: {self.current_recipe.name if self.current_recipe else 'Unknown'}")
        
        # Notify completion callbacks
        for callback in self._completion_callbacks:
            try:
                callback(self.current_recipe)
            except Exception as e:
                self.logger.error(f"Error in completion callback: {e}")
        
        self._cleanup_execution()
    
    def _error_execution(self, error_message: str) -> None:
        """Handle error in recipe execution."""
        self.logger.error(f"Recipe execution error: {error_message}")
        
        # Stop all flows
        self.gas_controller.stop_all_flows()
        
        # Notify error callbacks
        for callback in self._error_callbacks:
            try:
                callback(self.current_recipe, error_message)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
        
        self._cleanup_execution()
    
    def _cleanup_execution(self) -> None:
        """Clean up execution state."""
        self.current_recipe = None
        self.current_step = 0
        self.step_start_time = None
        self.is_executing = False
        self.is_paused = False
    
    def get_execution_status(self) -> Dict[str, Any]:
        """Get current execution status."""
        if not self.is_executing:
            return {'executing': False}
        
        progress = 0.0
        if self.current_recipe and self.step_start_time:
            total_duration = self.current_recipe.total_duration or 0
            if total_duration > 0:
                # Calculate progress based on completed steps + current step progress
                completed_time = sum(
                    self.current_recipe.steps[i].duration 
                    for i in range(self.current_step)
                )
                current_step_elapsed = time.time() - self.step_start_time
                current_step_progress = min(
                    current_step_elapsed / self.current_recipe.steps[self.current_step].duration,
                    1.0
                )
                progress = (completed_time + current_step_progress * self.current_recipe.steps[self.current_step].duration) / total_duration
        
        return {
            'executing': True,
            'paused': self.is_paused,
            'recipe_name': self.current_recipe.name if self.current_recipe else None,
            'current_step': self.current_step,
            'total_steps': len(self.current_recipe.steps) if self.current_recipe else 0,
            'step_name': self.current_recipe.steps[self.current_step].name if self.current_recipe and self.current_step < len(self.current_recipe.steps) else None,
            'progress': progress,
            'step_start_time': self.step_start_time
        }
    
    def add_step_callback(self, callback: callable) -> None:
        """Add callback for step changes."""
        self._step_callbacks.append(callback)
    
    def add_completion_callback(self, callback: callable) -> None:
        """Add callback for recipe completion."""
        self._completion_callbacks.append(callback)
    
    def add_error_callback(self, callback: callable) -> None:
        """Add callback for execution errors."""
        self._error_callbacks.append(callback)


class RecipeManager:
    """Manages gas recipes - loading, saving, and organizing."""
    
    def __init__(self, recipes_dir: Optional[Path] = None):
        """Initialize recipe manager.
        
        Args:
            recipes_dir: Directory to store recipe files (default: ./gas_recipes)
        """
        if recipes_dir is None:
            recipes_dir = Path.cwd() / "gas_recipes"
        
        self.recipes_dir = Path(recipes_dir)
        self.recipes_dir.mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
        self._recipes: Dict[str, GasRecipe] = {}
        
        # Load existing recipes
        self.load_all_recipes()
    
    def save_recipe(self, recipe: GasRecipe) -> bool:
        """Save a recipe to file.
        
        Args:
            recipe: Recipe to save
            
        Returns:
            bool: True if saved successfully
        """
        try:
            filename = f"{recipe.name.replace(' ', '_').lower()}.json"
            filepath = self.recipes_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(recipe.to_dict(), f, indent=2)
            
            self._recipes[recipe.name] = recipe
            self.logger.info(f"Saved recipe: {recipe.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save recipe {recipe.name}: {e}")
            return False
    
    def load_recipe(self, name: str) -> Optional[GasRecipe]:
        """Load a recipe by name.
        
        Args:
            name: Recipe name
            
        Returns:
            GasRecipe or None if not found
        """
        if name in self._recipes:
            return self._recipes[name]
        
        # Try to load from file
        filename = f"{name.replace(' ', '_').lower()}.json"
        filepath = self.recipes_dir / filename
        
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                recipe = GasRecipe.from_dict(data)
                self._recipes[name] = recipe
                return recipe
            except Exception as e:
                self.logger.error(f"Failed to load recipe {name}: {e}")
        
        return None
    
    def load_all_recipes(self) -> None:
        """Load all recipes from the recipes directory."""
        self._recipes.clear()
        
        for filepath in self.recipes_dir.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                recipe = GasRecipe.from_dict(data)
                self._recipes[recipe.name] = recipe
                self.logger.debug(f"Loaded recipe: {recipe.name}")
            except Exception as e:
                self.logger.error(f"Failed to load recipe from {filepath}: {e}")
        
        self.logger.info(f"Loaded {len(self._recipes)} recipes")
    
    def get_recipe(self, name: str) -> Optional[GasRecipe]:
        """Get a recipe by name."""
        return self._recipes.get(name)
    
    def list_recipes(self) -> List[str]:
        """Get list of available recipe names."""
        return list(self._recipes.keys())
    
    def get_all_recipes(self) -> Dict[str, GasRecipe]:
        """Get all recipes."""
        return self._recipes.copy()
    
    def delete_recipe(self, name: str) -> bool:
        """Delete a recipe.
        
        Args:
            name: Recipe name to delete
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            # Remove from memory
            if name in self._recipes:
                del self._recipes[name]
            
            # Remove file
            filename = f"{name.replace(' ', '_').lower()}.json"
            filepath = self.recipes_dir / filename
            if filepath.exists():
                filepath.unlink()
            
            self.logger.info(f"Deleted recipe: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete recipe {name}: {e}")
            return False
    
    def create_simple_recipe(self, name: str, description: str, 
                           flows: Dict[str, float], duration: float) -> GasRecipe:
        """Create a simple single-step recipe.
        
        Args:
            name: Recipe name
            description: Recipe description
            flows: Dictionary of channel_name -> flow_rate
            duration: Duration in seconds
            
        Returns:
            GasRecipe: Created recipe
        """
        step = GasStep(
            name=f"{name} - Step 1",
            duration=duration,
            flows=flows,
            description=f"Set flows: {flows}"
        )
        
        recipe = GasRecipe(
            name=name,
            description=description,
            steps=[step]
        )
        
        return recipe
    
    def export_recipe(self, name: str, filepath: Path) -> bool:
        """Export a recipe to a specific file.
        
        Args:
            name: Recipe name
            filepath: Target file path
            
        Returns:
            bool: True if exported successfully
        """
        recipe = self.get_recipe(name)
        if not recipe:
            return False
        
        try:
            with open(filepath, 'w') as f:
                json.dump(recipe.to_dict(), f, indent=2)
            
            self.logger.info(f"Exported recipe {name} to {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export recipe {name}: {e}")
            return False
    
    def import_recipe(self, filepath: Path, overwrite: bool = False) -> bool:
        """Import a recipe from a file.
        
        Args:
            filepath: Source file path
            overwrite: Whether to overwrite existing recipe
            
        Returns:
            bool: True if imported successfully
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            recipe = GasRecipe.from_dict(data)
            
            if recipe.name in self._recipes and not overwrite:
                self.logger.warning(f"Recipe {recipe.name} already exists (use overwrite=True)")
                return False
            
            self.save_recipe(recipe)
            self.logger.info(f"Imported recipe: {recipe.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to import recipe from {filepath}: {e}")
            return False