"""Metadata schema definitions and field type system for annotations.

This module defines the annotation metadata schema with field types, 
constraints, and validation rules. Supports extensibility while 
maintaining backward compatibility with legacy fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class FieldType(Enum):
    """Metadata field data types."""
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    CHOICE = "choice"  # Enumerated values
    DATETIME = "datetime"
    CONFIDENCE = "confidence"  # Normalized 0-1 float


@dataclass
class FieldConstraint:
    """Constraints on a metadata field value."""
    
    # For numeric types: [min, max] inclusive
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
    # For string/choice: allowed values (None = any)
    allowed_values: Optional[List[str]] = None
    
    # For string: max length
    max_length: Optional[int] = None
    
    # Custom validation function
    validator: Optional[Callable[[Any], bool]] = None


@dataclass
class FieldDefinition:
    """Definition of a single metadata field.
    
    Parameters
    ----------
    name : str
        Field name (key in metadata dict).
    field_type : FieldType
        Data type of the field.
    display_name : str
        Human-readable name for UI display.
    description : str
        Help text or description.
    default : Any
        Default value when field is missing.
    required : bool
        Whether field must be present.
    editable : bool
        Whether user can edit this field.
    searchable : bool
        Whether field can be searched/filtered in UI.
    constraint : FieldConstraint
        Validation constraints.
    """
    
    name: str
    field_type: FieldType
    display_name: str
    description: str = ""
    default: Any = None
    required: bool = False
    editable: bool = True
    searchable: bool = True
    constraint: FieldConstraint = field(default_factory=FieldConstraint)


class AnnotationMetadataSchema:
    """Schema definition for annotation metadata.
    
    Defines baseline fields, their types, constraints, and validation rules.
    Supports extension with custom fields while preserving unknown legacy fields.
    """
    
    # Baseline field definitions (M0 spec freeze)
    BASELINE_FIELDS = {
        "confidence": FieldDefinition(
            name="confidence",
            field_type=FieldType.CONFIDENCE,
            display_name="Confidence",
            description="Detection confidence (0.0 = uncertain, 1.0 = certain)",
            default=None,
            required=False,
            constraint=FieldConstraint(min_value=0.0, max_value=1.0),
        ),
        "annotator": FieldDefinition(
            name="annotator",
            field_type=FieldType.STRING,
            display_name="Annotator",
            description="Name of person who made the annotation",
            default="",
            required=False,
            constraint=FieldConstraint(max_length=100),
        ),
        "timestamp": FieldDefinition(
            name="timestamp",
            field_type=FieldType.DATETIME,
            display_name="Timestamp",
            description="When the annotation was created (ISO 8601)",
            default=None,
            required=False,
        ),
        "comment": FieldDefinition(
            name="comment",
            field_type=FieldType.STRING,
            display_name="Comment",
            description="Additional notes or remarks",
            default="",
            required=False,
            constraint=FieldConstraint(max_length=500),
        ),
        "uncertain": FieldDefinition(
            name="uncertain",
            field_type=FieldType.BOOL,
            display_name="Uncertain",
            description="Mark annotation as uncertain/flagged for review",
            default=False,
            required=False,
        ),
    }
    
    def __init__(self):
        """Initialize schema with baseline fields."""
        self._fields: Dict[str, FieldDefinition] = dict(self.BASELINE_FIELDS)
        self._field_order = list(self.BASELINE_FIELDS.keys())
    
    def add_custom_field(self, definition: FieldDefinition) -> None:
        """Add a custom field definition.
        
        Parameters
        ----------
        definition : FieldDefinition
            Custom field to add.
        
        Raises
        ------
        ValueError
            If field name already exists.
        """
        if definition.name in self._fields:
            raise ValueError(f"Field '{definition.name}' already exists")
        self._fields[definition.name] = definition
        self._field_order.append(definition.name)
    
    def get_field(self, name: str) -> Optional[FieldDefinition]:
        """Get definition for a field.
        
        Parameters
        ----------
        name : str
            Field name.
        
        Returns
        -------
        FieldDefinition or None
            Field definition if found, None otherwise.
        """
        return self._fields.get(name)
    
    def get_all_fields(self) -> Dict[str, FieldDefinition]:
        """Get all defined fields."""
        return dict(self._fields)
    
    def get_field_order(self) -> List[str]:
        """Get field names in display order."""
        return list(self._field_order)
    
    def has_field(self, name: str) -> bool:
        """Check if a field is defined."""
        return name in self._fields
    
    def get_baseline_fields(self) -> Dict[str, FieldDefinition]:
        """Get only baseline fields."""
        return dict(self.BASELINE_FIELDS)
    
    def get_custom_fields(self) -> Dict[str, FieldDefinition]:
        """Get only custom (non-baseline) fields."""
        return {
            name: defn for name, defn in self._fields.items()
            if name not in self.BASELINE_FIELDS
        }


# Global schema instance (can be extended by application)
GLOBAL_METADATA_SCHEMA = AnnotationMetadataSchema()


def get_global_schema() -> AnnotationMetadataSchema:
    """Get the global metadata schema instance."""
    return GLOBAL_METADATA_SCHEMA
