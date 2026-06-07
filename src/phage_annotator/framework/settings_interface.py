"""Settings-service interface contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict


class SettingsService(ABC):
    """Configuration/preferences interface."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""

    @abstractmethod
    def get_all(self) -> Dict[str, Any]:
        """Get all settings as dict."""

    @abstractmethod
    def load_defaults(self) -> None:
        """Reset to default values."""

    @abstractmethod
    def on_changed(
        self,
        key: str,
        callback: Callable[[str, Any], None],
    ) -> Callable[[], None]:
        """Subscribe to changes for a specific setting."""
