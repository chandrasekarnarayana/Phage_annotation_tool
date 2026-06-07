"""Split definitions from test_modality_canvas.py."""

from __future__ import annotations

import pytest
from PyQt5 import QtCore

# Import directly since this is a Qt test
from phage_annotator.ui_qt.widgets.modality_canvas import (
    LayoutMode,
    ModalityCanvasManager,
    ModalityCanvasView,
)


from tests.unit.ui_qt.test_modality_canvas_split1 import canvas_manager

class TestModalityCanvasIntegration:
    """Integration tests for canvas manager."""
    
    def test_dynamic_modality_addition(self, canvas_manager):
        """Test dynamically adding modalities."""
        # Start with 1
        canvas_manager.set_modalities([(0, "A")])
        assert len(canvas_manager._modality_views) == 1
        
        # Add 2 more
        canvas_manager.set_modalities([(0, "A"), (1, "B"), (2, "C")])
        assert len(canvas_manager._modality_views) == 3
    
    def test_dynamic_modality_removal(self, canvas_manager):
        """Test dynamically removing modalities."""
        # Start with 3
        canvas_manager.set_modalities([(0, "A"), (1, "B"), (2, "C")])
        assert len(canvas_manager._modality_views) == 3
        
        # Remove one
        canvas_manager.set_modalities([(0, "A"), (1, "B")])
        assert len(canvas_manager._modality_views) == 2
        assert canvas_manager.get_view(2) is None
    
    def test_layout_switching_preserves_active(self, canvas_manager):
        """Test switching layouts preserves active modality."""
        canvas_manager.set_modalities([(0, "A"), (1, "B"), (2, "C")])
        canvas_manager.set_active_modality(1)
        
        # Switch layout
        canvas_manager.set_layout_mode(LayoutMode.GRID_2X2)
        
        # Active modality should be preserved
        assert canvas_manager._active_modality_idx == 1
    
    def test_modality_rename(self, canvas_manager):
        """Test renaming a modality."""
        canvas_manager.set_modalities([(0, "Original Name")])
        canvas_manager.update_modality_title(0, "New Name")
        
        view = canvas_manager.get_view(0)
        assert view.modality_name == "New Name"
    
    def test_max_grid_capacity(self, canvas_manager):
        """Test grid doesn't exceed capacity."""
        # Create 15 modalities but 3x3 grid only shows 9
        specs = [(i, f"Mod{i}") for i in range(15)]
        canvas_manager.set_layout_mode(LayoutMode.GRID_3X3)
        canvas_manager.set_modalities(specs)
        
        # Should only have 9 views
        assert len(canvas_manager._modality_views) <= 9
