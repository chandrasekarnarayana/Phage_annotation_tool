"""Unit tests for annotation UI components.

Tests annotation table model, metadata editors, and their integration
with the schema, validation, and taxonomy systems.
"""

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


class TestAnnotationTableModel:
    """Test AnnotationTableModel."""
    
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
                meta={
                    "confidence": 0.9,
                    "annotator": "alice",
                    "comment": "clear",
                },
            ),
            Keypoint(
                annotation_id="ann-2",
                t=1,
                z=6,
                x=150.0,
                y=250.0,
                label="artifact",
                meta={
                    "confidence": 0.5,
                    "annotator": "bob",
                    "comment": "uncertain",
                },
            ),
            Keypoint(
                annotation_id="ann-3",
                t=0,
                z=5,
                x=120.0,
                y=210.0,
                label="phage",
                meta={
                    "confidence": 0.85,
                    "annotator": "alice",
                    "comment": "good",
                },
            ),
        ]
    
    @pytest.fixture
    def schema(self):
        """Create test schema."""
        schema = AnnotationMetadataSchema()
        schema.add_custom_field(
            FieldDefinition(
                name="comment",
                field_type=FieldType.STRING,
                display_name="Comment",
                constraint=FieldConstraint(max_length=100),
            )
        )
        return schema
    
    @pytest.fixture
    def taxonomy(self):
        """Create test taxonomy."""
        return create_default_taxonomy()
    
    def test_row_count(self, annotations, schema):
        """Test row count with all annotations."""
        # Mock Qt
        with patch("phage_annotator.ui_qt.models.annotation_table_model.QtCore"):
            from phage_annotator.ui_qt.models.annotation_table_model import (
                AnnotationTableModel,
            )
            
            model = AnnotationTableModel(annotations, schema=schema)
            assert model.rowCount() == 3  # All annotations
    
    def test_column_count(self, annotations, schema):
        """Test column count includes standard + metadata columns."""
        with patch("phage_annotator.ui_qt.models.annotation_table_model.QtCore"):
            from phage_annotator.ui_qt.models.annotation_table_model import (
                AnnotationTableModel,
            )
            
            model = AnnotationTableModel(annotations, schema=schema)
            # Standard: Label, T, Z, X, Y; Metadata: Confidence, Annotator, Uncertain, Comment
            expected_columns = 5 + 4  # Standard + baseline metadata
            assert model.columnCount() == expected_columns
    
    def test_set_search_text(self, annotations, schema):
        """Test search text filtering."""
        with patch("phage_annotator.ui_qt.models.annotation_table_model.QtCore"):
            from phage_annotator.ui_qt.models.annotation_table_model import (
                AnnotationTableModel,
            )
            
            model = AnnotationTableModel(annotations, schema=schema)
            
            # Initial: all 3 annotations
            assert model.rowCount() == 3
            
            # Search for "artifact"
            model.set_search_text("artifact")
            assert model.rowCount() == 1
            
            # Clear search
            model.set_search_text("")
            assert model.rowCount() == 3
    
    def test_set_field_filter(self, annotations, schema):
        """Test metadata field filtering."""
        with patch("phage_annotator.ui_qt.models.annotation_table_model.QtCore"):
            from phage_annotator.ui_qt.models.annotation_table_model import (
                AnnotationTableModel,
            )
            
            model = AnnotationTableModel(annotations, schema=schema)
            
            # Filter by annotator
            model.set_field_filter("annotator", "alice")
            assert model.rowCount() == 2  # ann-1 and ann-3
            
            # Add another filter
            model.set_field_filter("confidence", 0.9)
            assert model.rowCount() == 1  # Only ann-1
            
            # Clear filter
            model.set_field_filter("confidence", None)
            assert model.rowCount() == 2  # Back to alice's annotations
    
    def test_get_annotation(self, annotations, schema):
        """Test retrieval of annotation by row."""
        with patch("phage_annotator.ui_qt.models.annotation_table_model.QtCore"):
            from phage_annotator.ui_qt.models.annotation_table_model import (
                AnnotationTableModel,
            )
            
            model = AnnotationTableModel(annotations, schema=schema)
            
            # Get first annotation
            ann = model.get_annotation(0)
            assert ann.annotation_id == "ann-1"
            
            # Out of range
            assert model.get_annotation(100) is None
    
    def test_set_column_visibility(self, annotations, schema):
        """Test dynamic column visibility changes."""
        with patch("phage_annotator.ui_qt.models.annotation_table_model.QtCore"):
            from phage_annotator.ui_qt.models.annotation_table_model import (
                AnnotationTableModel,
            )
            
            model = AnnotationTableModel(annotations, schema=schema)
            initial_cols = model.columnCount()
            
            # Reduce visible columns
            model.set_column_visibility(["Label", "X", "Y"])
            assert model.columnCount() == 3
    
    def test_add_remove_metadata_column(self, annotations, schema):
        """Test adding/removing metadata columns."""
        with patch("phage_annotator.ui_qt.models.annotation_table_model.QtCore"):
            from phage_annotator.ui_qt.models.annotation_table_model import (
                AnnotationTableModel,
            )
            
            # Add custom field to schema
            schema.add_custom_field(
                FieldDefinition(
                    name="photons",
                    field_type=FieldType.INT,
                    display_name="Photon Count",
                )
            )
            
            model = AnnotationTableModel(annotations, schema=schema)
            initial_cols = model.columnCount()
            
            # Add column
            model.add_metadata_column("photons")
            assert model.columnCount() == initial_cols + 1
            
            # Remove column
            model.remove_metadata_column("photons")
            assert model.columnCount() == initial_cols


