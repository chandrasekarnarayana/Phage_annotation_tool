"""Preferences and configuration handlers."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.lut_manager import lut_names


class PreferencesControlsMixin:
    """Mixin for preferences and configuration handlers."""

    def _show_preferences_dialog(self) -> None:
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Preferences")
        layout = QtWidgets.QFormLayout(dlg)
        cache_spin = QtWidgets.QSpinBox()
        cache_spin.setRange(64, 8192)
        cache_spin.setValue(int(self._settings.value("cacheMaxMB", 1024, type=int)))
        recent_spin = QtWidgets.QSpinBox()
        recent_spin.setRange(0, 50)
        recent_spin.setValue(int(self._settings.value("keepRecentImages", 10, type=int)))
        preset_combo = QtWidgets.QComboBox()
        preset_combo.addItems(["Default", "Annotate", "Analyze", "Minimal"])
        preset_combo.setCurrentText(self._settings.value("defaultLayoutPreset", "Default", type=str))
        cmap_combo = QtWidgets.QComboBox()
        cmap_combo.addItems(lut_names())
        cmap_combo.setCurrentText(self._settings.value("defaultColormap", lut_names()[0], type=str))
        fps_spin = QtWidgets.QSpinBox()
        fps_spin.setRange(1, 120)
        fps_spin.setValue(int(self._settings.value("defaultFPS", 10, type=int)))
        autosave_chk = QtWidgets.QCheckBox("Enable autosave recovery")
        autosave_chk.setChecked(self._settings.value("autosaveRecoveryEnabled", True, type=bool))
        autoload_ann_chk = QtWidgets.QCheckBox("Auto-load annotations on image open")
        autoload_ann_chk.setChecked(self._settings.value("autoLoadAnnotations", True, type=bool))
        apply_meta_chk = QtWidgets.QCheckBox("Apply annotation metadata on load")
        apply_meta_chk.setChecked(self._settings.value("applyAnnotationMetaOnLoad", False, type=bool))
        encode_meta_chk = QtWidgets.QCheckBox("Encode annotation metadata in filename")
        encode_meta_chk.setChecked(self._settings.value("encodeAnnotationMetaFilename", False, type=bool))
        pyramid_chk = QtWidgets.QCheckBox("Enable multi-resolution pyramid")
        pyramid_chk.setChecked(self._settings.value("pyramidEnabled", False, type=bool))
        pyramid_levels_spin = QtWidgets.QSpinBox()
        pyramid_levels_spin.setRange(1, 4)
        pyramid_levels_spin.setValue(int(self._settings.value("pyramidMaxLevels", 3, type=int)))
        block_spin = QtWidgets.QSpinBox()
        block_spin.setRange(4, 256)
        block_spin.setValue(int(self._settings.value("prefetchBlockSizeFrames", 64, type=int)))
        inflight_spin = QtWidgets.QSpinBox()
        inflight_spin.setRange(1, 8)
        inflight_spin.setValue(int(self._settings.value("prefetchMaxInflightBlocks", 2, type=int)))
        throttle_spin = QtWidgets.QDoubleSpinBox()
        throttle_spin.setRange(0.5, 10.0)
        throttle_spin.setSingleStep(0.5)
        throttle_spin.setValue(float(self._settings.value("throttleAnalysisHzDuringPlayback", 2, type=float)))
        layout.addRow("Cache (MB)", cache_spin)
        layout.addRow("Recent images count", recent_spin)
        layout.addRow("Default layout preset", preset_combo)
        layout.addRow("Default colormap", cmap_combo)
        layout.addRow("Default FPS", fps_spin)
        layout.addRow(autosave_chk)
        layout.addRow(autoload_ann_chk)
        layout.addRow(apply_meta_chk)
        layout.addRow(encode_meta_chk)
        layout.addRow(pyramid_chk)
        layout.addRow("Pyramid levels", pyramid_levels_spin)
        layout.addRow("Prefetch block size (frames)", block_spin)
        layout.addRow("Prefetch inflight blocks", inflight_spin)
        layout.addRow("Throttle analysis (Hz)", throttle_spin)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addRow(buttons)

        def _apply() -> None:
            self._settings.setValue("cacheMaxMB", cache_spin.value())
            self._settings.setValue("keepRecentImages", recent_spin.value())
            self._settings.setValue("defaultLayoutPreset", preset_combo.currentText())
            self._settings.setValue("defaultColormap", cmap_combo.currentText())
            self._settings.setValue("defaultFPS", fps_spin.value())
            self._settings.setValue("autosaveRecoveryEnabled", autosave_chk.isChecked())
            self._settings.setValue("autoLoadAnnotations", autoload_ann_chk.isChecked())
            self._settings.setValue("applyAnnotationMetaOnLoad", apply_meta_chk.isChecked())
            self._settings.setValue(
                "encodeAnnotationMetaFilename", encode_meta_chk.isChecked()
            )
            self._settings.setValue("pyramidEnabled", pyramid_chk.isChecked())
            self._settings.setValue("pyramidMaxLevels", pyramid_levels_spin.value())
            self._settings.setValue("prefetchBlockSizeFrames", block_spin.value())
            self._settings.setValue("prefetchMaxInflightBlocks", inflight_spin.value())
            self._settings.setValue(
                "throttleAnalysisHzDuringPlayback", throttle_spin.value()
            )
            self.cache_budget_spin.setValue(cache_spin.value())
            self.speed_slider.setValue(fps_spin.value())
            if cmap_combo.currentText() in lut_names():
                self.current_cmap_idx = lut_names().index(cmap_combo.currentText())
                self.pyramid_enabled = pyramid_chk.isChecked()
                self.pyramid_max_levels = pyramid_levels_spin.value()
                if self.pyramid_chk is not None:
                    self.pyramid_chk.setChecked(self.pyramid_enabled)
                if self.pyramid_levels_spin is not None:
                    self.pyramid_levels_spin.setValue(self.pyramid_max_levels)
            if preset_combo.currentText() != "Default":
                self.apply_preset(preset_combo.currentText())
            self._refresh_image()
            dlg.accept()

        buttons.accepted.connect(_apply)
        buttons.rejected.connect(dlg.reject)
        dlg.exec()
    def _on_pixel_size_change(self, val: float) -> None:
        self.pixel_size_um_per_px = float(val)
        self._settings.setValue("defaultPixelSizeUmPerPx", self.pixel_size_um_per_px)
        self._update_status()
        self._refresh_image()

    def _on_cache_budget_change(self, val: int) -> None:
        self._settings.setValue("cacheMaxMB", int(val))
        self.proj_cache.set_budget_mb(int(val))
        self._update_status()

    def _on_downsample_factor_change(self, val: int) -> None:
        self.downsample_factor = max(1, int(val))
        self._settings.setValue("downsampleFactor", self.downsample_factor)
        self._refresh_image()

    def _on_downsample_toggle(self) -> None:
        self.downsample_images = self.downsample_images_chk.isChecked()
        self.downsample_hist = self.downsample_hist_chk.isChecked()
        self.downsample_profile = self.downsample_profile_chk.isChecked()
        self._settings.setValue("downsampleImages", self.downsample_images)
        self._settings.setValue("downsampleHist", self.downsample_hist)
        self._settings.setValue("downsampleProfile", self.downsample_profile)
        self._refresh_image()

    def _on_pyramid_toggle(self) -> None:
        self.pyramid_enabled = self.pyramid_chk.isChecked()
        self._settings.setValue("pyramidEnabled", self.pyramid_enabled)
        self._last_render_level = 0
        self._refresh_image()

    def _on_pyramid_levels_change(self, val: int) -> None:
        self.pyramid_max_levels = max(1, int(val))
        self._settings.setValue("pyramidMaxLevels", self.pyramid_max_levels)
        self._last_render_level = min(self._last_render_level, self.pyramid_max_levels)
        self._refresh_image()

    def _on_scalebar_change(self) -> None:
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
        self._settings.setValue("scaleBarIncludeInExport", self.scale_bar_include_in_export)
        self._refresh_image()
