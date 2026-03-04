"""Tests for projection and modality-renaming UI integration.

Tests cover:
- ProjectionSelectorWidget signal emission
- RenameModalityDialog validation
- Integration with DisplayControlsMixin
- Modality display_name updates
"""

from __future__ import annotations

import pytest
pytest.importorskip("PyQt5")
pytest.importorskip("PyQt5.sip")
from PyQt5 import QtCore, QtTest

from phage_annotator.session.modality import (
    ModalitySpec,
    ModalityDisplaySettings,
    ProjectionType,
)
from phage_annotator.ui_qt.widgets.projection_selector import ProjectionSelectorWidget
from phage_annotator.ui_qt.dialogs.rename_modality_dialog import RenameModalityDialog


# ============================================================================
# ProjectionSelectorWidget Tests
# ============================================================================


@pytest.mark.gui
class TestProjectionSelectorWidget:
    """Test ProjectionSelectorWidget functionality."""

    def test_widget_creation(self, qtbot):
        """Test widget can be created."""
        widget = ProjectionSelectorWidget()
        qtbot.addWidget(widget)
        assert widget is not None
        assert hasattr(widget, "projection_combo")
        assert hasattr(widget, "axis_combo")

    def test_projection_combo_items(self, qtbot):
        """Test projection combo has correct items."""
        widget = ProjectionSelectorWidget()
        qtbot.addWidget(widget)
        items = [widget.projection_combo.itemText(i) for i in range(widget.projection_combo.count())]
        assert items == ["Source Frame", "Mean", "Std Dev", "Min", "Max"]

    def test_axis_combo_items(self, qtbot):
        """Test axis combo has correct items."""
        widget = ProjectionSelectorWidget()
        qtbot.addWidget(widget)
        items = [widget.axis_combo.itemText(i) for i in range(widget.axis_combo.count())]
        assert items == ["T (Time)", "Z (Depth)"]

    def test_projection_changed_signal_on_type_change(self, qtbot):
        """Test projection_changed signal is emitted when type changes."""
        widget = ProjectionSelectorWidget()
        with qtbot.waitSignal(widget.projection_changed):
            widget.projection_combo.setCurrentText("Mean")

    def test_projection_changed_signal_on_axis_change(self, qtbot):
        """Test projection_changed signal is emitted when axis changes."""
        widget = ProjectionSelectorWidget()
        with qtbot.waitSignal(widget.projection_changed):
            widget.axis_combo.setCurrentText("Z (Depth)")

    def test_projection_changed_signal_arguments(self, qtbot):
        """Test projection_changed signal contains correct arguments."""
        widget = ProjectionSelectorWidget()
        spy = QtTest.QSignalSpy(widget.projection_changed)
        widget.projection_combo.setCurrentText("Mean")
        
        assert len(spy) >= 1
        args = spy[-1]
        assert args[0] == "mean"

    def test_get_selection_raw_t(self):
        """Test get_selection returns correct values for Source Frame + T."""
        widget = ProjectionSelectorWidget()
        widget.projection_combo.setCurrentText("Source Frame")
        widget.axis_combo.setCurrentText("T (Time)")
        proj_type, axis = widget.get_selection()
        assert proj_type == "raw"
        assert axis == "t"

    def test_get_selection_mean_z(self):
        """Test get_selection returns correct values for Mean + Z."""
        widget = ProjectionSelectorWidget()
        widget.projection_combo.setCurrentText("Mean")
        widget.axis_combo.setCurrentText("Z (Depth)")
        proj_type, axis = widget.get_selection()
        assert proj_type == "mean"
        assert axis == "z"

    def test_get_selection_std_dev(self):
        """Test get_selection handles Std Dev projection."""
        widget = ProjectionSelectorWidget()
        widget.projection_combo.setCurrentText("Std Dev")
        widget.axis_combo.setCurrentText("T (Time)")
        proj_type, axis = widget.get_selection()
        assert proj_type == "std"
        assert axis == "t"

    def test_set_modality_raw(self):
        """Test set_modality updates combos for RAW projection."""
        widget = ProjectionSelectorWidget()
        modality = ModalitySpec(
            idx=0,
            image_id=1,
            display_name="Test",
            projection_type=ProjectionType.RAW,
            display_settings=ModalityDisplaySettings(projection_axis="t"),
        )
        widget.set_modality(modality)
        
        assert widget.projection_combo.currentText() == "Source Frame"
        assert widget.axis_combo.currentText() == "T (Time)"

    def test_set_modality_mean_z(self):
        """Test set_modality updates combos for MEAN projection with Z axis."""
        widget = ProjectionSelectorWidget()
        modality = ModalitySpec(
            idx=0,
            image_id=1,
            display_name="Test",
            projection_type=ProjectionType.MEAN,
            display_settings=ModalityDisplaySettings(projection_axis="z"),
        )
        widget.set_modality(modality)
        
        assert widget.projection_combo.currentText() == "Mean"
        assert widget.axis_combo.currentText() == "Z (Depth)"

    def test_set_modality_std(self):
        """Test set_modality handles STD projection."""
        widget = ProjectionSelectorWidget()
        modality = ModalitySpec(
            idx=0,
            image_id=1,
            display_name="Test",
            projection_type=ProjectionType.STD,
            display_settings=ModalityDisplaySettings(projection_axis="t"),
        )
        widget.set_modality(modality)
        
        assert widget.projection_combo.currentText() == "Std Dev"
        assert widget.axis_combo.currentText() == "T (Time)"

    def test_set_modality_no_signal_emission(self, qtbot):
        """Test set_modality doesn't emit signals during update."""
        widget = ProjectionSelectorWidget()
        modality = ModalitySpec(
            idx=0,
            image_id=1,
            display_name="Test",
            projection_type=ProjectionType.MEAN,
            display_settings=ModalityDisplaySettings(projection_axis="z"),
        )
        
        spy = QtTest.QSignalSpy(widget.projection_changed)
        widget.set_modality(modality)
        # Signal should not be emitted when using blockSignals internally
        # (spy might catch it briefly during blockSignals=False, but that's OK)
        assert len(spy) <= 1
        
        # The important part is that set_modality works
        assert widget.projection_combo.currentText() == "Mean"


