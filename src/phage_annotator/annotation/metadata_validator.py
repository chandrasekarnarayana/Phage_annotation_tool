"""Metadata validation for annotations.

Validates annotation metadata values against schema constraints,
handles type coercion, and provides detailed error reporting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from phage_annotator.annotation.metadata_schema import (
    AnnotationMetadataSchema,
    FieldConstraint,
    FieldDefinition,
    FieldType,
)


class ValidationError:
    """Single validation error for a metadata field."""
    
    def __init__(self, field_name: str, value: Any, reason: str):
        """Initialize validation error.
        
        Parameters
        ----------
        field_name : str
            Name of field that failed validation.
        value : Any
            Value that failed validation.
        reason : str
            Human-readable reason for failure.
        """
        self.field_name = field_name
        self.value = value
        self.reason = reason
    
    def __repr__(self) -> str:
        return f"ValidationError({self.field_name}={self.value!r}): {self.reason}"


class MetadataValidator:
    """Validates metadata against schema."""
    
    def __init__(self, schema: Optional[AnnotationMetadataSchema] = None):
        """Initialize validator with schema.
        
        Parameters
        ----------
        schema : AnnotationMetadataSchema, optional
            Schema to validate against. If None, uses global schema.
        """
        from phage_annotator.annotation.metadata_schema import get_global_schema
        self.schema = schema or get_global_schema()
    
    def validate_metadata(
        self,
        metadata: Dict[str, Any],
        strict: bool = False,
    ) -> Tuple[Dict[str, Any], List[ValidationError]]:
        """Validate and normalize metadata dict.
        
        Parameters
        ----------
        metadata : Dict[str, Any]
            Metadata to validate.
        strict : bool
            If True, fail on unknown fields. If False, preserve unknown fields.
        
        Returns
        -------
        normalized_metadata : Dict[str, Any]
            Validated and normalized metadata (may include legacy unknown fields).
        errors : List[ValidationError]
            List of validation errors. Empty if all valid.
        """
        normalized = {}
        errors = []
        
        # Process defined fields
        for field_name, definition in self.schema.get_all_fields().items():
            value = metadata.get(field_name)
            
            if value is None:
                # Use default if missing
                normalized[field_name] = definition.default
            else:
                # Validate and coerce type
                coerced, error = self._validate_field(
                    field_name, value, definition
                )
                if error:
                    errors.append(error)
                    # Still include original value
                    normalized[field_name] = value
                else:
                    normalized[field_name] = coerced
        
        # Handle unknown fields
        unknown_fields = set(metadata.keys()) - set(self.schema.get_all_fields().keys())
        if unknown_fields:
            if strict:
                for field_name in unknown_fields:
                    errors.append(ValidationError(
                        field_name,
                        metadata[field_name],
                        f"Unknown field (strict mode)"
                    ))
            else:
                # Preserve unknown fields for backward compatibility
                for field_name in unknown_fields:
                    normalized[field_name] = metadata[field_name]
        
        return normalized, errors
    
    def validate_field(
        self,
        field_name: str,
        value: Any,
    ) -> Tuple[Any, Optional[ValidationError]]:
        """Validate a single field.
        
        Parameters
        ----------
        field_name : str
            Name of field.
        value : Any
            Value to validate.
        
        Returns
        -------
        coerced_value : Any
            Coerced value.
        error : ValidationError or None
            Error if validation failed, None otherwise.
        """
        definition = self.schema.get_field(field_name)
        if definition is None:
            return value, ValidationError(
                field_name, value, "Unknown field"
            )
        
        return self._validate_field(field_name, value, definition)
    
    def _validate_field(
        self,
        field_name: str,
        value: Any,
        definition: FieldDefinition,
    ) -> Tuple[Any, Optional[ValidationError]]:
        """Internal field validation.
        
        Parameters
        ----------
        field_name : str
            Field name.
        value : Any
            Value to validate.
        definition : FieldDefinition
            Field definition.
        
        Returns
        -------
        coerced_value : Any
            Coerced value.
        error : ValidationError or None
            Error if validation failed.
        """
        # Type coercion and validation
        coerced = value
        
        if definition.field_type == FieldType.STRING:
            if not isinstance(value, str):
                return value, ValidationError(
                    field_name, value, f"Expected string, got {type(value).__name__}"
                )
            if definition.constraint.max_length and len(value) > definition.constraint.max_length:
                return value, ValidationError(
                    field_name, value, f"Exceeds max length {definition.constraint.max_length}"
                )
        
        elif definition.field_type == FieldType.INT:
            try:
                coerced = int(value)
            except (ValueError, TypeError):
                return value, ValidationError(
                    field_name, value, f"Cannot convert to int"
                )
            if self._check_numeric_constraints(coerced, definition.constraint):
                return coerced, None
            return value, ValidationError(
                field_name, value, self._numeric_constraint_msg(definition.constraint)
            )
        
        elif definition.field_type == FieldType.FLOAT:
            try:
                coerced = float(value)
            except (ValueError, TypeError):
                return value, ValidationError(
                    field_name, value, f"Cannot convert to float"
                )
            if self._check_numeric_constraints(coerced, definition.constraint):
                return coerced, None
            return value, ValidationError(
                field_name, value, self._numeric_constraint_msg(definition.constraint)
            )
        
        elif definition.field_type == FieldType.CONFIDENCE:
            try:
                coerced = float(value)
            except (ValueError, TypeError):
                return value, ValidationError(
                    field_name, value, f"Cannot convert to float"
                )
            if not (0.0 <= coerced <= 1.0):
                return value, ValidationError(
                    field_name, value, "Confidence must be in [0.0, 1.0]"
                )
            return coerced, None
        
        elif definition.field_type == FieldType.BOOL:
            if isinstance(value, bool):
                return value, None
            if isinstance(value, str):
                if value.lower() in ("true", "yes", "1"):
                    return True, None
                elif value.lower() in ("false", "no", "0"):
                    return False, None
            if isinstance(value, int):
                return bool(value), None
            return value, ValidationError(
                field_name, value, "Cannot convert to bool"
            )
        
        elif definition.field_type == FieldType.CHOICE:
            allowed = definition.constraint.allowed_values or []
            if str(value) not in allowed:
                return value, ValidationError(
                    field_name, value, f"Must be one of: {allowed}"
                )
            return value, None
        
        elif definition.field_type == FieldType.DATETIME:
            if isinstance(value, datetime):
                return value.isoformat(), None
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value)
                    return value, None
                except ValueError:
                    return value, ValidationError(
                        field_name, value, "Invalid ISO 8601 datetime"
                    )
            return value, ValidationError(
                field_name, value, "Expected datetime or ISO 8601 string"
            )
        
        # Custom validator
        if definition.constraint.validator:
            if not definition.constraint.validator(coerced):
                return value, ValidationError(
                    field_name, value, "Failed custom validation"
                )
        
        return coerced, None
    
    @staticmethod
    def _check_numeric_constraints(value: float, constraint: FieldConstraint) -> bool:
        """Check if numeric value satisfies constraints."""
        if constraint.min_value is not None and value < constraint.min_value:
            return False
        if constraint.max_value is not None and value > constraint.max_value:
            return False
        return True
    
    @staticmethod
    def _numeric_constraint_msg(constraint: FieldConstraint) -> str:
        """Generate constraint violation message."""
        if constraint.min_value is not None and constraint.max_value is not None:
            return f"Must be in [{constraint.min_value}, {constraint.max_value}]"
        elif constraint.min_value is not None:
            return f"Must be >= {constraint.min_value}"
        elif constraint.max_value is not None:
            return f"Must be <= {constraint.max_value}"
        return "Constraint violation"


def validate_metadata(metadata: Dict[str, Any]) -> Tuple[Dict[str, Any], List[ValidationError]]:
    """Validate metadata using global schema.
    
    Parameters
    ----------
    metadata : Dict[str, Any]
        Metadata to validate.
    
    Returns
    -------
    normalized_metadata : Dict[str, Any]
        Validated metadata.
    errors : List[ValidationError]
        List of validation errors.
    """
    validator = MetadataValidator()
    return validator.validate_metadata(metadata, strict=False)
