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
