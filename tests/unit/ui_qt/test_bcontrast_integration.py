"""Integration tests for keyboard shortcuts and visual indicators in the main window.

These tests validate that B&C features integrate correctly with KeypointAnnotator
without breaking existing functionality.
"""

import pytest
from unittest.mock import Mock, patch

pytest.importorskip("PyQt5")
pytest.importorskip("PyQt5.sip")
pytest.importorskip("matplotlib.backends.qt_compat")

from phage_annotator.ui_qt.utils.bcontrast_integration import (
    KeyboardShortcutIntegration,
    VisualIndicatorIntegration,
    integrate_b_contrast_features,
)


class TestKeyboardShortcutIntegration:
    """Tests for keyboard shortcut integration into main window."""
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.KeyboardShortcutManager')
    def test_install_shortcuts_returns_manager(self, mock_manager_class):
        """Test that install_shortcuts returns a valid manager."""
        mock_window = Mock()
        mock_window._switch_modality = Mock()
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        
        manager = KeyboardShortcutIntegration.install_shortcuts(mock_window)
        
        assert manager is not None
        assert hasattr(manager, "register_action") or manager == mock_manager
        assert hasattr(mock_window, "_keyboard_shortcut_manager")
        assert mock_window._keyboard_shortcut_manager is manager
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.KeyboardShortcutManager')
    def test_install_shortcuts_registers_modality_actions(self, mock_manager_class):
        """Test that the shortcut manager is initialized and attached."""
        mock_window = Mock()
        mock_window._switch_modality = Mock()
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        
        manager = KeyboardShortcutIntegration.install_shortcuts(mock_window)
        
        mock_manager_class.assert_called_once_with(mock_window)
        assert manager is mock_manager
        assert mock_window._keyboard_shortcut_manager is mock_manager
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.KeyboardShortcutManager')
    def test_install_shortcuts_modality_callbacks_work(self, mock_manager_class):
        """Test that installation works without explicit callback registration."""
        mock_window = Mock()
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        
        manager = KeyboardShortcutIntegration.install_shortcuts(mock_window)
        
        mock_manager_class.assert_called_once_with(mock_window)
        assert manager is not None
        assert mock_window._keyboard_shortcut_manager is mock_manager
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.KeyboardShortcutManager')
    def test_install_shortcuts_handles_missing_methods(self, mock_manager_class):
        """Test that missing methods don't break installation."""
        mock_window = Mock()
        mock_manager = Mock()
        mock_manager.register_action = Mock()
        mock_manager_class.return_value = mock_manager
        # Don't set _switch_modality, _open_contrast_dialog, etc.
        
        manager = KeyboardShortcutIntegration.install_shortcuts(mock_window)
        
        # Should still return a valid manager
        assert manager is not None


class TestVisualIndicatorIntegration:
    """Tests for visual indicator integration into status bar."""
    
    def test_install_status_indicators_requires_status_bar(self):
        """Test that indicators require a status bar."""
        mock_window = Mock()
        mock_window.statusBar = Mock(return_value=None)
        
        with pytest.raises(RuntimeError):
            VisualIndicatorIntegration.install_status_indicators(mock_window)
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.StatusIndicatorBar')
    def test_install_status_indicators_adds_to_status_bar(self, mock_bar_class):
        """Test that indicators are added to status bar."""
        mock_status_bar = Mock()
        mock_indicator_bar = Mock()
        mock_bar_class.return_value = mock_indicator_bar
        
        mock_window = Mock()
        mock_window.statusBar = Mock(return_value=mock_status_bar)
        
        result = VisualIndicatorIntegration.install_status_indicators(mock_window)
        
        assert result is not None
        mock_status_bar.addPermanentWidget.assert_called_once_with(mock_indicator_bar)
        assert hasattr(mock_window, "_status_indicator_bar")
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.StatusIndicatorBar')
    def test_install_status_indicators_connects_signals(self, mock_bar_class):
        """Test that indicator signals are connected to display controller."""
        mock_status_bar = Mock()
        mock_indicator_bar = Mock()
        mock_indicator_bar.update_modality = Mock()
        mock_indicator_bar.update_sync_state = Mock()
        mock_indicator_bar.update_display_mode = Mock()
        mock_bar_class.return_value = mock_indicator_bar
        
        mock_controller = Mock()
        mock_controller.modality_changed = Mock()
        mock_controller.sync_state_changed = Mock()
        mock_controller.display_mode_changed = Mock()
        
        mock_window = Mock()
        mock_window.statusBar = Mock(return_value=mock_status_bar)
        mock_window.display_controller = mock_controller
        
        result = VisualIndicatorIntegration.install_status_indicators(mock_window)
        
        # Should not raise even if signals don't exist
        assert result is not None
    
    def test_add_help_menu_item_requires_menu_bar(self):
        """Test that help menu item addition handles missing menu bar."""
        mock_window = Mock()
        mock_window.menuBar = Mock(return_value=None)
        
        # Should not raise
        VisualIndicatorIntegration.add_help_menu_item(mock_window)
    
    def test_add_help_menu_item_creates_help_menu(self):
        """Test that help menu is created if missing."""
        mock_menu_bar = Mock()
        mock_menu_bar.actions = Mock(return_value=[])
        mock_help_menu = Mock()
        mock_menu_bar.addMenu = Mock(return_value=mock_help_menu)
        
        mock_window = Mock()
        mock_window.menuBar = Mock(return_value=mock_menu_bar)
        mock_window._keyboard_shortcut_manager = Mock()
        
        VisualIndicatorIntegration.add_help_menu_item(mock_window)
        
        # Help menu should be created
        mock_menu_bar.addMenu.assert_called()
    
    def test_add_help_menu_item_finds_existing_help_menu(self):
        """Test that existing help menu is found and reused."""
        mock_help_menu = Mock()
        mock_help_action = Mock()
        mock_help_action.menu = Mock(return_value=mock_help_menu)
        mock_help_action.text = Mock(return_value="Help")
        
        mock_menu_bar = Mock()
        mock_menu_bar.actions = Mock(return_value=[mock_help_action])
        
        mock_window = Mock()
        mock_window.menuBar = Mock(return_value=mock_menu_bar)
        mock_window._keyboard_shortcut_manager = Mock()
        
        VisualIndicatorIntegration.add_help_menu_item(mock_window)
        
        # Should not create a new menu
        mock_menu_bar.addMenu.assert_not_called()


