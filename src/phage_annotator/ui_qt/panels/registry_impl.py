"""Backward compatibility facade for panel registry.

This module has been moved to phage_annotator.ui_qt.registry.panel_registry.
"""

from phage_annotator.ui_qt.registry.panel_registry import SidebarPanelSpec, build_sidebar_panel_registry

__all__ = ["SidebarPanelSpec", "build_sidebar_panel_registry"]
