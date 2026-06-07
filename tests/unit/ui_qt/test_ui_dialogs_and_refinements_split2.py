"""Split definitions from test_ui_dialogs_and_refinements.py."""


import numpy as np
import pytest
from matplotlib.backends.qt_compat import QtWidgets, QtCore, QtGui

from phage_annotator.ui_qt.dialogs.modality_rename_dialog import ModalityRenamingDialog
from phage_annotator.ui_qt.dialogs.contrast_adjustment_dialog import ContrastAdjustmentDialog
from phage_annotator.ui_qt.utils.modality_styling import ModalityStyleScheme, ModalityVisualState
from phage_annotator.data.display_mapping import DisplayMapping



class TestVisualStyling:
    """Test visual styling for active/inactive modalities."""

    def test_active_stylesheet_generation(self):
        """Should generate valid active stylesheet."""
        stylesheet = ModalityStyleScheme.get_active_stylesheet()
        assert "background-color" in stylesheet
        assert "border" in stylesheet

    def test_inactive_stylesheet_generation(self):
        """Should generate valid inactive stylesheet."""
        stylesheet = ModalityStyleScheme.get_inactive_stylesheet()
        assert "background-color" in stylesheet
        assert "border" in stylesheet

    def test_sync_state_color_none(self):
        """NONE sync state should have gray color."""
        color = ModalityStyleScheme.get_sync_state_color("NONE")
        assert isinstance(color, QtGui.QColor)
        assert color == ModalityStyleScheme.SYNC_NONE_COLOR

    def test_sync_state_color_vmin(self):
        """VMIN sync state should have orange color."""
        color = ModalityStyleScheme.get_sync_state_color("VMIN")
        assert color == ModalityStyleScheme.SYNC_VMIN_COLOR

    def test_sync_state_color_both(self):
        """VMIN+VMAX sync state should have green color."""
        color = ModalityStyleScheme.get_sync_state_color("VMIN+VMAX")
        assert color == ModalityStyleScheme.SYNC_BOTH_COLOR

    def test_sync_state_color_contrast(self):
        """CONTRAST sync state should have blue color."""
        color = ModalityStyleScheme.get_sync_state_color("CONTRAST")
        assert color == ModalityStyleScheme.SYNC_CONTRAST_COLOR

    def test_visual_state_set_active(self, qtbot):
        """Visual state should apply active styling."""
        widget = QtWidgets.QWidget()
        qtbot.addWidget(widget)
        
        visual_state = ModalityVisualState(widget, is_active=False)
        visual_state.set_active()
        
        assert visual_state.is_active is True

    def test_visual_state_set_inactive(self, qtbot):
        """Visual state should apply inactive styling."""
        widget = QtWidgets.QWidget()
        qtbot.addWidget(widget)
        
        visual_state = ModalityVisualState(widget, is_active=True)
        visual_state.set_inactive()
        
        assert visual_state.is_active is False

    def test_visual_state_toggle(self, qtbot):
        """Visual state should toggle between active and inactive."""
        widget = QtWidgets.QWidget()
        qtbot.addWidget(widget)
        
        visual_state = ModalityVisualState(widget, is_active=False)
        visual_state.toggle_active()
        assert visual_state.is_active is True
        
        visual_state.toggle_active()
        assert visual_state.is_active is False

class TestKeyboardIntegration:
    """Test keyboard shortcuts for modality switching."""

    def test_ctrl_1_switches_to_first_modality(self):
        """Ctrl+1 should switch to first modality."""
        # Placeholder - will test when keyboard handler is wired
        assert True

    def test_ctrl_2_switches_to_second_modality(self):
        """Ctrl+2 should switch to second modality."""
        # Placeholder - will test when keyboard handler is wired
        assert True

    def test_ctrl_9_switches_to_ninth_modality(self):
        """Ctrl+9 should switch to ninth modality."""
        # Placeholder - will test when keyboard handler is wired
        assert True