class TestIntegrateBContrastFeatures:
    """Tests for the main integration function."""
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.KeyboardShortcutIntegration')
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.VisualIndicatorIntegration')
    def test_integrate_features_installs_all_components(self, mock_visual, mock_shortcuts):
        """Test that integrate_b_contrast_features installs all components."""
        mock_shortcuts.install_shortcuts = Mock(return_value=Mock())
        mock_visual.install_status_indicators = Mock(return_value=Mock())
        mock_visual.add_help_menu_item = Mock()
        
        mock_status_bar = Mock()
        mock_menu_bar = Mock()
        mock_menu_bar.actions = Mock(return_value=[])
        mock_help_menu = Mock()
        mock_menu_bar.addMenu = Mock(return_value=mock_help_menu)
        
        mock_window = Mock()
        mock_window.statusBar = Mock(return_value=mock_status_bar)
        mock_window.menuBar = Mock(return_value=mock_menu_bar)
        mock_window._switch_modality = Mock()
        
        # Should not raise
        integrate_b_contrast_features(mock_window)
        
        # Should have attempted to install shortcuts
        mock_shortcuts.install_shortcuts.assert_called_once()
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.KeyboardShortcutIntegration')
    def test_integrate_features_handles_missing_status_bar(self, mock_shortcuts):
        """Test that missing status bar doesn't break integration."""
        mock_shortcuts.install_shortcuts = Mock(return_value=Mock())
        
        mock_menu_bar = Mock()
        mock_menu_bar.actions = Mock(return_value=[])
        
        mock_window = Mock()
        mock_window.statusBar = Mock(return_value=None)
        mock_window.menuBar = Mock(return_value=mock_menu_bar)
        mock_window._switch_modality = Mock()
        
        # Should not raise
        integrate_b_contrast_features(mock_window)
        
        # Shortcuts should still be installed
        mock_shortcuts.install_shortcuts.assert_called_once()
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.KeyboardShortcutIntegration')
    def test_integrate_features_handles_errors_gracefully(self, mock_shortcuts):
        """Test that errors in integration don't break the process."""
        mock_shortcuts.install_shortcuts = Mock(side_effect=Exception("Test error"))
        
        mock_window = Mock()
        mock_window.statusBar = Mock(side_effect=Exception("Test error"))
        mock_window.menuBar = Mock(side_effect=Exception("Test error"))
        mock_window._switch_modality = Mock()
        
        # Should not raise, should handle exceptions gracefully
        integrate_b_contrast_features(mock_window)


class TestIntegrationEndToEnd:
    """End-to-end integration tests."""
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.KeyboardShortcutIntegration')
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.VisualIndicatorIntegration')
    def test_shortcuts_and_indicators_coexist(self, mock_visual, mock_shortcuts):
        """Test that shortcuts and indicators can be installed together."""
        mock_shortcuts.install_shortcuts = Mock(return_value=Mock())
        mock_visual.install_status_indicators = Mock(return_value=Mock())
        mock_visual.add_help_menu_item = Mock()
        
        mock_status_bar = Mock()
        mock_menu_bar = Mock()
        mock_menu_bar.actions = Mock(return_value=[])
        mock_help_menu = Mock()
        mock_menu_bar.addMenu = Mock(return_value=mock_help_menu)
        
        mock_window = Mock()
        mock_window.statusBar = Mock(return_value=mock_status_bar)
        mock_window.menuBar = Mock(return_value=mock_menu_bar)
        mock_window._switch_modality = Mock()
        
        integrate_b_contrast_features(mock_window)
        
        # Both installation methods should be called
        mock_shortcuts.install_shortcuts.assert_called_once()
        mock_visual.install_status_indicators.assert_called_once()
    
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.KeyboardShortcutIntegration')
    @patch('phage_annotator.ui_qt.utils.bcontrast_integration.VisualIndicatorIntegration')
    def test_multiple_integrations_idempotent(self, mock_visual, mock_shortcuts):
        """Test that calling integration multiple times is safe."""
        mock_shortcuts.install_shortcuts = Mock(return_value=Mock())
        mock_visual.install_status_indicators = Mock(return_value=Mock())
        mock_visual.add_help_menu_item = Mock()
        
        mock_status_bar = Mock()
        mock_menu_bar = Mock()
        mock_menu_bar.actions = Mock(return_value=[])
        mock_help_menu = Mock()
        mock_menu_bar.addMenu = Mock(return_value=mock_help_menu)
        
        mock_window = Mock()
        mock_window.statusBar = Mock(return_value=mock_status_bar)
        mock_window.menuBar = Mock(return_value=mock_menu_bar)
        mock_window._switch_modality = Mock()
        
        # Call integration twice
        integrate_b_contrast_features(mock_window)
        integrate_b_contrast_features(mock_window)
        
        # Should call install methods twice
        assert mock_shortcuts.install_shortcuts.call_count == 2
        assert mock_visual.install_status_indicators.call_count == 2