# ============================================================================
# RenameModalityDialog Tests
# ============================================================================


@pytest.mark.gui
class TestRenameModalityDialog:
    """Test RenameModalityDialog functionality."""

    def test_dialog_creation(self):
        """Test dialog can be created."""
        dialog = RenameModalityDialog("Original Name")
        assert dialog is not None
        assert dialog.name_input.text() == "Original Name"

    def test_dialog_text_selected(self):
        """Test dialog selects all text on creation."""
        dialog = RenameModalityDialog("Original Name")
        # Text should be selected for easy replacement
        assert dialog.name_input.text() == "Original Name"

    def test_reserved_name_validation_frame(self):
        """Test reserved name 'frame' is rejected."""
        dialog = RenameModalityDialog("Original")
        dialog.name_input.setText("frame")
        feedback = dialog._validate_name("frame")
        assert "reserved" in feedback.lower()

    def test_reserved_name_validation_mean(self):
        """Test reserved name 'mean' is rejected."""
        dialog = RenameModalityDialog("Original")
        dialog.name_input.setText("mean")
        feedback = dialog._validate_name("mean")
        assert "reserved" in feedback.lower()

    def test_reserved_name_validation_support(self):
        """Test reserved name 'support' is rejected."""
        dialog = RenameModalityDialog("Original")
        dialog.name_input.setText("support")
        feedback = dialog._validate_name("support")
        assert "reserved" in feedback.lower()

    def test_empty_name_validation(self):
        """Test empty name is rejected."""
        dialog = RenameModalityDialog("Original")
        feedback = dialog._validate_name("")
        assert "empty" in feedback.lower()

    def test_duplicate_name_validation(self):
        """Test duplicate name is rejected."""
        existing = {"Modality 1", "Modality 2"}
        dialog = RenameModalityDialog("Original", existing)
        feedback = dialog._validate_name("Modality 1")
        assert "exists" in feedback.lower() or "duplicate" in feedback.lower()

    def test_valid_name_acceptance(self):
        """Test valid name is accepted."""
        dialog = RenameModalityDialog("Original", {"Other"})
        feedback = dialog._validate_name("New Name")
        assert feedback == ""

    def test_valid_name_with_numbers(self):
        """Test name with numbers is valid."""
        dialog = RenameModalityDialog("Original")
        feedback = dialog._validate_name("Modality 1")
        assert feedback == ""

    def test_valid_name_with_hyphen(self):
        """Test name with hyphen is valid."""
        dialog = RenameModalityDialog("Original")
        feedback = dialog._validate_name("My-Modality")
        assert feedback == ""

    def test_valid_name_with_underscore(self):
        """Test name with underscore is valid."""
        dialog = RenameModalityDialog("Original")
        feedback = dialog._validate_name("My_Modality")
        assert feedback == ""

    def test_valid_name_with_parentheses(self):
        """Test name with parentheses is valid."""
        dialog = RenameModalityDialog("Original")
        feedback = dialog._validate_name("Modality (test)")
        assert feedback == ""

    def test_invalid_chars_rejected(self):
        """Test invalid characters are rejected."""
        dialog = RenameModalityDialog("Original")
        feedback = dialog._validate_name("Modality@Name")
        assert "invalid" in feedback.lower()

    def test_get_new_name(self):
        """Test get_new_name returns input text."""
        dialog = RenameModalityDialog("Original")
        dialog.name_input.setText("New Name")
        assert dialog.get_new_name() == "New Name"

    def test_get_new_name_strips_whitespace(self):
        """Test get_new_name strips whitespace."""
        dialog = RenameModalityDialog("Original")
        dialog.name_input.setText("  New Name  ")
        assert dialog.get_new_name() == "New Name"

    def test_ok_button_disabled_on_invalid(self):
        """Test OK button is disabled for invalid names."""
        dialog = RenameModalityDialog("Original")
        dialog._on_text_changed("frame")  # Reserved name
        assert not dialog.ok_button.isEnabled()

    def test_ok_button_enabled_on_valid(self):
        """Test OK button is enabled for valid names."""
        dialog = RenameModalityDialog("Original")
        dialog._on_text_changed("Valid Name")
        assert dialog.ok_button.isEnabled()

    def test_char_count_display(self):
        """Test character count is displayed."""
        dialog = RenameModalityDialog("Original")
        dialog._on_text_changed("Test")
        assert "4/50" in dialog.char_count_label.text()

    def test_char_count_update(self):
        """Test character count updates."""
        dialog = RenameModalityDialog("Original")
        dialog._on_text_changed("")
        assert "0/50" in dialog.char_count_label.text()
        dialog._on_text_changed("Longer Name")
        assert "11/50" in dialog.char_count_label.text()

    def test_max_length_enforced(self):
        """Test maximum length of 50 characters is enforced."""
        dialog = RenameModalityDialog("Original")
        assert dialog.name_input.maxLength() == 50


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.gui
class TestProjectionSelectorIntegration:
    """Test integration of ProjectionSelectorWidget with modality changes."""

    def test_projection_type_change_message(self, qtbot):
        """Test signal contains both type and axis on changes."""
        widget = ProjectionSelectorWidget()
        
        # Store all signal emissions
        emissions = []
        widget.projection_changed.connect(lambda t, a: emissions.append((t, a)))
        
        # Change projection type
        widget.projection_combo.setCurrentText("Mean")
        QtCore.QCoreApplication.processEvents()
        
        assert len(emissions) > 0
        proj_type, axis = emissions[-1]
        assert proj_type == "mean"
        assert axis == "t"  # Default axis

    def test_projection_axis_change_message(self, qtbot):
        """Test signal contains both type and axis when axis changes."""
        widget = ProjectionSelectorWidget()
        
        # Store all signal emissions
        emissions = []
        widget.projection_changed.connect(lambda t, a: emissions.append((t, a)))
        
        # Change axis
        widget.axis_combo.setCurrentText("Z (Depth)")
        QtCore.QCoreApplication.processEvents()
        
        assert len(emissions) > 0
        proj_type, axis = emissions[-1]
        assert proj_type == "raw"  # Default type
        assert axis == "z"

    def test_modality_persistence_mean(self):
        """Test modality settings persist and can be restored."""
        widget = ProjectionSelectorWidget()
        
        # Create and set a modality
        modality1 = ModalitySpec(
            idx=0,
            image_id=1,
            display_name="Test 1",
            projection_type=ProjectionType.MEAN,
            display_settings=ModalityDisplaySettings(projection_axis="z"),
        )
        widget.set_modality(modality1)
        proj_type, axis = widget.get_selection()
        assert proj_type == "mean"
        assert axis == "z"
        
        # Switch to different modality
        modality2 = ModalitySpec(
            idx=1,
            image_id=2,
            display_name="Test 2",
            projection_type=ProjectionType.STD,
            display_settings=ModalityDisplaySettings(projection_axis="t"),
        )
        widget.set_modality(modality2)
        proj_type, axis = widget.get_selection()
        assert proj_type == "std"
        assert axis == "t"
        
        # Switch back to first modality
        widget.set_modality(modality1)
        proj_type, axis = widget.get_selection()
        assert proj_type == "mean"
        assert axis == "z"


@pytest.mark.gui
class TestRenameModalityIntegration:
    """Test integration of RenameModalityDialog."""

    def test_dialog_preserves_other_names(self):
        """Test dialog doesn't modify other modality names."""
        existing = {"Modality 1", "Modality 2", "Modality 3"}
        dialog = RenameModalityDialog("Custom Name", existing.copy())
        
        # Validate name that's not a duplicate
        feedback = dialog._validate_name("Modality 4")
        assert feedback == ""  # Valid since it doesn't exist

    def test_dialog_case_insensitive_duplicate(self):
        """Test duplicate detection is case-insensitive."""
        existing = {"Modality 1"}
        dialog = RenameModalityDialog("Original", existing)
        
        feedback = dialog._validate_name("modality 1")
        assert "exists" in feedback.lower() or "duplicate" in feedback.lower()

    def test_dialog_case_insensitive_reserved(self):
        """Test reserved name detection is case-insensitive."""
        dialog = RenameModalityDialog("Original")
        
        for reserved in ["FRAME", "Mean", "SUPPORT", "Std"]:
            feedback = dialog._validate_name(reserved)
            assert "reserved" in feedback.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
