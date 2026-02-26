"""Plugin discovery and management system.

This module provides plugin loading, discovery, and lifecycle management
using setuptools entry points. Plugins can extend functionality dynamically.

Example:
    manager = PluginManager()
    manager.load_plugins()  # Load entry points
    for plugin in manager.get_plugins():
        plugin.activate(context)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass
import importlib
import importlib.metadata as metadata
import logging

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Base class for application plugins."""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Unique plugin identifier."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""
        pass
    
    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"
    
    @property
    def description(self) -> str:
        """Plugin description."""
        return ""
    
    @property
    def author(self) -> str:
        """Plugin author."""
        return ""
    
    @property
    def dependencies(self) -> List[str]:
        """List of plugin IDs this plugin depends on."""
        return []
    
    @property
    def enabled(self) -> bool:
        """Whether plugin is enabled."""
        return True
    
    @abstractmethod
    def initialize(self, context: Any) -> None:
        """Initialize plugin with application context.
        
        Args:
            context: ApplicationContext
        """
        pass
    
    @abstractmethod
    def activate(self, context: Any) -> None:
        """Activate plugin to start providing functionality.
        
        Args:
            context: ApplicationContext
        """
        pass
    
    def deactivate(self, context: Any) -> None:
        """Deactivate plugin, cleaning up resources.
        
        Args:
            context: ApplicationContext (optional)
        """
        pass
    
    def cleanup(self) -> None:
        """Clean up plugin resources on shutdown."""
        pass


@dataclass
class PluginMetadata:
    """Plugin metadata loaded from entry point."""
    id: str
    name: str
    module: str
    entry_point: str
    loaded: bool = False
    instance: Optional[Plugin] = None
    error: Optional[str] = None


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""
    
    ENTRY_POINT_GROUP = "phage_annotator.plugins"
    
    def __init__(self):
        self._plugins: Dict[str, PluginMetadata] = {}
        self._loaded_plugins: Dict[str, Plugin] = {}
        self._context: Optional[Any] = None
    
    def discover_plugins(self) -> List[PluginMetadata]:
        """Discover plugins from entry points.
        
        Returns:
            List of discovered plugin metadata
        """
        plugins = []
        
        try:
            entry_points = metadata.entry_points()
            # Handle both Python 3.10+ and earlier APIs
            if hasattr(entry_points, 'select'):
                # Python 3.10+
                group = entry_points.select(group=self.ENTRY_POINT_GROUP)
            else:
                # Python 3.9 and earlier
                group = entry_points.get(self.ENTRY_POINT_GROUP, [])
            
            for entry_point in group:
                metadata_obj = PluginMetadata(
                    id=entry_point.name,
                    name=entry_point.name,
                    module=entry_point.value.split(':')[0],
                    entry_point=entry_point.value,
                )
                self._plugins[entry_point.name] = metadata_obj
                plugins.append(metadata_obj)
                logger.debug(f"Discovered plugin: {entry_point.name} -> {entry_point.value}")
        
        except Exception as e:
            logger.warning(f"Error discovering plugins: {e}")
        
        return plugins
    
    def load_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Load a specific plugin.
        
        Args:
            plugin_id: Plugin ID to load
            
        Returns:
            Loaded plugin instance or None if failed
        """
        if plugin_id in self._loaded_plugins:
            return self._loaded_plugins[plugin_id]
        
        metadata_obj = self._plugins.get(plugin_id)
        if not metadata_obj:
            logger.error(f"Plugin '{plugin_id}' not found")
            return None
        
        try:
            # Parse entry point: "module:class"
            module_name, class_name = metadata_obj.entry_point.split(':')
            module = importlib.import_module(module_name)
            plugin_class = getattr(module, class_name)
            
            # Instantiate plugin
            instance = plugin_class()
            metadata_obj.instance = instance
            metadata_obj.loaded = True
            
            self._loaded_plugins[plugin_id] = instance
            logger.info(f"Loaded plugin: {plugin_id}")
            
            return instance
        
        except Exception as e:
            metadata_obj.error = str(e)
            logger.error(f"Failed to load plugin '{plugin_id}': {e}")
            return None
    
    def load_plugins(self, plugin_ids: List[str] = None) -> Dict[str, Plugin]:
        """Load plugins (all or specified).
        
        Args:
            plugin_ids: Specific plugins to load. If None, loads all.
            
        Returns:
            Dict mapping plugin IDs to instances
        """
        if plugin_ids is None:
            plugin_ids = list(self._plugins.keys())
        
        for plugin_id in plugin_ids:
            self.load_plugin(plugin_id)
        
        return self._loaded_plugins
    
    def initialize_plugins(self, context: Any) -> None:
        """Initialize all loaded plugins.
        
        Args:
            context: ApplicationContext
        """
        self._context = context
        
        for plugin_id, plugin in self._loaded_plugins.items():
            try:
                if not plugin.enabled:
                    logger.info(f"Skipping disabled plugin: {plugin_id}")
                    continue
                
                plugin.initialize(context)
                logger.info(f"Initialized plugin: {plugin_id}")
            
            except Exception as e:
                logger.error(f"Failed to initialize plugin '{plugin_id}': {e}")
    
    def activate_plugins(self, context: Any = None) -> None:
        """Activate all initialized plugins.
        
        Args:
            context: ApplicationContext (uses stored context if not provided)
        """
        if context is None:
            context = self._context
        
        if context is None:
            raise ValueError("No context provided and none stored")
        
        for plugin_id, plugin in self._loaded_plugins.items():
            try:
                if not plugin.enabled:
                    continue
                
                plugin.activate(context)
                logger.info(f"Activated plugin: {plugin_id}")
            
            except Exception as e:
                logger.error(f"Failed to activate plugin '{plugin_id}': {e}")
    
    def deactivate_plugins(self) -> None:
        """Deactivate all active plugins."""
        for plugin_id, plugin in self._loaded_plugins.items():
            try:
                plugin.deactivate(self._context)
                logger.info(f"Deactivated plugin: {plugin_id}")
            
            except Exception as e:
                logger.error(f"Failed to deactivate plugin '{plugin_id}': {e}")
    
    def cleanup_plugins(self) -> None:
        """Clean up all plugins on shutdown."""
        for plugin_id, plugin in self._loaded_plugins.items():
            try:
                plugin.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up plugin '{plugin_id}': {e}")
    
    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get a loaded plugin by ID."""
        return self._loaded_plugins.get(plugin_id)
    
    def get_all_plugins(self) -> List[Plugin]:
        """Get all loaded plugins."""
        return list(self._loaded_plugins.values())
    
    def get_plugin_metadata(self, plugin_id: str) -> Optional[PluginMetadata]:
        """Get plugin metadata."""
        return self._plugins.get(plugin_id)
    
    def get_all_metadata(self) -> List[PluginMetadata]:
        """Get metadata for all discovered plugins."""
        return list(self._plugins.values())


# Global plugin manager instance
_default_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the default global plugin manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = PluginManager()
    return _default_manager


def set_plugin_manager(manager: PluginManager) -> None:
    """Set the global plugin manager."""
    global _default_manager
    _default_manager = manager
