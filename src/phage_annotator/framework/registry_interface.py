"""Service-registry interface contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar


ServiceType = TypeVar("ServiceType")


class ServiceRegistry(ABC):
    """Registry for looking up services by type."""

    @abstractmethod
    def register(self, service_type: Type[ServiceType], implementation: ServiceType) -> None:
        """Register a service implementation."""

    @abstractmethod
    def get(self, service_type: Type[ServiceType]) -> ServiceType:
        """Get a registered service."""

    @abstractmethod
    def get_or_none(self, service_type: Type[ServiceType]) -> Optional[ServiceType]:
        """Get a service, or None if not registered."""

    @abstractmethod
    def unregister(self, service_type: Type) -> None:
        """Unregister a service."""

    @abstractmethod
    def list_services(self) -> Dict[str, Any]:
        """List all registered services."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all services."""
