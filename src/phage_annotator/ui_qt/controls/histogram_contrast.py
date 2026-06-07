"""Extracted method group 2 for PreferencesControlsMixin."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger



class HistogramContrastMixin:
    """Method group 2 extracted from PreferencesControlsMixin."""

    def _on_pixel_size_change(self, val: float) -> None:
        """Handle the on pixel size change helper flow."""
        old_value = self.pixel_size_um_per_px
        self.pixel_size_um_per_px = float(val)
        logger = get_panel_logger("prepare")
        self._settings.setValue("defaultPixelSizeUmPerPx", self.pixel_size_um_per_px)
        logger.log_action(
            "pixel_size_change",
            old_value=round(float(old_value), 6) if old_value else None,
            new_value=round(self.pixel_size_um_per_px, 6),
        )
        if hasattr(self, "_refresh_advanced_settings_panel"):
            self._refresh_advanced_settings_panel()
        self._update_status()
        self._request_ui_refresh("preferences")
    def _on_cache_budget_change(self, val: int) -> None:
        """Handle the on cache budget change helper flow."""
        self._settings.setValue("cacheMaxMB", int(val))
        self.proj_cache.set_budget_mb(int(val))
        self._update_status()
    def _on_downsample_factor_change(self, val: int) -> None:
        """Handle the on downsample factor change helper flow."""
        self.downsample_factor = max(1, int(val))
        self._settings.setValue("downsampleFactor", self.downsample_factor)
        self._request_ui_refresh("preferences")
    def _on_downsample_toggle(self) -> None:
        """Handle the on downsample toggle helper flow."""
        self.downsample_images = self.downsample_images_chk.isChecked()
        self.downsample_hist = self.downsample_hist_chk.isChecked()
        self.downsample_profile = self.downsample_profile_chk.isChecked()
        self._settings.setValue("downsampleImages", self.downsample_images)
        self._settings.setValue("downsampleHist", self.downsample_hist)
        self._settings.setValue("downsampleProfile", self.downsample_profile)
        self._request_ui_refresh("preferences")
    def _on_pyramid_toggle(self) -> None:
        """Handle the on pyramid toggle helper flow."""
        self.pyramid_enabled = self.pyramid_chk.isChecked()
        self._settings.setValue("pyramidEnabled", self.pyramid_enabled)
        self._last_render_level = 0
        self._request_ui_refresh("preferences")
    def _on_pyramid_levels_change(self, val: int) -> None:
        """Handle the on pyramid levels change helper flow."""
        self.pyramid_max_levels = max(1, int(val))
        self._settings.setValue("pyramidMaxLevels", self.pyramid_max_levels)
        self._last_render_level = min(self._last_render_level, self.pyramid_max_levels)
        self._request_ui_refresh("preferences")
    def _on_scalebar_change(self) -> None:
        """Handle the on scalebar change helper flow."""
        self.scale_bar_enabled = self.scalebar_chk.isChecked()
        self.scale_bar_length_um = float(self.scalebar_length_spin.value())
        self.scale_bar_thickness_px = int(self.scalebar_thickness_spin.value())
        self.scale_bar_location = self.scalebar_location_combo.currentText()
        self.scale_bar_show_text = self.scalebar_text_chk.isChecked()
        self.scale_bar_background_box = self.scalebar_background_chk.isChecked()
        self.scale_bar_include_in_export = self.scalebar_export_chk.isChecked()
        self._settings.setValue("scaleBarEnabled", self.scale_bar_enabled)
        self._settings.setValue("scaleBarLengthUm", self.scale_bar_length_um)
        self._settings.setValue("scaleBarThicknessPx", self.scale_bar_thickness_px)
        self._settings.setValue("scaleBarLocation", self.scale_bar_location)
        self._settings.setValue("scaleBarShowText", self.scale_bar_show_text)
        self._settings.setValue("scaleBarBackgroundBox", self.scale_bar_background_box)
        self._settings.setValue(
            "scaleBarIncludeInExport", self.scale_bar_include_in_export
        )
        self._request_ui_refresh("preferences")
