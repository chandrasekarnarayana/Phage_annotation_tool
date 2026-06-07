"""Extracted method group 3 for UiSetupMixin."""

from __future__ import annotations

from typing import List, Optional, Tuple

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.figure import Figure

from phage_annotator.ui_qt.utils import ui_actions, ui_docks
from phage_annotator.ui_qt.utils.ui_setup_registry import UiSetupRegistryMixin
from phage_annotator.ui_qt.utils.ui_setup_assist import build_assist_controls
from phage_annotator.ui_qt.utils.ui_setup_canvas import (
    build_annotation_table_panel,
    build_canvas_workspace,
)
from phage_annotator.ui_qt.utils.ui_setup_panels import (
    build_panel_policy_controls,
    refresh_panel_policy_controls,
)
from phage_annotator.ui_qt.utils.ui_setup_workspace import build_modality_loader_section
from phage_annotator.ui_qt.keyboard_registry import apply_menu_shortcuts
from phage_annotator.ui_qt.utils.constants import DEFAULT_PLAYBACK_FPS
from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.ui_qt.rendering.lut_manager import LUTS, cmap_for, lut_names
from phage_annotator.ui_qt.panels.performance import PerformancePanel
from phage_annotator.rendering.mpl import Renderer
from phage_annotator.ui_qt.models.lazy_loader import LAZY_LOADER_TREE_HEADER
from phage_annotator.ui_qt.widgets.modality_canvas import ModalityCanvasManager

try:
    from phage_annotator.ui_qt.utils.bcontrast_integration import integrate_b_contrast_features
    HAS_BCONTRAST = True
except ImportError:
    HAS_BCONTRAST = False

# Temporary feature gates.
DISABLE_QC = True
DISABLE_DIAGNOSTICS = True
DISABLE_SHORTCUTS = False



class ChannelDisplayMixin:
    """Method group 3 extracted from UiSetupMixin."""

    def _apply_default_preferences(self) -> None:
        """Apply startup preferences from QSettings without overwriting layouts."""
        preset = self._settings.value("defaultLayoutPreset", "Default", type=str)
        if not self._has_canvas_rows() and preset != "Default":
            # Loader-first startup should not auto-apply non-default canvas presets.
            self._settings.setValue("defaultLayoutPreset", "Default")
            preset = "Default"
        if preset and preset != "Default":
            if not self._settings.value("customState", type=QtCore.QByteArray):
                self.apply_preset(preset)
        default_cmap = self._settings.value("defaultColormap", lut_names()[0], type=str)
        if default_cmap in lut_names():
            self.current_cmap_idx = lut_names().index(default_cmap)
        default_fps = self._settings.value("defaultFPS", self.speed_slider.value(), type=int)
        self.speed_slider.setValue(int(default_fps))
        low_pct = float(self._settings.value("autoLowPct", 0.35))
        high_pct = float(self._settings.value("autoHighPct", 99.65))
        if self.auto_pct_label is not None:
            self.auto_pct_label.setText(f"{low_pct:.2f}% / {high_pct:.2f}%")
    def _maybe_show_first_run_welcome(self) -> None:
        """Show a first-run quick guide for onboarding and discoverability."""
        if bool(self._settings.value("firstRunWelcomeShown", False, type=bool)):
            return
        self._settings.setValue("firstRunWelcomeShown", True)
        # Non-blocking onboarding: status message instead of modal popup.
        if hasattr(self, "_status_info"):
            self._status_info(
                "Welcome: A/R/N/P review suggestions | Check status bar | Layout menu has presets",
                timeout_ms=8000,
                source="setup.first_run",
            )
        elif hasattr(self, "_status_info"):
            self._status_info(
                "Welcome: A/R/N/P review suggestions | Check status bar | Layout menu has presets",
                timeout_ms=8000,
                source="setup.first_run",
            )
    def _init_panels(self, dock_menu: QtWidgets.QMenu) -> None:
        """Initialize panels for the current workflow."""
        ui_docks.init_panels(self, dock_menu)
    def _init_channel_panel_integration(self) -> None:
        """Wire channel panel signals to session state integration."""
        panel = getattr(self, "channel_panel", None)
        if panel is None:
            self.channel_integration = None
            return
        try:
            from phage_annotator.ui_qt.integration.channel_integration import (
                ChannelPanelIntegration,
            )
        except Exception:
            self.channel_integration = None
            return
        self.channel_integration = ChannelPanelIntegration(
            self.controller,
            refresh_request_callback=lambda: self._request_ui_refresh(
                "channel-integration", image=True, status=True
            ),
        )
        panel.channel_visibility_changed.connect(
            self.channel_integration.on_channel_visibility_changed
        )
        panel.channel_opacity_changed.connect(
            self.channel_integration.on_channel_opacity_changed
        )
        panel.channel_lut_changed.connect(self.channel_integration.on_channel_lut_changed)
        panel.blend_mode_changed.connect(self.channel_integration.on_blend_mode_changed)
        self._sync_channel_panel_for_active_image()
    def _sync_channel_panel_for_active_image(self) -> None:
        """Refresh channel panel visibility/settings for the active primary image."""
        panel = getattr(self, "channel_panel", None)
        integration = getattr(self, "channel_integration", None)
        if panel is None or integration is None or not self.images:
            return
        channel_count = int(getattr(self.primary_image, "channel_count", 1) or 1)
        dock = getattr(self, "dock_channels", None)
        hidden_for_single = bool(
            getattr(self, "_channel_panel_hidden_for_single_channel", False)
        )
        if channel_count <= 1:
            panel.setEnabled(False)
            if dock is not None:
                if hasattr(self, "set_panel_visible"):
                    self.set_panel_visible(
                        "channels", False, source="channel_panel:auto_single_channel"
                    )
                else:
                    dock.setVisible(False)
                self._channel_panel_hidden_for_single_channel = True
            return
        panel.setEnabled(True)
        settings = integration.initialize_from_session(channel_count)
        self.controller.set_channel_display_settings_value(settings.to_dict())
        panel.set_channel_settings(settings)
        should_show = (
            hidden_for_single
            or not getattr(self, "_channel_panel_autoshown", False)
            or (dock is not None and not dock.isVisible())
        )
        if dock is not None and should_show:
            if hasattr(self, "set_panel_visible"):
                self.set_panel_visible("channels", True, source="channel_panel:auto_multi_channel")
            else:
                dock.setVisible(True)
            try:
                dock.raise_()
            except Exception:
                pass
            self._channel_panel_autoshown = True
            self._channel_panel_hidden_for_single_channel = False
    def _build_sidebar_pages(
        self, display_group: QtWidgets.QGroupBox
    ) -> List[Tuple[str, QtWidgets.QStyle.StandardPixmap, QtWidgets.QWidget]]:
        # Delegate to the registry-driven workflow sidebar so legacy pages like
        # "Playback Settings" do not reappear beside the fixed bottom bar.
        """Build sidebar pages for the current workflow."""
        return super()._build_sidebar_pages(display_group)
