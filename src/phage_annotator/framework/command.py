"""Command system for application commands and actions.

This module provides a simple command registry and execution framework
that enables extensibility via plugins and dynamic command discovery.

Example:
    registry = CommandRegistry()
    registry.register(OpenFileCommand())
    registry.execute('file.open', context)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass


class Command(ABC):
    """Base class for application commands."""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique command identifier (e.g., 'file.open', 'edit.undo')."""
        pass
    
    @property
    @abstractmethod
    def title(self) -> str:
        """Human-readable command title (e.g., 'Open File')."""
        pass
    
    @property
    def description(self) -> str:
        """Optional command description."""
        return ""
    
    @property
    def category(self) -> str:
        """Category for grouping commands (e.g., 'File', 'Edit', 'View')."""
        # Default to first part of command ID
        return self.id.split('.')[0].capitalize()
    
    @property
    def icon(self) -> Optional[str]:
        """Optional icon name or path."""
        return None
    
    @property
    def keybinding(self) -> Optional[str]:
        """Optional keyboard shortcut (e.g., 'Ctrl+O')."""
        return None
    
    @property
    def enabled(self) -> bool:
        """Whether command can be executed now."""
        return True
    
    @abstractmethod
    def execute(self, context: Any = None, **kwargs) -> Any:
        """Execute the command.
        
        Args:
            context: ApplicationContext or similar
            **kwargs: Command-specific arguments
            
        Returns:
            Command result (optional)
        """
        pass


@dataclass
class CommandRegistration:
    """Registration info for a command."""
    command: Command
    tags: List[str] = None
    
    def __post_init__(self):
        """Normalize derived state after dataclass initialization."""
        if self.tags is None:
            self.tags = []


class CommandRegistry:
    """Registry for managing and executing commands."""
    
    def __init__(self):
        """Initialize the object and prepare its runtime state."""
        self._commands: Dict[str, CommandRegistration] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
    
    def register(self, command: Command, tags: List[str] = None) -> None:
        """Register a command.
        
        Args:
            command: Command instance to register
            tags: Optional tags for grouping/filtering
        """
        if command.id in self._commands:
            raise ValueError(f"Command '{command.id}' already registered")
        
        self._commands[command.id] = CommandRegistration(command, tags)
        self._notify('command.registered', command)
    
    def unregister(self, command_id: str) -> None:
        """Unregister a command by ID."""
        if command_id in self._commands:
            del self._commands[command_id]
            self._notify('command.unregistered', command_id)
    
    def get(self, command_id: str) -> Optional[Command]:
        """Get a command by ID."""
        registration = self._commands.get(command_id)
        return registration.command if registration else None
    
    def execute(self, command_id: str, context: Any = None, **kwargs) -> Any:
        """Execute a command by ID.
        
        Args:
            command_id: ID of command to execute
            context: ApplicationContext or similar
            **kwargs: Command-specific arguments
            
        Returns:
            Command result
            
        Raises:
            ValueError: If command not found or not enabled
        """
        command = self.get(command_id)
        if not command:
            raise ValueError(f"Command '{command_id}' not found")
        
        if not command.enabled:
            raise ValueError(f"Command '{command_id}' is not enabled")
        
        self._notify('command.before_execute', command)
        try:
            result = command.execute(context, **kwargs)
            self._notify('command.execute', command, result)
            return result
        except Exception as e:
            self._notify('command.error', command, e)
            raise
    
    def get_all(self, category: str = None, tag: str = None) -> List[Command]:
        """Get all registered commands, optionally filtered.
        
        Args:
            category: Optional category filter (e.g., 'File', 'Edit')
            tag: Optional tag filter
            
        Returns:
            List of matching commands
        """
        commands = list(self._commands.values())
        
        if category:
            commands = [c for c in commands if c.command.category == category]
        
        if tag:
            commands = [c for c in commands if tag in c.tags]
        
        return [c.command for c in commands]
    
    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        categories = set()
        for registration in self._commands.values():
            categories.add(registration.command.category)
        return sorted(list(categories))
    
    def on(self, event_type: str, callback: Callable) -> None:
        """Register a callback for registry events.
        
        Supported events:
            - command.registered
            - command.unregistered
            - command.before_execute
            - command.execute
            - command.error
        """
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
    
    def _notify(self, event_type: str, *args) -> None:
        """Notify listeners of an event."""
        callbacks = self._callbacks.get(event_type, [])
        for callback in callbacks:
            try:
                callback(*args)
            except Exception:
                pass  # Silently ignore callback errors


# Global registry instance
_default_registry: Optional[CommandRegistry] = None


def get_registry() -> CommandRegistry:
    """Get the default global command registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = CommandRegistry()
    return _default_registry


def set_registry(registry: CommandRegistry) -> None:
    """Set the global command registry."""
    global _default_registry
    _default_registry = registry
