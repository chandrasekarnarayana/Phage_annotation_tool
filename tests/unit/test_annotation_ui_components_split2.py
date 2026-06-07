"""Split definitions from test_annotation_ui_components.py."""


import pytest
from unittest.mock import Mock, MagicMock, patch

from phage_annotator.annotation.label_taxonomy import (
    LabelColor,
    LabelDefinition,
    LabelTaxonomy,
    create_default_taxonomy,
)
from phage_annotator.annotation.metadata_schema import (
    AnnotationMetadataSchema,
    FieldConstraint,
    FieldDefinition,
    FieldType,
)
from phage_annotator.core.annotation import Keypoint

pytestmark = pytest.mark.skip(
    reason="Legacy model-based annotation table architecture removed; unified runtime table uses dock table controller."
)


class TestBulkMetadataEditorDialog:
    """Test BulkMetadataEditorDialog."""
    
    @pytest.fixture
    def annotations(self):
        """Create test annotations."""
        return [
            Keypoint(
                annotation_id="ann-1",
                t=0,
                z=5,
                x=100.5,
                y=200.5,
                label="phage",
                meta={"confidence": 0.9, "annotator": "alice"},
            ),
            Keypoint(
                annotation_id="ann-2",
                t=1,
                z=6,
                x=150.0,
                y=250.0,
                label="artifact",
                meta={"confidence": 0.5, "annotator": "bob"},
            ),
        ]
    
    @pytest.fixture
    def schema(self):
        """Create test schema."""
        return AnnotationMetadataSchema()
    
    def test_dialog_creation(self, annotations, schema):
        """Test bulk dialog initializes with multiple annotations."""
        with patch("phage_annotator.ui_qt.dialogs.bulk_metadata_editor_dialog.QtWidgets.QDialog.__init__"):
            from phage_annotator.ui_qt.dialogs.bulk_metadata_editor_dialog import (
                BulkMetadataEditorDialog,
            )
            
            dialog = BulkMetadataEditorDialog(annotations, schema=schema)
            assert dialog.annotations == annotations
            assert len(dialog.annotations) == 2
    
    def test_get_updates_empty(self, annotations, schema):
        """Test get_updates returns empty dict when no fields checked."""
        with patch("phage_annotator.ui_qt.dialogs.bulk_metadata_editor_dialog.QtWidgets.QDialog.__init__"):
            from phage_annotator.ui_qt.dialogs.bulk_metadata_editor_dialog import (
                BulkMetadataEditorDialog,
            )
            
            dialog = BulkMetadataEditorDialog(annotations, schema=schema)
            
            # Create mock checkboxes that are unchecked
            for field_name in ["confidence", "annotator"]:
                mock_checkbox = Mock()
                mock_checkbox.isChecked.return_value = False
                dialog.field_widgets[field_name] = (mock_checkbox, Mock())
            
            updates = dialog.get_updates()
            assert len(updates) == 0

class TestMetadataIntegrationUI:
    """Integration tests for metadata UI components."""
    
    def test_schema_and_table_model_integration(self):
        """Test table model works with schema."""
        schema = AnnotationMetadataSchema()
        schema.add_custom_field(
            FieldDefinition(
                name="location",
                field_type=FieldType.STRING,
                display_name="Location",
                constraint=FieldConstraint(max_length=50),
            )
        )
        
        annotations = [
            Keypoint(
                annotation_id="ann-1",
                t=0,
                z=5,
                x=100.0,
                y=200.0,
                label="phage",
                meta={"confidence": 0.9, "location": "nucleus"},
            ),
        ]
        
        with patch("phage_annotator.ui_qt.models.annotation_table_model.QtCore"):
            from phage_annotator.ui_qt.models.annotation_table_model import (
                AnnotationTableModel,
            )
            
            model = AnnotationTableModel(annotations, schema=schema)
            
            # Table should include custom field
            assert "location" in model._visible_columns or model.columnCount() > 5
    
    def test_validator_applied_in_editor(self):
        """Test metadata editor uses validator."""
        schema = AnnotationMetadataSchema()
        annotation = Keypoint(
            annotation_id="ann-1",
            t=0,
            z=5,
            x=100.0,
            y=200.0,
            label="phage",
            meta={"confidence": 0.9},
        )
        
        # Schema should validate confidence 0-1
        with patch("phage_annotator.ui_qt.dialogs.metadata_editor_dialog.QtWidgets.QDialog.__init__"):
            from phage_annotator.ui_qt.dialogs.metadata_editor_dialog import (
                MetadataEditorDialog,
            )
            
            dialog = MetadataEditorDialog(annotation, schema=schema)
            assert dialog.validator is not None
            assert dialog.schema == schema

class TestLabelTaxonomyInUI:
    """Test label taxonomy integration in UI components."""
    
    def test_table_model_with_taxonomy(self):
        """Test table model respects taxonomy labels."""
        taxonomy = create_default_taxonomy()
        
        annotations = [
            Keypoint(
                annotation_id="ann-1",
                t=0,
                z=5,
                x=100.0,
                y=200.0,
                label="phage",
                meta={"confidence": 0.9},
            ),
            Keypoint(
                annotation_id="ann-2",
                t=1,
                z=6,
                x=150.0,
                y=250.0,
                label="artifact",
                meta={"confidence": 0.5},
            ),
        ]
        
        with patch("phage_annotator.ui_qt.models.annotation_table_model.QtCore"):
            from phage_annotator.ui_qt.models.annotation_table_model import (
                AnnotationTableModel,
            )
            
            model = AnnotationTableModel(annotations, taxonomy=taxonomy)
            
            # Should have taxonomy set
            assert model.taxonomy == taxonomy
    
    def test_editor_dialog_with_taxonomy(self):
        """Test metadata editor uses taxonomy for label combo."""
        taxonomy = create_default_taxonomy()
        annotation = Keypoint(
            annotation_id="ann-1",
            t=0,
            z=5,
            x=100.0,
            y=200.0,
            label="phage",
            meta={"confidence": 0.9},
        )
        
        with patch("phage_annotator.ui_qt.dialogs.metadata_editor_dialog.QtWidgets.QDialog.__init__"):
            from phage_annotator.ui_qt.dialogs.metadata_editor_dialog import (
                MetadataEditorDialog,
            )
            
            dialog = MetadataEditorDialog(annotation, taxonomy=taxonomy)
            assert dialog.taxonomy == taxonomy
