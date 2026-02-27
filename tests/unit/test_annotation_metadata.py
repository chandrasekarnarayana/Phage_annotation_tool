"""Comprehensive tests for annotation organization and metadata behavior.

Tests cover:
- Metadata schema definitions and field constraints
- Metadata validation with type coercion
- Label taxonomy organization and normalization
- Metadata and label update commands
"""

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


class TestLabelTaxonomy:
    """Test label taxonomy."""
    
    def test_add_and_get_label(self):
        """Test adding and retrieving labels."""
        taxonomy = LabelTaxonomy()
        label = LabelDefinition(
            name="phage",
            display_name="Phage",
            color=LabelColor.GREEN.value,
        )
        taxonomy.add_label(label)
        
        retrieved = taxonomy.get_label("phage")
        assert retrieved == label
    
    def test_get_label_by_alias(self):
        """Test retrieving labels by alias."""
        taxonomy = LabelTaxonomy()
        label = LabelDefinition(
            name="phage",
            display_name="Phage",
            aliases=["phages", "bacteriophage"],
        )
        taxonomy.add_label(label)
        
        # Get by alias
        assert taxonomy.get_label("phages") == label
        assert taxonomy.get_label("bacteriophage") == label
    
    def test_normalize_label(self):
        """Test label normalization."""
        taxonomy = LabelTaxonomy()
        label = LabelDefinition(
            name="phage",
            display_name="Phage",
            aliases=["phages"],
        )
        taxonomy.add_label(label)
        
        # Direct name
        assert taxonomy.normalize_label("phage") == "phage"
        
        # Alias normalized to canonical name
        assert taxonomy.normalize_label("phages") == "phage"
        
        # Unknown label returned as-is
        assert taxonomy.normalize_label("unknown") == "unknown"
    
    def test_labels_by_category(self):
        """Test retrieving labels by category."""
        taxonomy = LabelTaxonomy()
        taxonomy.add_category("particles", "Particle labels")
        
        phage_label = LabelDefinition(
            name="phage",
            display_name="Phage",
            category="particles",
        )
        artifact_label = LabelDefinition(
            name="artifact",
            display_name="Artifact",
            category="defects",
        )
        
        taxonomy.add_label(phage_label)
        taxonomy.add_label(artifact_label)
        
        particles = taxonomy.get_labels_by_category("particles")
        assert len(particles) == 1
        assert particles[0].name == "phage"
    
    def test_taxonomy_serialization(self):
        """Test taxonomy round-trip serialization."""
        taxonomy = LabelTaxonomy()
        taxonomy.add_category("particles", "Particle labels")
        
        label = LabelDefinition(
            name="phage",
            display_name="Phage",
            description="Bacteriophage",
            color=LabelColor.GREEN.value,
            aliases=["phages"],
            category="particles",
        )
        taxonomy.add_label(label)
        
        # Serialize
        data = taxonomy.to_dict()
        
        # Deserialize
        restored = LabelTaxonomy.from_dict(data)
        
        # Verify
        assert restored.get_label("phage") is not None
        restored_label = restored.get_label("phage")
        assert restored_label.display_name == "Phage"
        assert restored_label.color == LabelColor.GREEN.value
        assert "phages" in restored_label.aliases
    
    def test_default_taxonomy(self):
        """Test default taxonomy creation."""
        taxonomy = create_default_taxonomy()
        
        assert taxonomy.get_label("phage") is not None
        assert taxonomy.get_label("artifact") is not None
        assert taxonomy.get_label("flagged") is not None
    
    def test_add_duplicate_label_raises(self):
        """Test that duplicate labels raise error."""
        taxonomy = LabelTaxonomy()
        label1 = LabelDefinition(name="phage", display_name="Phage")
        label2 = LabelDefinition(name="phage", display_name="Phage")
        
        taxonomy.add_label(label1)
        
        with pytest.raises(ValueError, match="already exists"):
            taxonomy.add_label(label2)


class TestMetadataIntegration:
    """Integration tests for metadata schema and validation."""
    
    def test_schema_and_validator_integration(self):
        """Test schema and validator work together."""
        schema = AnnotationMetadataSchema()
        
        # Extend schema with custom field
        custom_field = FieldDefinition(
            name="photons",
            field_type=FieldType.INT,
            display_name="Photon Count",
            constraint=FieldConstraint(min_value=0),
        )
        schema.add_custom_field(custom_field)
        
        # Validate metadata
        validator = MetadataValidator(schema)
        meta = {
            "confidence": 0.8,
            "photons": 1000,
            "custom_unknown": "ignored",
        }
        
        normalized, errors = validator.validate_metadata(meta, strict=False)
        
        # Validation succeeds
        assert len(errors) == 0
        assert normalized["confidence"] == 0.8
        assert normalized["photons"] == 1000
        assert normalized["custom_unknown"] == "ignored"
    
    def test_global_schema_instance(self):
        """Test global schema instance."""
        schema = get_global_schema()
        
        assert schema.has_field("confidence")
        assert schema.has_field("annotator")
        assert schema.has_field("timestamp")
