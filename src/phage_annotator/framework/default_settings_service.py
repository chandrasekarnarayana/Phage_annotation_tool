"""Default in-memory settings service implementation."""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

from phage_annotator.framework.base import SettingsService


class DefaultSettingsService(SettingsService):
    """In-memory settings with optional file backing.

    Suitable for headless/CLI usage. UI layer wraps QSettings.
    """

    def __init__(self, defaults: Optional[Dict[str, Any]] = None):
        """Initialize settings from an optional default dictionary."""
        self._settings = defaults.copy() if defaults else {}
        self._observers: Dict[str, list[Callable]] = {}
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        """Return a setting value or the provided default."""
        with self._lock:
            return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Store a setting and notify observers when the value changes."""
        with self._lock:
            old_value = self._settings.get(key)
            self._settings[key] = value

            if key in self._observers and old_value != value:
                for callback in list(self._observers[key]):
                    try:
                        callback(key, value)
                    except Exception:
                        pass

    def get_all(self) -> Dict[str, Any]:
        """Return a shallow copy of all settings."""
        with self._lock:
            return self._settings.copy()

    def load_defaults(self) -> None:
        """Reset to defaults by clearing current settings."""
        with self._lock:
            self._settings.clear()

    def on_changed(
        self,
        key: str,
        callback: Callable[[str, Any], None],
    ) -> Callable[[], None]:
        """Subscribe to changes for one setting key."""
        with self._lock:
            if key not in self._observers:
                self._observers[key] = []
            self._observers[key].append(callback)

        def unsubscribe():
            """Remove the callback from the setting observer list."""
            with self._lock:
                if key in self._observers:
                    try:
                        self._observers[key].remove(callback)
                    except ValueError:
                        pass

        return unsubscribe
