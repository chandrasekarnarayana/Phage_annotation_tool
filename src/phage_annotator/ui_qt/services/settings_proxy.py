"""Unified settings proxy bridging QSettings and settings service."""

from __future__ import annotations

from typing import Any, Optional


class UnifiedSettingsProxy:
    """QSettings-compatible wrapper that prefers settings service when available."""

    def __init__(self, qsettings, settings_service=None) -> None:
        """Initialize the object and prepare its runtime state."""
        self._qsettings = qsettings
        self._service = settings_service

    def value(self, key: str, default: Any = None, type: Optional[type] = None) -> Any:
        """Run the value workflow."""
        if self._service is not None:
            try:
                getter = getattr(self._service, "get", None)
                if callable(getter):
                    value = getter(key, default)
                else:
                    value = self._service.get_value(key, default)
                if type is not None and value is not None and not isinstance(value, type):
                    return type(value)
                return value
            except Exception:
                pass
        # PyQt's QSettings.value does not accept `type=None` on some runtimes.
        if type is None:
            return self._qsettings.value(key, default)
        return self._qsettings.value(key, default, type=type)

    def setValue(self, key: str, value: Any) -> None:
        """Run the setValue workflow."""
        if self._service is not None:
            try:
                setter = getattr(self._service, "set", None)
                if callable(setter):
                    setter(key, value)
                else:
                    self._service.set_value(key, value)
            except Exception:
                pass
        self._qsettings.setValue(key, value)

    def contains(self, key: str) -> bool:
        """Run the contains workflow."""
        return bool(self._qsettings.contains(key))

    def remove(self, key: str) -> None:
        """Remove remove for the current workflow."""
        if self._service is not None:
            try:
                remover = getattr(self._service, "remove", None)
                if callable(remover):
                    remover(key)
                else:
                    self._service.delete_value(key)
            except Exception:
                pass
        self._qsettings.remove(key)

    def clear(self) -> None:
        """Clear clear for the current workflow."""
        self._qsettings.clear()

    def allKeys(self):
        """Run the allKeys workflow."""
        return self._qsettings.allKeys()

    def sync(self) -> None:
        """Synchronize sync for the current workflow."""
        self._qsettings.sync()