class TestMetadataEditorDialog:
    """Test MetadataEditorDialog."""
    
    @pytest.fixture
    def annotation(self):
        """Create test annotation."""
        return Keypoint(
            annotation_id="ann-1",
            t=0,
            z=5,
            x=100.5,
            y=200.5,
            label="phage",
            meta={
                "confidence": 0.9,
                "annotator": "alice",
                "uncertain": False,
            },
        )
    
    @pytest.fixture
    def schema(self):
        """Create test schema."""
        schema = AnnotationMetadataSchema()
        schema.add_custom_field(
            FieldDefinition(
                name="rating",
                field_type=FieldType.INT,
                display_name="Quality Rating",
                constraint=FieldConstraint(min_value=1, max_value=10),
            )
        )
        return schema
    
    def test_dialog_creation(self, annotation, schema):
        """Test dialog initializes with annotation data."""
        with patch("phage_annotator.ui_qt.dialogs.metadata_editor_dialog.QtWidgets.QDialog.__init__"):
            from phage_annotator.ui_qt.dialogs.metadata_editor_dialog import (
                MetadataEditorDialog,
            )
            
            dialog = MetadataEditorDialog(annotation, schema=schema)
            assert dialog.annotation == annotation
            assert dialog.schema == schema
    
    def test_get_metadata_unchanged(self, annotation, schema):
        """Test get_metadata returns original if not changed."""
        with patch("phage_annotator.ui_qt.dialogs.metadata_editor_dialog.QtWidgets.QDialog.__init__"):
            with patch("phage_annotator.ui_qt.dialogs.metadata_editor_dialog.QtWidgets.QDoubleSpinBox"):
                from phage_annotator.ui_qt.dialogs.metadata_editor_dialog import (
                    MetadataEditorDialog,
                )
                
                dialog = MetadataEditorDialog(annotation, schema=schema)
                dialog.annotation.meta = annotation.meta.copy()
                
                # Create mock widgets that return original values
                mock_widget = Mock()
                mock_widget.value.return_value = 0.9
                dialog.field_widgets["confidence"] = mock_widget
                
                # Should still have original confidence
                metadata = dialog.get_metadata()
                assert "confidence" in metadata


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
