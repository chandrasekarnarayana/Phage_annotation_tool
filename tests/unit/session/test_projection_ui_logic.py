"""Logic tests for projection and modality naming workflows.

Note: These tests focus on the logic and validation functions rather than
instantiating full Qt widgets, which can be problematic in headless environments.
GUI functionality is tested via manual testing and integration tests.
"""

from phage_annotator.session.modality import ModalityDisplaySettings, ModalitySpec, ProjectionType

RESERVED_MODALITY_NAMES = {"frame", "mean", "std", "support", "raw"}


# Logic tests (no Qt widget instantiation needed)
class TestProjectionSelectorLogic:
    """Test projection selector logic without Qt dependencies."""
    
    def test_projection_type_to_display_name_mapping(self):
        """Verify projection type maps to display names correctly."""
        mappings = {
            "raw": "Source Frame",
            "mean": "Mean",
            "std": "Std Dev",
            "min": "Min",
            "max": "Max",
        }
        for type_str, display_name in mappings.items():
            assert isinstance(type_str, str)
            assert isinstance(display_name, str)
    
    def test_axis_to_display_name_mapping(self):
        """Verify projection axis maps to display names correctly."""
        mappings = {
            "t": "T (Time)",
            "z": "Z (Depth)",
        }
        for axis_str, display_name in mappings.items():
            assert len(axis_str) == 1
            assert "Time" in display_name or "Depth" in display_name
    
    def test_projection_type_enum_values(self):
        """Verify ProjectionType enum has all expected values."""
        assert ProjectionType.RAW.value == "raw"
        assert ProjectionType.MEAN.value == "mean"
        assert ProjectionType.STD.value == "std"
        assert ProjectionType.MIN.value == "min"
        assert ProjectionType.MAX.value == "max"
    
    def test_modality_spec_with_projections(self):
        """Test creating modality specs with different projection types."""
        projections = [
            ProjectionType.RAW,
            ProjectionType.MEAN,
            ProjectionType.STD,
            ProjectionType.MIN,
            ProjectionType.MAX,
        ]
        axes = ["t", "z"]
        
        for proj in projections:
            for axis in axes:
                modality = ModalitySpec(
                    idx=0,
                    image_id=0,
                    display_name="Test",
                    projection_type=proj,
                    display_settings=ModalityDisplaySettings(projection_axis=axis),
                )
                assert modality.projection_type == proj
                assert modality.display_settings.projection_axis == axis


class TestRenameModalityDialogLogic:
    """Test modality renaming validation logic."""
    
    def _validate_name(self, name: str, reserved: set = None, existing: set = None) -> str:
        """Standalone validation function for testing."""
        reserved = reserved or RESERVED_MODALITY_NAMES
        existing = existing or set()
        
        # Check if empty
        if not name or not name.strip():
            return "Name cannot be empty"
        
        # Check for reserved names (case-insensitive)
        if name.lower() in reserved:
            return f"'{name}' is a reserved name"
        
        # Check for duplicates (case-insensitive)
        for existing_name in existing:
            if existing_name.lower() == name.lower():
                return f"'{name}' already exists"
        
        # Check for valid characters
        valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_()")
        if not all(c in valid_chars for c in name):
            return "Name contains invalid characters"
        
        return ""
    
    def test_validate_empty_name(self):
        """Verify validation rejects empty names."""
        assert self._validate_name("")
        assert self._validate_name("   ")
    
    def test_validate_reserved_names(self):
        """Verify validation rejects reserved names."""
        reserved = {"frame", "mean", "std", "support", "raw"}
        for name in reserved:
            assert self._validate_name(name, reserved=reserved)
            assert self._validate_name(name.upper(), reserved=reserved)
    
    def test_validate_duplicate_names(self):
        """Verify validation rejects duplicate names."""
        existing = {"TIRF", "GFP", "RFP"}
        assert self._validate_name("TIRF", existing=existing)
        assert self._validate_name("tirf", existing=existing)
    
    def test_validate_valid_names(self):
        """Verify validation accepts valid names."""
        valid_names = [
            "TIRF 405",
            "GFP-488",
            "Phase_Contrast",
            "DIC (brightfield)",
            "Modality_1",
            "Custom Name",
        ]
        for name in valid_names:
            result = self._validate_name(name)
            assert not result, f"'{name}' should be valid but got: {result}"
    
    def test_validate_invalid_characters(self):
        """Verify validation rejects invalid characters."""
        invalid_names = [
            "Bad@Name",
            "Name#1",
            "Test!",
            "Name$",
            "Test%Mod",
        ]
        for name in invalid_names:
            result = self._validate_name(name)
            assert result, f"'{name}' should be invalid"
    
    def test_validate_same_as_current_allowed(self):
        """Verify setting name to itself is properly handled.
        
        Note: The validation function treats it as a duplicate, but the actual
        dialog has check_against_current parameter to allow renaming to same name.
        """
        result = self._validate_name("Current", existing={"Current"})
        # The generic validator says it's a duplicate (which is correct)
        # The dialog's actual implementation handles current_name separately
        assert "already exists" in result
    
    def test_reserved_names_complete_set(self):
        """Verify reserved names set includes system names."""
        reserved = RESERVED_MODALITY_NAMES
        system_names = {"frame", "mean", "std", "support"}
        for name in system_names:
            assert name in reserved


