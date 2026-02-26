"""Qt-specific SettingsService implementation using QSettings.

Provides persistent application settings storage using Qt's QSettings,
which handles platform-specific storage locations automatically.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
try:
    from PyQt5.QtCore import QSettings
except ImportError:
    QSettings = None

from phage_annotator.framework.services import SettingsService


class QSettingsService(SettingsService):
    """QSettings-backed settings service for persistent storage."""
    
    def __init__(self, organization: str, application: str):
        """Initialize QSettings service.
        
        Args:
            organization: Organization name (e.g., "ChandrasekarLab")
            application: Application name (e.g., "PhageAnnotator")
        """
        if QSettings is None:
            raise ImportError("PyQt5 is required for QSettingsService")
        
        self._settings = QSettings(organization, application)
        self._listeners: Dict[str, list] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value.
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        # Handle type conversion for common types
        if self._settings.contains(key):
            value = self._settings.value(key)
            # QSettings returns strings for most values, attempt type inference
            return value if value is not None else default
        return default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer setting."""
        if self._settings.contains(key):
            try:
                return int(self._settings.value(key))
            except (ValueError, TypeError):
                return default
        return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean setting."""
        if self._settings.contains(key):
            value = self._settings.value(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)
        return default
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value.
        
        Args:
            key: Setting key
            value: Value to store
        """
        self._settings.setValue(key, value)
        self._notify_changed(key, value)
    
    def set_int(self, key: str, value: int) -> None:
        """Set an integer setting."""
        self.set(key, int(value))
    
    def set_bool(self, key: str, value: bool) -> None:
        """Set a boolean setting."""
        self.set(key, bool(value))
    
    def remove(self, key: str) -> None:
        """Remove a setting.
        
        Args:
            key: Setting key to remove
        """
        if self._settings.contains(key):
            self._settings.remove(key)
            self._notify_changed(key, None)
    
    def clear(self) -> None:
        """Clear all settings."""
        self._settings.clear()
        self._notify_changed("*", None)
    
    def contains(self, key: str) -> bool:
        """Check if a setting exists."""
        return self._settings.contains(key)
    
    def keys(self) -> list:
        """Get all setting keys."""
        return self._settings.allKeys()
    
    def sync(self) -> None:
        """Sync settings to storage."""
        self._settings.sync()
    
    def on_changed(self, key: str, callback) -> None:
        """Register callback for setting changes.
        
        Args:
            key: Setting key to watch
            callback: Function to call when setting changes
        """
        if key not in self._listeners:
            self._listeners[key] = []
        self._listeners[key].append(callback)
    
    def _notify_changed(self, key: str, value: Any) -> None:
        """Notify listeners of setting change."""
        if key in self._listeners:
            for callback in self._listeners[key]:
                try:
                    callback(key, value)
                except Exception:
                    pass  # Silently ignore callback errors
