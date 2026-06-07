"""Split definitions from test_annotation_metadata.py."""


import pytest
from datetime import datetime

from phage_annotator.annotation.metadata_schema import (
    AnnotationMetadataSchema,
    FieldConstraint,
    FieldDefinition,
    FieldType,
    get_global_schema,
)
from phage_annotator.annotation.metadata_validator import (
    MetadataValidator,
    ValidationError,
    validate_metadata,
)
from phage_annotator.annotation.label_taxonomy import (
    LabelColor,
    LabelDefinition,
    LabelTaxonomy,
    create_default_taxonomy,
)


class TestMetadataSchema:
    """Test metadata schema definitions."""
    
    def test_schema_baseline_fields(self):
        """Test that schema includes baseline fields."""
        schema = AnnotationMetadataSchema()
        assert "confidence" in schema.get_baseline_fields()
        assert "annotator" in schema.get_baseline_fields()
        assert "timestamp" in schema.get_baseline_fields()
        assert "comment" in schema.get_baseline_fields()
        assert "uncertain" in schema.get_baseline_fields()
    
    def test_add_custom_field(self):
        """Test adding custom fields."""
        schema = AnnotationMetadataSchema()
        custom = FieldDefinition(
            name="sigma",
            field_type=FieldType.FLOAT,
            display_name="Sigma",
        )
        schema.add_custom_field(custom)
        
        assert schema.has_field("sigma")
        assert schema.get_field("sigma") == custom
    
    def test_add_duplicate_field_raises(self):
        """Test that adding duplicate field raises error."""
        schema = AnnotationMetadataSchema()
        custom = FieldDefinition(
            name="confidence",
            field_type=FieldType.FLOAT,
            display_name="Confidence",
        )
        
        with pytest.raises(ValueError, match="already exists"):
            schema.add_custom_field(custom)
    
    def test_field_order(self):
        """Test field order preservation."""
        schema = AnnotationMetadataSchema()
        field_order = schema.get_field_order()
        
        assert "confidence" in field_order
        assert "annotator" in field_order
        assert len(field_order) >= 5  # At least baseline fields

class TestMetadataValidator:
    """Test metadata validation."""
    
    def test_validate_confidence_field(self):
        """Test confidence field validation."""
        validator = MetadataValidator()
        
        # Valid confidence
        meta = {"confidence": 0.75}
        normalized, errors = validator.validate_metadata(meta)
        assert len(errors) == 0
        assert normalized["confidence"] == 0.75
        
        # Valid confidence at boundaries
        normalized, errors = validator.validate_metadata({"confidence": 0.0})
        assert len(errors) == 0
        assert normalized["confidence"] == 0.0
        
        normalized, errors = validator.validate_metadata({"confidence": 1.0})
        assert len(errors) == 0
        assert normalized["confidence"] == 1.0
    
    def test_validate_confidence_out_of_range(self):
        """Test that out-of-range confidence fails."""
        validator = MetadataValidator()
        
        meta = {"confidence": 1.5}
        normalized, errors = validator.validate_metadata(meta)
        assert len(errors) == 1
        assert errors[0].field_name == "confidence"
        assert "must be in [0.0, 1.0]" in errors[0].reason.lower()
    
    def test_validate_string_field(self):
        """Test string field validation."""
        validator = MetadataValidator()
        
        meta = {"annotator": "Dr. Smith"}
        normalized, errors = validator.validate_metadata(meta)
        assert len(errors) == 0
        assert normalized["annotator"] == "Dr. Smith"
    
    def test_validate_string_max_length(self):
        """Test string max length constraint."""
        validator = MetadataValidator()
        
        # Too long annotator (max 100)
        meta = {"annotator": "a" * 101}
        normalized, errors = validator.validate_metadata(meta)
        assert len(errors) == 1
        assert "max length" in errors[0].reason.lower()
    
    def test_validate_bool_field(self):
        """Test boolean field validation."""
        validator = MetadataValidator()
        
        # Direct bool
        normalized, errors = validator.validate_metadata({"uncertain": True})
        assert len(errors) == 0
        assert normalized["uncertain"] is True
        
        # String coercion
        normalized, errors = validator.validate_metadata({"uncertain": "true"})
        assert len(errors) == 0
        assert normalized["uncertain"] is True
        
        # Int coercion
        normalized, errors = validator.validate_metadata({"uncertain": 1})
        assert len(errors) == 0
        assert normalized["uncertain"] is True
    
    def test_validate_unknown_fields_preserved(self):
        """Test that unknown fields are preserved by default."""
        validator = MetadataValidator()
        
        meta = {
            "confidence": 0.5,
            "custom_field": "custom_value",
            "unknown_int": 42,
        }
        normalized, errors = validator.validate_metadata(meta, strict=False)
        
        # No errors in non-strict mode
        assert len(errors) == 0
        
        # Unknown fields preserved
        assert normalized["custom_field"] == "custom_value"
        assert normalized["unknown_int"] == 42
    
    def test_validate_unknown_fields_strict(self):
        """Test that unknown fields fail in strict mode."""
        validator = MetadataValidator()
        
        meta = {
            "confidence": 0.5,
            "unknown_field": "value",
        }
        normalized, errors = validator.validate_metadata(meta, strict=True)
        
        # Error for unknown field
        assert len(errors) == 1
        assert errors[0].field_name == "unknown_field"
