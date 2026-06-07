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


@pytest.fixture
def canvas_manager(qtbot):
    """Create a ModalityCanvasManager instance for testing."""
    manager = ModalityCanvasManager()
    qtbot.addWidget(manager)
    return manager

class TestLayoutMode:
    """Test LayoutMode enum."""
    
    def test_layout_modes_defined(self):
        """Verify all expected layout modes exist."""
        assert hasattr(LayoutMode, 'SINGLE')
        assert hasattr(LayoutMode, 'HORIZONTAL')
        assert hasattr(LayoutMode, 'VERTICAL')
        assert hasattr(LayoutMode, 'GRID_2X2')
        assert hasattr(LayoutMode, 'GRID_3X2')
        assert hasattr(LayoutMode, 'GRID_3X3')
        assert hasattr(LayoutMode, 'AUTO')
    
    def test_layout_mode_values(self):
        """Verify layout mode string values."""
        assert LayoutMode.SINGLE.value == "single"
        assert LayoutMode.HORIZONTAL.value == "horizontal"
        assert LayoutMode.AUTO.value == "auto"

class TestModalityCanvasView:
    """Test ModalityCanvasView class."""
    
    def test_view_initialization(self, qtbot):
        """Test creating a canvas view."""
        manager = ModalityCanvasManager()
        qtbot.addWidget(manager)
        
        # Set up a single modality
        manager.set_modalities([(0, "Test Modality")])
        
        view = manager.get_view(0)
        assert view is not None
        assert view.modality_idx == 0
        assert view.modality_name == "Test Modality"
        assert view.ax is not None
        assert view.canvas is not None
    
    def test_view_active_state(self, qtbot):
        """Test active/inactive visual state."""
        manager = ModalityCanvasManager()
        qtbot.addWidget(manager)
        
        manager.set_modalities([(0, "Modality A"), (1, "Modality B")])
        
        view_a = manager.get_view(0)
        view_b = manager.get_view(1)
        
        # Set A as active
        manager.set_active_modality(0)
        assert view_a._is_active is True
        assert view_b._is_active is False
        
        # Switch to B
        manager.set_active_modality(1)
        assert view_a._is_active is False
        assert view_b._is_active is True
    
    def test_view_title_update(self, qtbot):
        """Test updating modality title."""
        manager = ModalityCanvasManager()
        qtbot.addWidget(manager)
        
        manager.set_modalities([(0, "Original")])
        manager.update_modality_title(0, "Updated")
        
        view = manager.get_view(0)
        assert view.modality_name == "Updated"

