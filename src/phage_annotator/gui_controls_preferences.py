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
        cache_spin.setToolTip("Maximum memory (MB) for caching projections and pyramids")
        recent_spin = QtWidgets.QSpinBox()
        recent_spin.setRange(0, 50)
        recent_spin.setValue(
            int(self._settings.value("keepRecentImages", 10, type=int))
        )
        recent_spin.setToolTip("Number of recent file paths to remember")
        preset_combo = QtWidgets.QComboBox()
        preset_combo.addItems(["Default", "Annotate", "Analyze", "Minimal"])
        preset_combo.setCurrentText(
            self._settings.value("defaultLayoutPreset", "Default", type=str)
        )
        preset_combo.setToolTip("Default dock layout on startup")
        cmap_combo = QtWidgets.QComboBox()
        cmap_combo.addItems(lut_names())
        cmap_combo.setCurrentText(
            self._settings.value("defaultColormap", lut_names()[0], type=str)
        )
        cmap_combo.setToolTip("Default colormap/LUT for new images")
        fps_spin = QtWidgets.QSpinBox()
        fps_spin.setRange(1, 120)
        fps_spin.setValue(int(self._settings.value("defaultFPS", 10, type=int)))
        fps_spin.setToolTip("Default playback speed (frames per second)")
        autosave_chk = QtWidgets.QCheckBox("Enable autosave recovery")
        autosave_chk.setChecked(
            self._settings.value("autosaveRecoveryEnabled", True, type=bool)
        )
        autosave_chk.setToolTip("Periodically save session state for crash recovery")
        autoload_ann_chk = QtWidgets.QCheckBox("Auto-load annotations on image open")
        autoload_ann_chk.setChecked(
            self._settings.value("autoLoadAnnotations", True, type=bool)
        )
        autoload_ann_chk.setToolTip("Automatically load matching annotation files when opening images")
        apply_meta_chk = QtWidgets.QCheckBox("Apply annotation metadata on load")
        apply_meta_chk.setChecked(
            self._settings.value("applyAnnotationMetaOnLoad", False, type=bool)
        )
        apply_meta_chk.setToolTip("Apply ROI/crop/display settings from annotation metadata")
        encode_meta_chk = QtWidgets.QCheckBox("Encode annotation metadata in filename")
        encode_meta_chk.setChecked(
            self._settings.value("encodeAnnotationMetaFilename", False, type=bool)
        )
        encode_meta_chk.setToolTip("Include ROI/crop/display info in saved annotation filenames")
        pyramid_chk = QtWidgets.QCheckBox("Enable multi-resolution pyramid")
        pyramid_chk.setChecked(self._settings.value("pyramidEnabled", False, type=bool))
        pyramid_chk.setToolTip("Generate multi-resolution image pyramids for faster zooming")
        pyramid_levels_spin = QtWidgets.QSpinBox()
        pyramid_levels_spin.setRange(1, 4)
        pyramid_levels_spin.setValue(
            int(self._settings.value("pyramidMaxLevels", 3, type=int))
        )
        pyramid_levels_spin.setToolTip("Number of pyramid levels (1=original only, 4=max downsampling)")
        block_spin = QtWidgets.QSpinBox()
        block_spin.setRange(4, 256)
        block_spin.setValue(
            int(self._settings.value("prefetchBlockSizeFrames", 64, type=int))
        )
        block_spin.setToolTip("Number of frames to prefetch as a batch during playback")
        inflight_spin = QtWidgets.QSpinBox()
        inflight_spin.setRange(1, 8)
        inflight_spin.setValue(
            int(self._settings.value("prefetchMaxInflightBlocks", 2, type=int))
        )
        inflight_spin.setToolTip("Maximum concurrent prefetch operations")
        throttle_spin = QtWidgets.QDoubleSpinBox()
        throttle_spin.setRange(0.5, 10.0)
        throttle_spin.setSingleStep(0.5)
        throttle_spin.setValue(
            float(
                self._settings.value("throttleAnalysisHzDuringPlayback", 2, type=float)
            )
        )
        throttle_spin.setToolTip("Limit analysis update rate (Hz) during playback to maintain smoothness")
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

        # Confirmations section (P3.3)
        confirm_label = QtWidgets.QLabel("Confirmations")
        confirm_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addRow(confirm_label)
        confirm_apply_display_chk = QtWidgets.QCheckBox(
            "Ask before applying display mapping"
        )
        confirm_apply_display_chk.setChecked(
            self._settings.value("confirmApplyDisplayMapping", True, type=bool)
        )
        confirm_apply_display_chk.setToolTip("Show confirmation when applying display settings")
        confirm_apply_threshold_chk = QtWidgets.QCheckBox(
            "Ask before applying threshold (destructive)"
        )
        confirm_apply_threshold_chk.setChecked(
            self._settings.value("confirmApplyThreshold", True, type=bool)
        )
        confirm_apply_threshold_chk.setToolTip("Show confirmation before destructive threshold operations")
        confirm_clear_roi_chk = QtWidgets.QCheckBox(
            "Ask before clearing ROI"
        )
        confirm_clear_roi_chk.setChecked(
            self._settings.value("confirmClearROI", True, type=bool)
        )
        confirm_clear_roi_chk.setToolTip("Show confirmation before clearing ROI selection")
        confirm_delete_annotations_chk = QtWidgets.QCheckBox(
            "Ask before deleting annotations"
        )
        confirm_delete_annotations_chk.setChecked(
            self._settings.value("confirmDeleteAnnotations", True, type=bool)
        )
        confirm_delete_annotations_chk.setToolTip("Show confirmation before deleting annotation points")
        confirm_overwrite_file_chk = QtWidgets.QCheckBox(
            "Ask before overwriting files"
        )
        confirm_overwrite_file_chk.setChecked(
            self._settings.value("confirmOverwriteFile", True, type=bool)
        )
        confirm_overwrite_file_chk.setToolTip("Show confirmation before overwriting existing files on save")
        layout.addRow(confirm_apply_display_chk)
        layout.addRow(confirm_apply_threshold_chk)
        layout.addRow(confirm_clear_roi_chk)
        layout.addRow(confirm_delete_annotations_chk)
        layout.addRow(confirm_overwrite_file_chk)
        reset_confirms_btn = QtWidgets.QPushButton("Reset All Confirmations")
        reset_confirms_btn.setToolTip("Re-enable all confirmation dialogs")
        layout.addRow(reset_confirms_btn)

        # Histogram defaults
        hist_label = QtWidgets.QLabel("Histogram")
        hist_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addRow(hist_label)
        hist_bins_pref = QtWidgets.QSpinBox()
        hist_bins_pref.setRange(10, 512)
        hist_bins_pref.setValue(
            int(self._settings.value("histBinsDefault", 100, type=int))
        )
        layout.addRow("Bins (default)", hist_bins_pref)
        
        # Reset to defaults button
        reset_defaults_btn = QtWidgets.QPushButton("Reset All to Defaults")
        reset_defaults_btn.setToolTip("Reset all preferences to factory defaults")
        layout.addRow(reset_defaults_btn)
        
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
            self._settings.setValue(
                "applyAnnotationMetaOnLoad", apply_meta_chk.isChecked()
            )
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
            # Persist confirmation toggles (P3.3)
            self._settings.setValue(
                "confirmApplyDisplayMapping", confirm_apply_display_chk.isChecked()
            )
            self._settings.setValue(
                "confirmApplyThreshold", confirm_apply_threshold_chk.isChecked()
            )
            self._settings.setValue(
                "confirmClearROI", confirm_clear_roi_chk.isChecked()
            )
            self._settings.setValue(
                "confirmDeleteAnnotations", confirm_delete_annotations_chk.isChecked()
            )
            self._settings.setValue(
                "confirmOverwriteFile", confirm_overwrite_file_chk.isChecked()
            )
            # Update histogram bins default from preferences if provided
            try:
                hb = int(hist_bins_pref.value())
                self._settings.setValue("histBinsDefault", hb)
                if getattr(self, "hist_bins_spin", None) is not None:
                    self.hist_bins_spin.setValue(hb)
            except Exception:
                pass
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
        
        # Wire reset buttons
        def _reset_to_defaults() -> None:
            """Reset all preferences to factory defaults."""
            reply = QtWidgets.QMessageBox.question(
                dlg,
                "Reset to Defaults",
                "Reset all preferences to factory defaults?\n\nThis will restore:\n• Cache: 1024 MB\n• Recent files: 10\n• FPS: 10\n• All other settings to defaults\n\nThis action cannot be undone.",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                # Reset to hardcoded defaults
                cache_spin.setValue(1024)
                recent_spin.setValue(10)
                preset_combo.setCurrentText("Default")
                cmap_combo.setCurrentIndex(0)
                fps_spin.setValue(10)
                autosave_chk.setChecked(True)
                autoload_ann_chk.setChecked(True)
                confirm_clear_roi_chk.setChecked(True)
                confirm_delete_annotations_chk.setChecked(True)
                confirm_overwrite_file_chk.setChecked(True)
                apply_meta_chk.setChecked(False)
                encode_meta_chk.setChecked(False)
                pyramid_chk.setChecked(False)
                pyramid_levels_spin.setValue(3)
                block_spin.setValue(64)
                inflight_spin.setValue(2)
                throttle_spin.setValue(2.0)
                confirm_apply_display_chk.setChecked(True)
                confirm_apply_threshold_chk.setChecked(True)
                hist_bins_pref.setValue(100)
        
        try:
            reset_confirms_btn.clicked.connect(self._reset_confirmations)
            reset_defaults_btn.clicked.connect(_reset_to_defaults)
        except Exception:
            pass
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
        self._settings.setValue(
            "scaleBarIncludeInExport", self.scale_bar_include_in_export
        )
        self._refresh_image()
