"""Default service registry implementation."""

from __future__ import annotations

import threading
from typing import Any, Dict, Type, TypeVar

from phage_annotator.framework.base import ServiceRegistry


ServiceType = TypeVar("ServiceType")


class DefaultServiceRegistry(ServiceRegistry):
    """Simple service registry backed by dict."""

    def __init__(self):
        """Initialize empty registry."""
        self._services: Dict[Type, Any] = {}
        self._lock = threading.RLock()

    def register(self, service_type: Type[ServiceType], implementation: ServiceType) -> None:
        """Register one service implementation for its interface type."""
        with self._lock:
            if service_type in self._services:
                raise ValueError(f"Service {service_type.__name__} already registered")
            self._services[service_type] = implementation

    def get(self, service_type: Type[ServiceType]) -> ServiceType:
        """Return the registered implementation for a service type."""
        with self._lock:
            if service_type not in self._services:
                raise KeyError(f"Service {service_type.__name__} not registered")
            return self._services[service_type]

    def get_or_none(self, service_type: Type[ServiceType]) -> ServiceType | None:
        """Return a service implementation or None when it is not registered."""
        with self._lock:
            return self._services.get(service_type)

    def unregister(self, service_type: Type) -> None:
        """Remove a registered service implementation if present."""
        with self._lock:
            self._services.pop(service_type, None)

    def list_services(self) -> Dict[str, Any]:
        """Return all registered services keyed by interface name."""
        with self._lock:
            return {
                svc_type.__name__: svc
                for svc_type, svc in self._services.items()
            }

    def clear(self) -> None:
        """Clear all registered services."""
        with self._lock:
            self._services.clear()
