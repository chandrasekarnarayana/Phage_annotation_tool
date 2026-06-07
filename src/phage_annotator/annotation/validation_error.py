"""Validation error objects for annotation metadata checks."""

from __future__ import annotations

from typing import Any


class ValidationError:
    """Single validation error for a metadata field."""

    def __init__(self, field_name: str, value: Any, reason: str):
        """Record the field, value, and reason for a validation failure."""
        self.field_name = field_name
        self.value = value
        self.reason = reason

    def __repr__(self) -> str:
        """Return a developer-friendly representation for diagnostics."""
        return f"ValidationError({self.field_name}={self.value!r}): {self.reason}"
