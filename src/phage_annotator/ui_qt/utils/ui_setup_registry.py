"""Dock registry and panel-factory helpers for UI setup - aggregator."""
from __future__ import annotations

from phage_annotator.ui_qt.utils.ui_panel_registry import UiPanelRegistryMixin
from phage_annotator.ui_qt.utils.ui_sidebar_builder import UiSidebarBuilderMixin


class UiSetupRegistryMixin(UiPanelRegistryMixin, UiSidebarBuilderMixin):
    """Aggregated mixin for dock registry and sidebar panel factory."""
    pass