class TestModalityCanvasManager:
    """Test ModalityCanvasManager class."""
    
    def test_initialization(self, canvas_manager):
        """Test manager initializes correctly."""
        assert canvas_manager._layout_mode == LayoutMode.AUTO
        assert canvas_manager._active_modality_idx is None
        assert canvas_manager._figure is not None
        assert canvas_manager._canvas is not None
    
    def test_empty_modalities(self, canvas_manager):
        """Test with no modalities."""
        canvas_manager.set_modalities([])
        assert len(canvas_manager._modality_views) == 0
    
    def test_single_modality(self, canvas_manager):
        """Test with a single modality."""
        canvas_manager.set_modalities([(0, "Single")])
        
        assert len(canvas_manager._modality_views) == 1
        view = canvas_manager.get_view(0)
        assert view is not None
        assert view.modality_name == "Single"
    
    def test_multiple_modalities(self, canvas_manager):
        """Test with multiple modalities."""
        specs = [
            (0, "TIRF"),
            (1, "Confocal"),
            (2, "Brightfield")
        ]
        canvas_manager.set_modalities(specs)
        
        assert len(canvas_manager._modality_views) == 3
        assert canvas_manager.get_view(0).modality_name == "TIRF"
        assert canvas_manager.get_view(1).modality_name == "Confocal"
        assert canvas_manager.get_view(2).modality_name == "Brightfield"
    
    def test_layout_mode_single(self, canvas_manager):
        """Test SINGLE layout mode shows only active modality."""
        specs = [(0, "A"), (1, "B"), (2, "C")]
        canvas_manager.set_modalities(specs)
        
        canvas_manager.set_layout_mode(LayoutMode.SINGLE)
        canvas_manager.set_active_modality(1)
        
        # Recreate with single mode
        canvas_manager.set_modalities(specs)
        
        # Only active modality should be visible
        assert len(canvas_manager._modality_views) == 1
        assert 1 in canvas_manager._modality_views
    
    def test_layout_mode_horizontal(self, canvas_manager):
        """Test HORIZONTAL layout creates 1xN grid."""
        specs = [(0, "A"), (1, "B"), (2, "C")]
        canvas_manager.set_layout_mode(LayoutMode.HORIZONTAL)
        canvas_manager.set_modalities(specs)
        
        rows, cols = canvas_manager._compute_layout_grid(3, LayoutMode.HORIZONTAL)
        assert rows == 1
        assert cols == 3
    
    def test_layout_mode_vertical(self, canvas_manager):
        """Test VERTICAL layout creates Nx1 grid."""
        specs = [(0, "A"), (1, "B")]
        canvas_manager.set_layout_mode(LayoutMode.VERTICAL)
        canvas_manager.set_modalities(specs)
        
        rows, cols = canvas_manager._compute_layout_grid(2, LayoutMode.VERTICAL)
        assert rows == 2
        assert cols == 1
    
    def test_layout_mode_grid_2x2(self, canvas_manager):
        """Test GRID_2X2 layout."""
        specs = [(0, "A"), (1, "B"), (2, "C"), (3, "D")]
        canvas_manager.set_layout_mode(LayoutMode.GRID_2X2)
        canvas_manager.set_modalities(specs)
        
        rows, cols = canvas_manager._compute_layout_grid(4, LayoutMode.GRID_2X2)
        assert rows == 2
        assert cols == 2
    
    def test_layout_mode_auto_selection(self, canvas_manager):
        """Test AUTO mode chooses appropriate layouts."""
        # 1 modality → 1x1
        rows, cols = canvas_manager._compute_layout_grid(1, LayoutMode.AUTO)
        assert (rows, cols) == (1, 1)
        
        # 2 modalities → 1x2
        rows, cols = canvas_manager._compute_layout_grid(2, LayoutMode.AUTO)
        assert (rows, cols) == (1, 2)
        
        # 4 modalities → 2x2
        rows, cols = canvas_manager._compute_layout_grid(4, LayoutMode.AUTO)
        assert (rows, cols) == (2, 2)
        
        # 6 modalities → 2x3
        rows, cols = canvas_manager._compute_layout_grid(6, LayoutMode.AUTO)
        assert (rows, cols) == (2, 3)
        
        # 9+ modalities → 3x3
        rows, cols = canvas_manager._compute_layout_grid(9, LayoutMode.AUTO)
        assert (rows, cols) == (3, 3)
    
    def test_active_modality_highlight(self, canvas_manager):
        """Test active modality visual highlighting."""
        specs = [(0, "A"), (1, "B")]
        canvas_manager.set_modalities(specs)
        
        canvas_manager.set_active_modality(0)
        assert canvas_manager._active_modality_idx == 0
        
        canvas_manager.set_active_modality(1)
        assert canvas_manager._active_modality_idx == 1
    
    def test_get_view(self, canvas_manager):
        """Test retrieving specific modality view."""
        canvas_manager.set_modalities([(0, "A"), (1, "B")])
        
        view_a = canvas_manager.get_view(0)
        assert view_a is not None
        assert view_a.modality_idx == 0
        
        view_missing = canvas_manager.get_view(99)
        assert view_missing is None
    
    def test_get_all_views(self, canvas_manager):
        """Test retrieving all views."""
        specs = [(0, "A"), (1, "B"), (2, "C")]
        canvas_manager.set_modalities(specs)
        
        all_views = canvas_manager.get_all_views()
        assert len(all_views) == 3
        assert 0 in all_views
        assert 1 in all_views
        assert 2 in all_views
    
    def test_canvas_click_signal(self, canvas_manager, qtbot):
        """Test modality_clicked signal emission."""
        specs = [(0, "A"), (1, "B")]
        canvas_manager.set_modalities(specs)
        
        # Monitor signal
        with qtbot.waitSignal(canvas_manager.modality_clicked, timeout=1000) as blocker:
            canvas_manager.modality_clicked.emit(1)
        
        assert blocker.args == [1]
    
    def test_layout_changed_signal(self, canvas_manager, qtbot):
        """Test layout_changed signal emission."""
        canvas_manager.set_modalities([(0, "A")])
        
        # Monitor signal
        with qtbot.waitSignal(canvas_manager.layout_changed, timeout=1000) as blocker:
            canvas_manager.set_layout_mode(LayoutMode.GRID_2X2)
        
        assert blocker.args == ["grid_2x2"]
    
    def test_canvas_property(self, canvas_manager):
        """Test canvas property accessor."""
        canvas = canvas_manager.canvas
        assert canvas is not None
        assert canvas == canvas_manager._canvas
    
    def test_figure_property(self, canvas_manager):
        """Test figure property accessor."""
        figure = canvas_manager.figure
        assert figure is not None
        assert figure == canvas_manager._figure
    
    def test_layout_mode_no_redundant_rebuild(self, canvas_manager):
        """Test setting same layout mode doesn't rebuild."""
        canvas_manager.set_modalities([(0, "A")])
        canvas_manager.set_layout_mode(LayoutMode.AUTO)
        
        initial_canvas = canvas_manager._canvas
        
        # Set same mode again
        canvas_manager.set_layout_mode(LayoutMode.AUTO)
        
        # Canvas should not be recreated
        assert canvas_manager._canvas is initial_canvas
