"""Dock registry and panel-factory helpers for UI setup."""

from __future__ import annotations

from typing import List, Optional, Tuple

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.panels.performance import PerformancePanel
from phage_annotator.ui_qt.panels.registry_legacy import PanelSpec
from phage_annotator.ui_qt.utils import ui_docks
from phage_annotator.ui_qt.utils.ui_setup_panels import (
    build_panel_policy_controls,
    refresh_panel_policy_controls,
)


class UiSetupRegistryMixin:
    """Mixin for dock registry wiring and dock factory wrappers."""

    def _refresh_advanced_settings_panel(self) -> None:
        """Mirror current calibration state into the right-side expert panel."""
        panel = getattr(self, "advanced_settings_panel", None)
        if panel is None:
            return
        image = getattr(self, "primary_image", None)
        report = dict(getattr(self.controller.session_state, "project_relink_report", {}) or {})
        unresolved = list(report.get("unresolved", []) or [])
        relinked = list(report.get("relinked", []) or [])
        loaded = int(report.get("loaded_count", 0))
        partial = bool(report.get("partial_load", False))
        skipped = int(report.get("skipped_count", len(report.get("missing", []) or [])))
        relink_summary = (
            f"Loaded {loaded} image(s). "
            f"{'Partial load active. ' if partial else ''}"
            f"Relinked: {len(relinked)} | Unresolved: {len(unresolved)} | Skipped: {skipped}"
            if report
            else "No relink activity."
        )
        if image is None:
            panel.set_state(
                image_name="-",
                effective_pixel_size_um=None,
                pixel_source="-",
                default_pixel_size_um=float(getattr(self, "pixel_size_um_per_px", 0.069) or 0.069),
                axis_mode=str(getattr(getattr(self, "axis_mode_combo", None), "currentText", lambda: "auto")() or "auto"),
                relink_summary=relink_summary,
                relink_retry_enabled=bool(unresolved),
            )
            return
        calibration = self._get_calibration_state(int(image.id))
        panel.set_state(
            image_name=str(getattr(image, "name", "") or getattr(image, "path", "") or "-"),
            effective_pixel_size_um=getattr(calibration, "pixel_size_um_per_px", None),
            pixel_source=str(getattr(calibration, "source", "unknown") or "unknown"),
            default_pixel_size_um=float(getattr(self, "pixel_size_um_per_px", 0.069) or 0.069),
            axis_mode=str(getattr(image, "interpret_3d_as", None) or getattr(getattr(self, "axis_mode_combo", None), "currentText", lambda: "auto")() or "auto"),
            relink_summary=relink_summary,
            relink_retry_enabled=bool(unresolved),
        )

    def _refresh_review_qc_page_summary(self) -> None:
        """Refresh the workflow summary labels shown on the Review / QC page."""
        context_lbl = getattr(self, "review_qc_context_summary_lbl", None)
        if context_lbl is not None:
            context_txt = "-"
            if hasattr(self, "_effective_assist_context_line"):
                try:
                    ranked = (
                        list(self._visible_suggestions_uncertain_first())
                        if hasattr(self, "_visible_suggestions_uncertain_first")
                        else []
                    )
                    context_txt = str(self._effective_assist_context_line(ranked))
                except Exception:
                    context_txt = "-"
            context_lbl.setText(f"Assist context: {context_txt}")

        summary_lbl = getattr(self, "review_qc_summary_lbl", None)
        if summary_lbl is not None:
            annotations = []
            if hasattr(self, "annotations_for_panel") and getattr(self, "annotate_target", None) is not None:
                try:
                    annotations = list(self.annotations_for_panel(str(self.annotate_target)))
                except Exception:
                    annotations = []
            elif getattr(self, "primary_image", None) is not None:
                annotations = list(getattr(self, "annotations", {}).get(int(self.primary_image.id), []))
            visible = list(self._visible_suggestions()) if hasattr(self, "_visible_suggestions") else []
            uncertain = (
                list(self._visible_suggestions_uncertain_first())
                if hasattr(self, "_visible_suggestions_uncertain_first")
                else []
            )
            metrics = dict(getattr(self.controller.session_state, "suggestion_metrics", {}) or {})
            accepted = int(metrics.get("accepted", 0))
            rejected = int(metrics.get("rejected", 0))
            generation = dict(getattr(self.controller.session_state, "last_suggestion_generation_summary", {}) or {})
            gen_bits = []
            if generation:
                gen_bits = [
                    f"{int(generation.get('new_count', 0))} new",
                    f"{int(generation.get('near_count', 0))} near existing",
                    f"{int(generation.get('conflict_count', 0))} conflict",
                    f"{int(generation.get('duplicate_count', 0))} duplicate skipped",
                ]
            summary_lbl.setText(
                "Current truth and review load: "
                f"{len(annotations)} committed points | "
                f"{len(visible)} visible suggestions | "
                f"{len(uncertain)} uncertain | "
                f"{accepted} accepted | {rejected} rejected"
                + (f" | Last generation: {', '.join(gen_bits)}" if gen_bits else "")
            )

        freshness_lbl = getattr(self, "review_qc_freshness_lbl", None)
        if freshness_lbl is not None:
            freshness_txt = "Suggestion freshness: n/a"
            if getattr(self, "primary_image", None) is not None and hasattr(self, "_suggestion_freshness_state"):
                try:
                    freshness = self._suggestion_freshness_state(
                        int(self.primary_image.id),
                        list(self._visible_suggestions()) if hasattr(self, "_visible_suggestions") else [],
                    )
                    if freshness.get("is_stale", False):
                        freshness_txt = (
                            f"Suggestion freshness: Stale ({freshness.get('age_text', 'n/a')})"
                        )
                    else:
                        freshness_txt = "Suggestion freshness: Fresh"
                except Exception:
                    pass
            freshness_lbl.setText(freshness_txt)

        qc_lbl = getattr(self, "review_qc_qc_summary_lbl", None)
        if qc_lbl is not None:
            issue_count = 0
            if getattr(self, "qc_state", None) is not None:
                try:
                    issue_count = int(len(getattr(self.qc_state, "issues", []) or []))
                except Exception:
                    issue_count = 0
            qc_lbl.setText(f"QC summary: {issue_count} issue(s) currently recorded")

    def _refresh_advanced_page_summary(self) -> None:
        """Refresh the summary labels shown on the Advanced page."""
        pipeline_lbl = getattr(self, "advanced_pipeline_summary_lbl", None)
        if pipeline_lbl is not None:
            annotations = []
            if hasattr(self, "annotations_for_panel") and getattr(self, "annotate_target", None) is not None:
                try:
                    annotations = list(self.annotations_for_panel(str(self.annotate_target)))
                except Exception:
                    annotations = []
            elif getattr(self, "primary_image", None) is not None:
                annotations = list(getattr(self, "annotations", {}).get(int(self.primary_image.id), []))
            pipeline_lbl.setText(
                "Power-tool pipeline: "
                f"{len(annotations)} committed annotations remain the operational truth; "
                "advanced detections and measurements should flow back through the same review/export path."
            )

        analysis_lbl = getattr(self, "advanced_analysis_summary_lbl", None)
        if analysis_lbl is not None:
            roi_active = bool(getattr(self, "roi_rect", None))
            particle_count = len(list(getattr(self, "_particles_results", []) or []))
            results_rows = 0
            results_table = getattr(self, "results_table", None)
            if results_table is not None:
                try:
                    results_rows = int(results_table.rowCount())
                except Exception:
                    results_rows = 0
            analysis_lbl.setText(
                "Analysis readiness: "
                f"{'ROI active' if roi_active else 'Full field'} | "
                f"{particle_count} particle result(s) | "
                f"{results_rows} result row(s)"
            )

        plugins_lbl = getattr(self, "advanced_plugins_summary_lbl", None)
        if plugins_lbl is not None:
            smlm_count = len(list(getattr(self, "_smlm_results", []) or []))
            run_history = list(getattr(self, "_smlm_run_history", []) or [])
            plugins_lbl.setText(
                "Plugin and SMLM state: "
                f"{smlm_count} localization(s) currently loaded | "
                f"{len(run_history)} recorded SMLM run(s)"
            )

    def _build_panel_registry(self) -> List[PanelSpec]:
        return ui_docks.build_panel_registry(self)

    def _apply_panel_defaults(self) -> None:
        ui_docks.apply_panel_defaults(self)

    def _create_dock(
        self, name: str, title: str, widget: QtWidgets.QWidget
    ) -> QtWidgets.QDockWidget:
        return ui_docks.create_dock(self, name, title, widget)

    def _wire_dock_action(
        self,
        dock: QtWidgets.QDockWidget,
        action: QtWidgets.QAction,
        checkbox: Optional[QtWidgets.QCheckBox] = None,
    ) -> None:
        ui_docks.wire_dock_action(self, dock, action, checkbox)

    def get_dock(self, panel_id: str) -> Optional[QtWidgets.QDockWidget]:
        return ui_docks.get_dock(self, panel_id)

    def open_panel(self, panel_id: str, *, reason: str = "user") -> Optional[QtWidgets.QDockWidget]:
        return ui_docks.open_panel(self, panel_id, reason=reason)

    def is_panel_auto_open_enabled(self, panel_id: str) -> bool:
        return ui_docks.is_panel_auto_open_enabled(self, panel_id)

    def set_panel_auto_open_enabled(self, panel_id: str, enabled: bool) -> None:
        ui_docks.set_panel_auto_open_enabled(self, panel_id, enabled)

    def is_panel_auto_open_enabled_for_trigger(self, panel_id: str, trigger: str) -> bool:
        return ui_docks.is_panel_auto_open_enabled_for_trigger(self, panel_id, trigger)

    def set_panel_auto_open_enabled_for_trigger(
        self, panel_id: str, trigger: str, enabled: bool
    ) -> None:
        ui_docks.set_panel_auto_open_enabled_for_trigger(self, panel_id, trigger, enabled)

    def is_panel_pinned(self, panel_id: str) -> bool:
        return ui_docks.is_panel_pinned(self, panel_id)

    def set_panel_pinned(self, panel_id: str, pinned: bool) -> None:
        ui_docks.set_panel_pinned(self, panel_id, pinned)

    def get_panel_opened_by(self, panel_id: str) -> str:
        return ui_docks.get_panel_opened_by(self, panel_id)

    def _init_panel_policy_controls(self) -> None:
        """Build per-panel auto-open and pin controls in Preferences."""
        build_panel_policy_controls(self)

    def _refresh_panel_policy_controls(self) -> None:
        """Sync panel policy checkboxes with persisted/current policy state."""
        refresh_panel_policy_controls(self)

    def _reset_panel_auto_open_defaults(self) -> None:
        """Reset all panel auto-open toggles to enabled defaults."""
        for spec in list(getattr(self, "panel_specs", []) or []):
            self.set_panel_auto_open_enabled(str(spec.id), True)
        self._refresh_panel_policy_controls()

    def _make_sidebar_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_sidebar_widget(self)

    def _make_annotations_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_annotations_widget(self)

    def _make_review_queue_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_review_queue_widget(self)

    def _make_advanced_settings_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_advanced_settings_widget(self)

    def _make_status_details_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_status_details_widget(self)

    def _make_advanced_analysis_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_advanced_analysis_widget(self)

    def _make_roi_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_roi_widget(self)

    def _make_roi_manager_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_roi_manager_widget(self)

    def _make_results_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_results_widget(self)

    def _make_recorder_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_recorder_widget(self)

    def _make_hist_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_hist_widget(self)

    def _make_profile_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_profile_widget(self)

    def _make_orthoview_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_orthoview_widget(self)

    def _make_smlm_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_smlm_widget(self)

    def _make_threshold_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_threshold_widget(self)

    def _make_particles_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_particles_widget(self)

    def _make_density_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_density_widget(self)

    def _make_channel_controls_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_channel_controls_widget(self)

    def _make_logs_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_logs_widget(self)

    def _make_metadata_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_metadata_widget(self)

    def _make_performance_widget(self) -> QtWidgets.QWidget:
        panel = PerformancePanel(parent=self)
        panel.set_cache(self.proj_cache)
        panel.set_ring_buffer(self._playback_ring)
        self.performance_panel = panel
        return panel

    def _make_qc_issues_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_qc_issues_widget(self)

    def _build_sidebar_pages(
        self, display_group: QtWidgets.QGroupBox
    ) -> List[Tuple[str, QtWidgets.QStyle.StandardPixmap, QtWidgets.QWidget]]:
        pages: List[Tuple[str, QtWidgets.QStyle.StandardPixmap, QtWidgets.QWidget]] = []

        def _make_scroll(widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            scroll.setWidget(widget)
            return scroll

        def _dock_button(text: str, panel_id: str, tooltip: str) -> QtWidgets.QPushButton:
            btn = QtWidgets.QPushButton(text)
            btn.setToolTip(str(tooltip))
            btn.clicked.connect(lambda: self.open_panel(str(panel_id), reason="sidebar_button"))
            return btn

        def _page_shell(
            title: str,
            description: str,
            content: QtWidgets.QWidget,
            *,
            quick_buttons: Optional[List[QtWidgets.QPushButton]] = None,
        ) -> QtWidgets.QWidget:
            page = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(page)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)

            title_lbl = QtWidgets.QLabel(str(title))
            title_lbl.setStyleSheet("font-weight: 700; font-size: 13px;")
            layout.addWidget(title_lbl)

            if str(description or "").strip():
                desc_lbl = QtWidgets.QLabel(str(description))
                desc_lbl.setWordWrap(True)
                desc_lbl.setStyleSheet("color: #4b5563;")
                layout.addWidget(desc_lbl)

            if quick_buttons:
                quick_row = QtWidgets.QHBoxLayout()
                quick_row.setSpacing(6)
                for button in quick_buttons:
                    quick_row.addWidget(button)
                quick_row.addStretch(1)
                layout.addLayout(quick_row)

            layout.addWidget(content)
            layout.addStretch(1)
            return _make_scroll(page)

        def _stack_sections(*sections: QtWidgets.QWidget) -> QtWidgets.QWidget:
            container = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)
            for section in sections:
                layout.addWidget(section)
            layout.addStretch(1)
            return container

        def _quick_group(
            title: str,
            description: str,
            buttons: List[QtWidgets.QPushButton],
        ) -> QtWidgets.QWidget:
            group = QtWidgets.QGroupBox(str(title))
            layout = QtWidgets.QVBoxLayout(group)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(6)
            desc = QtWidgets.QLabel(str(description))
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #4b5563;")
            layout.addWidget(desc)
            for button in buttons:
                layout.addWidget(button)
            return group

        def _build_lazy_loading_section() -> QtWidgets.QWidget:
            section = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)

            compare_group = QtWidgets.QGroupBox("Reference Views")
            compare_layout = QtWidgets.QVBoxLayout(compare_group)
            compare_layout.setContentsMargins(8, 8, 8, 8)
            compare_layout.setSpacing(6)
            self.prepare_reference_summary_lbl = QtWidgets.QLabel("Reference views: -")
            self.prepare_reference_summary_lbl.setStyleSheet("color: #455a64;")
            compare_layout.addWidget(self.prepare_reference_summary_lbl)
            layout.addWidget(compare_group)

            sync_group = QtWidgets.QGroupBox("Synchronized Navigation")
            sync_layout = QtWidgets.QVBoxLayout(sync_group)
            sync_layout.setContentsMargins(8, 8, 8, 8)
            sync_layout.setSpacing(6)
            self.prepare_sync_target_lbl = QtWidgets.QLabel("Sync target: -")
            self.prepare_sync_contract_lbl = QtWidgets.QLabel("Sync contract: -")
            self.prepare_sync_panels_lbl = QtWidgets.QLabel("Sync panels: -")
            for label in (
                self.prepare_sync_target_lbl,
                self.prepare_sync_contract_lbl,
                self.prepare_sync_panels_lbl,
            ):
                label.setStyleSheet("color: #455a64;")
                sync_layout.addWidget(label)
            sync_buttons = QtWidgets.QHBoxLayout()
            focus_sync_btn = QtWidgets.QPushButton("Focus Sync Controls")
            focus_sync_btn.setToolTip("Move focus to the bottom playback/sync control strip.")
            focus_sync_btn.clicked.connect(self._focus_playback_controls)
            sync_buttons.addWidget(focus_sync_btn)
            sync_buttons.addStretch(1)
            sync_layout.addLayout(sync_buttons)
            layout.addWidget(sync_group)

            return section

        def _build_roi_page_section() -> QtWidgets.QWidget:
            section = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)

            roi_group = QtWidgets.QGroupBox("ROI")
            roi_layout = QtWidgets.QVBoxLayout(roi_group)
            roi_layout.setContentsMargins(8, 8, 8, 8)
            roi_layout.setSpacing(6)
            self.prepare_roi_summary_lbl = QtWidgets.QLabel("ROI: Full field")
            self.prepare_roi_summary_lbl.setStyleSheet("color: #455a64;")
            roi_layout.addWidget(self.prepare_roi_summary_lbl)
            if getattr(self, "_roi_controls_layout", None) is not None:
                roi_layout.addLayout(self._roi_controls_layout)
            roi_buttons = QtWidgets.QHBoxLayout()
            roi_buttons.addWidget(
                _dock_button("ROI Manager", "roi_manager", "Open saved ROI management tools.")
            )
            clear_roi_btn = QtWidgets.QPushButton("Clear ROI")
            clear_roi_btn.setToolTip("Remove the active ROI and return to full field.")
            clear_roi_btn.clicked.connect(self._clear_roi)
            roi_buttons.addWidget(clear_roi_btn)
            roi_buttons.addStretch(1)
            roi_layout.addLayout(roi_buttons)
            layout.addWidget(roi_group)
            layout.addStretch(1)
            return section

        def _trigger_action(action_name: str) -> None:
            action = getattr(self, action_name, None)
            if action is not None:
                action.trigger()

        if getattr(self, "primary_combo", None) is not None:
            self.primary_combo.setVisible(True)
        if getattr(self, "support_combo", None) is not None:
            self.support_combo.setVisible(True)

        lazy_loading_content = _stack_sections(
            self.explore_panel,
            _build_lazy_loading_section(),
        )
        if hasattr(self, "_update_sync_keys_hint"):
            self._update_sync_keys_hint()
        if hasattr(self, "_refresh_prepare_setup_summary"):
            self._refresh_prepare_setup_summary()

        pages.append(
            (
                "Lazy Loading",
                QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon,
                _page_shell(
                    "Lazy Loading",
                    "",
                    lazy_loading_content,
                ),
            )
        )
        pages.append(
            (
                "Annotation",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView,
                _page_shell(
                    "Annotation",
                    "",
                    self._build_annotate_panel(),
                    quick_buttons=[
                        _dock_button("Annotation Table", "annotations", "Open the annotation table dock."),
                        _dock_button("Assist", "review_queue", "Open assist review and decision tools."),
                        _dock_button("QC", "qc_issues", "Open quality-control issues."),
                    ],
                ),
            )
        )
        pages.append(
            (
                "ROI",
                QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton,
                _page_shell(
                    "ROI",
                    "",
                    _build_roi_page_section(),
                    quick_buttons=[
                        _dock_button("ROI Manager", "roi_manager", "Open the ROI manager."),
                    ],
                ),
            )
        )
        pages.append(
            (
                "Contrast",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
                _page_shell(
                    "Contrast",
                    "",
                    display_group,
                    quick_buttons=[
                        _dock_button("Profile", "profile", "Open the line profile."),
                    ],
                ),
            )
        )
        return pages