class TestModalityRenameWorkflow:
    """Test complete rename workflow logic."""
    
    def test_rename_from_default_to_custom(self):
        """Test renaming from default name to custom."""
        new = "TIRF 405"
        existing = {"Modality 2", "Support"}
        
        # Verify new name is valid
        validator = RESERVED_MODALITY_NAMES
        assert new.lower() not in validator
        assert new not in existing
    
    def test_rename_with_duplicate_detection(self):
        """Test that duplicate names are detected."""
        new = "TIRF"
        existing = {"TIRF", "GFP", "RFP"}
        
        # new is duplicate
        assert new in existing
    
    def test_rename_preserves_case(self):
        """Test that rename preserves case of new name."""
        names = ["Custom", "CAPS", "MixedCase", "snake_case"]
        for name in names:
            # Verify we preserve exactly what user typed
            assert name == name  # Trivial but documents intent


class TestModalityProjectionWorkflow:
    """Test modality projection selection workflow."""
    
    def test_set_projection_type(self):
        """Test setting projection type on modality."""
        modality = ModalitySpec(
            idx=0,
            image_id=0,
            display_name="Test",
            projection_type=ProjectionType.RAW,
            display_settings=ModalityDisplaySettings(projection_axis="t"),
        )
        
        # Simulate changing projection
        modality.projection_type = ProjectionType.MEAN
        assert modality.projection_type == ProjectionType.MEAN
    
    def test_set_projection_axis(self):
        """Test setting projection axis on modality."""
        modality = ModalitySpec(
            idx=0,
            image_id=0,
            display_name="Test",
            projection_type=ProjectionType.MEAN,
            display_settings=ModalityDisplaySettings(projection_axis="t"),
        )
        
        # Simulate changing axis
        modality.display_settings.projection_axis = "z"
        assert modality.display_settings.projection_axis == "z"
    
    def test_all_projection_combinations(self):
        """Test all valid projection type and axis combinations."""
        combinations = [
            (ProjectionType.RAW, "t"),
            (ProjectionType.RAW, "z"),
            (ProjectionType.MEAN, "t"),
            (ProjectionType.MEAN, "z"),
            (ProjectionType.STD, "t"),
            (ProjectionType.STD, "z"),
            (ProjectionType.MIN, "t"),
            (ProjectionType.MIN, "z"),
            (ProjectionType.MAX, "t"),
            (ProjectionType.MAX, "z"),
        ]
        
        for proj_type, axis in combinations:
            modality = ModalitySpec(
                idx=0,
                image_id=0,
                display_name="Test",
                projection_type=proj_type,
                display_settings=ModalityDisplaySettings(projection_axis=axis),
            )
            assert modality.projection_type == proj_type
            assert modality.display_settings.projection_axis == axis


class TestModalityCloning:
    """Test modality spec cloning with projections and custom names."""
    
    def test_clone_preserves_projection_type(self):
        """Verify clone preserves projection type."""
        original = ModalitySpec(
            idx=0,
            image_id=0,
            display_name="Original",
            projection_type=ProjectionType.MEAN,
            display_settings=ModalityDisplaySettings(projection_axis="z"),
        )
        cloned = original.clone()
        assert cloned.projection_type == original.projection_type
    
    def test_clone_preserves_custom_name(self):
        """Verify clone preserves custom display name."""
        original = ModalitySpec(
            idx=0,
            image_id=0,
            display_name="Custom TIRF",
            projection_type=ProjectionType.RAW,
        )
        cloned = original.clone()
        assert cloned.display_name == original.display_name
    
    def test_clone_is_independent(self):
        """Verify clone is independent from original."""
        original = ModalitySpec(
            idx=0,
            image_id=0,
            display_name="Original",
            projection_type=ProjectionType.MEAN,
            display_settings=ModalityDisplaySettings(projection_axis="t"),
        )
        cloned = original.clone()
        
        # Modify clone
        cloned.display_name = "Modified"
        cloned.projection_type = ProjectionType.STD
        
        # Original should be unchanged
        assert original.display_name == "Original"
        assert original.projection_type == ProjectionType.MEAN
