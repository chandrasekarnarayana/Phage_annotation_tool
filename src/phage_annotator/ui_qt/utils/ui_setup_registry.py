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

    def _make_suggestion_explain_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_suggestion_explain_widget(self)

    def _make_status_details_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_status_details_widget(self)

    def _make_project_relink_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_project_relink_widget(self)

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

    def _make_modality_layers_widget(self) -> QtWidgets.QWidget:
        return ui_docks.make_modality_layers_widget(self)

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

        def _build_prepare_setup_section() -> QtWidgets.QWidget:
            section = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)

            compare_group = QtWidgets.QGroupBox("Reference and Comparison")
            compare_layout = QtWidgets.QVBoxLayout(compare_group)
            compare_layout.setContentsMargins(8, 8, 8, 8)
            compare_layout.setSpacing(6)
            compare_help = QtWidgets.QLabel(
                "Use the primary and reference views to compare evidence before annotation begins."
            )
            compare_help.setWordWrap(True)
            compare_help.setStyleSheet("color: #4b5563;")
            compare_layout.addWidget(compare_help)
            self.prepare_reference_summary_lbl = QtWidgets.QLabel("Reference views: -")
            self.prepare_reference_summary_lbl.setStyleSheet("color: #455a64;")
            compare_layout.addWidget(self.prepare_reference_summary_lbl)
            compare_buttons = QtWidgets.QHBoxLayout()
            compare_buttons.addWidget(
                _dock_button(
                    "Modality Layers",
                    "modality_layers",
                    "Open modality layers and A/B comparison controls.",
                )
            )
            compare_presets_btn = QtWidgets.QPushButton("Compare Presets A/B")
            compare_presets_btn.setToolTip("Run the configured modality preset comparison action.")
            compare_presets_btn.clicked.connect(
                lambda: getattr(self, "compare_layer_presets_act", None)
                and self.compare_layer_presets_act.trigger()
            )
            compare_buttons.addWidget(compare_presets_btn)
            compare_buttons.addStretch(1)
            compare_layout.addLayout(compare_buttons)
            layout.addWidget(compare_group)

            sync_group = QtWidgets.QGroupBox("Synchronized Navigation")
            sync_layout = QtWidgets.QVBoxLayout(sync_group)
            sync_layout.setContentsMargins(8, 8, 8, 8)
            sync_layout.setSpacing(6)
            sync_help = QtWidgets.QLabel(
                "Confirm the sync target before comparing modalities. Contrast, zoom/pan, playback, and ROI sharing follow the same centralized sync state."
            )
            sync_help.setWordWrap(True)
            sync_help.setStyleSheet("color: #4b5563;")
            sync_layout.addWidget(sync_help)
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
            sync_buttons.addWidget(
                _dock_button("Histogram", "hist", "Open histogram and brightness/contrast controls.")
            )
            sync_buttons.addStretch(1)
            sync_layout.addLayout(sync_buttons)
            layout.addWidget(sync_group)

            roi_group = QtWidgets.QGroupBox("ROI Setup")
            roi_layout = QtWidgets.QVBoxLayout(roi_group)
            roi_layout.setContentsMargins(8, 8, 8, 8)
            roi_layout.setSpacing(6)
            roi_help = QtWidgets.QLabel(
                "Define the working ROI before annotation. The active ROI is shared through the current sync group."
            )
            roi_help.setWordWrap(True)
            roi_help.setStyleSheet("color: #4b5563;")
            roi_layout.addWidget(roi_help)
            self.prepare_roi_summary_lbl = QtWidgets.QLabel("ROI: Full field")
            self.prepare_roi_summary_lbl.setStyleSheet("color: #455a64;")
            roi_layout.addWidget(self.prepare_roi_summary_lbl)
            roi_buttons = QtWidgets.QHBoxLayout()
            roi_buttons.addWidget(_dock_button("ROI Controls", "roi", "Open ROI controls for the current view."))
            roi_buttons.addWidget(_dock_button("ROI Manager", "roi_manager", "Open saved ROI management tools."))
            roi_buttons.addStretch(1)
            roi_layout.addLayout(roi_buttons)
            layout.addWidget(roi_group)

            return section

        def _trigger_action(action_name: str) -> None:
            action = getattr(self, action_name, None)
            if action is not None:
                action.trigger()

        def _build_review_qc_workflow_section() -> QtWidgets.QWidget:
            section = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)

            generate_group = QtWidgets.QGroupBox("Generate")
            generate_layout = QtWidgets.QVBoxLayout(generate_group)
            generate_layout.setContentsMargins(8, 8, 8, 8)
            generate_layout.setSpacing(6)
            generate_help = QtWidgets.QLabel(
                "Generate source-aware candidates, then review them against the current annotation truth."
            )
            generate_help.setWordWrap(True)
            generate_help.setStyleSheet("color: #4b5563;")
            generate_layout.addWidget(generate_help)
            self.review_qc_context_summary_lbl = QtWidgets.QLabel("Assist context: -")
            self.review_qc_context_summary_lbl.setStyleSheet("color: #455a64;")
            generate_layout.addWidget(self.review_qc_context_summary_lbl)
            generate_layout.addWidget(self._build_assist_panel())
            layout.addWidget(generate_group)

            merge_group = QtWidgets.QGroupBox("Merge Policy")
            merge_layout = QtWidgets.QVBoxLayout(merge_group)
            merge_layout.setContentsMargins(8, 8, 8, 8)
            merge_layout.setSpacing(6)
            merge_help = QtWidgets.QLabel(
                "Committed annotations remain the source of truth. Suggestions are reviewed explicitly and stale batches require acknowledgement before bulk acceptance."
            )
            merge_help.setWordWrap(True)
            merge_help.setStyleSheet("color: #4b5563;")
            merge_layout.addWidget(merge_help)
            merge_points = QtWidgets.QLabel(
                "Manual and imported points are preserved. Accepted suggestions become committed annotations only through the review/command path."
            )
            merge_points.setWordWrap(True)
            merge_points.setStyleSheet("color: #455a64;")
            merge_layout.addWidget(merge_points)
            layout.addWidget(merge_group)

            summary_group = QtWidgets.QGroupBox("Summary")
            summary_layout = QtWidgets.QVBoxLayout(summary_group)
            summary_layout.setContentsMargins(8, 8, 8, 8)
            summary_layout.setSpacing(6)
            self.review_qc_summary_lbl = QtWidgets.QLabel("Current truth and review load: -")
            self.review_qc_summary_lbl.setWordWrap(True)
            self.review_qc_summary_lbl.setStyleSheet("color: #455a64;")
            self.review_qc_freshness_lbl = QtWidgets.QLabel("Suggestion freshness: -")
            self.review_qc_freshness_lbl.setStyleSheet("color: #455a64;")
            summary_layout.addWidget(self.review_qc_summary_lbl)
            summary_layout.addWidget(self.review_qc_freshness_lbl)
            layout.addWidget(summary_group)

            review_group = QtWidgets.QGroupBox("Review Actions")
            review_layout = QtWidgets.QGridLayout(review_group)
            review_layout.setContentsMargins(8, 8, 8, 8)
            review_layout.setHorizontalSpacing(8)
            review_layout.setVerticalSpacing(6)
            review_layout.addWidget(
                _dock_button("Review Queue", "review_queue", "Open the review queue."),
                0,
                0,
            )
            review_layout.addWidget(
                _dock_button("Rationale", "suggestion_explain", "Open suggestion rationale."),
                0,
                1,
            )
            next_btn = QtWidgets.QPushButton("Next Uncertain")
            next_btn.clicked.connect(self._next_uncertain_suggestion)
            review_layout.addWidget(next_btn, 0, 2)
            accept_visible_btn = QtWidgets.QPushButton("Accept Visible")
            accept_visible_btn.clicked.connect(lambda: _trigger_action("accept_visible_suggestions_act"))
            review_layout.addWidget(accept_visible_btn, 1, 0)
            accept_green_btn = QtWidgets.QPushButton("Accept High-Confidence")
            accept_green_btn.clicked.connect(lambda: _trigger_action("accept_green_suggestions_act"))
            review_layout.addWidget(accept_green_btn, 1, 1)
            accept_roi_btn = QtWidgets.QPushButton("Accept In ROI")
            accept_roi_btn.clicked.connect(lambda: _trigger_action("accept_suggestions_in_roi_act"))
            review_layout.addWidget(accept_roi_btn, 1, 2)
            reject_visible_btn = QtWidgets.QPushButton("Reject Visible")
            reject_visible_btn.clicked.connect(lambda: _trigger_action("reject_visible_suggestions_act"))
            review_layout.addWidget(reject_visible_btn, 2, 0)
            layout.addWidget(review_group)

            qc_group = QtWidgets.QGroupBox("QC")
            qc_layout = QtWidgets.QVBoxLayout(qc_group)
            qc_layout.setContentsMargins(8, 8, 8, 8)
            qc_layout.setSpacing(6)
            self.review_qc_qc_summary_lbl = QtWidgets.QLabel("QC summary: -")
            self.review_qc_qc_summary_lbl.setStyleSheet("color: #455a64;")
            qc_layout.addWidget(self.review_qc_qc_summary_lbl)
            qc_buttons = QtWidgets.QHBoxLayout()
            run_qc_btn = QtWidgets.QPushButton("Run QC Validation")
            run_qc_btn.clicked.connect(self._trigger_qc_validation)
            qc_buttons.addWidget(run_qc_btn)
            qc_buttons.addWidget(_dock_button("QC Issues", "qc_issues", "Open QC issues."))
            qc_buttons.addWidget(_dock_button("Histogram", "hist", "Open histogram for QC inspection."))
            qc_buttons.addStretch(1)
            qc_layout.addLayout(qc_buttons)
            qc_layout.addWidget(self._build_qc_panel())
            layout.addWidget(qc_group)

            return section

        def _build_advanced_workflow_section() -> QtWidgets.QWidget:
            section = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)

            summary_group = QtWidgets.QGroupBox("Summary")
            summary_layout = QtWidgets.QVBoxLayout(summary_group)
            summary_layout.setContentsMargins(8, 8, 8, 8)
            summary_layout.setSpacing(6)
            self.advanced_pipeline_summary_lbl = QtWidgets.QLabel("Power-tool pipeline: -")
            self.advanced_pipeline_summary_lbl.setWordWrap(True)
            self.advanced_pipeline_summary_lbl.setStyleSheet("color: #455a64;")
            self.advanced_analysis_summary_lbl = QtWidgets.QLabel("Analysis readiness: -")
            self.advanced_analysis_summary_lbl.setWordWrap(True)
            self.advanced_analysis_summary_lbl.setStyleSheet("color: #455a64;")
            self.advanced_plugins_summary_lbl = QtWidgets.QLabel("Plugin and SMLM state: -")
            self.advanced_plugins_summary_lbl.setWordWrap(True)
            self.advanced_plugins_summary_lbl.setStyleSheet("color: #455a64;")
            summary_layout.addWidget(self.advanced_pipeline_summary_lbl)
            summary_layout.addWidget(self.advanced_analysis_summary_lbl)
            summary_layout.addWidget(self.advanced_plugins_summary_lbl)
            layout.addWidget(summary_group)

            segmentation_group = QtWidgets.QGroupBox("Segmentation and Candidate Generation")
            segmentation_layout = QtWidgets.QVBoxLayout(segmentation_group)
            segmentation_layout.setContentsMargins(8, 8, 8, 8)
            segmentation_layout.setSpacing(6)
            segmentation_help = QtWidgets.QLabel(
                "Use thresholding and particle-style extraction as power workflows. Any accepted detections should still re-enter the same annotation and review truth path."
            )
            segmentation_help.setWordWrap(True)
            segmentation_help.setStyleSheet("color: #4b5563;")
            segmentation_layout.addWidget(segmentation_help)
            segmentation_buttons = QtWidgets.QHBoxLayout()
            segmentation_buttons.addWidget(
                _dock_button("Threshold", "threshold", "Open threshold and mask controls.")
            )
            segmentation_buttons.addWidget(
                _dock_button("Particles", "particles", "Open particle analysis results.")
            )
            segmentation_buttons.addStretch(1)
            segmentation_layout.addLayout(segmentation_buttons)
            segmentation_layout.addWidget(self._build_threshold_panel())
            layout.addWidget(segmentation_group)

            quant_group = QtWidgets.QGroupBox("Quantitative Analysis")
            quant_layout = QtWidgets.QVBoxLayout(quant_group)
            quant_layout.setContentsMargins(8, 8, 8, 8)
            quant_layout.setSpacing(6)
            quant_help = QtWidgets.QLabel(
                "Use ROI-driven measurements, density, orthoviews, and results tables when the task shifts from marking objects to quantifying them."
            )
            quant_help.setWordWrap(True)
            quant_help.setStyleSheet("color: #4b5563;")
            quant_layout.addWidget(quant_help)
            quant_buttons = QtWidgets.QHBoxLayout()
            quant_buttons.addWidget(_dock_button("Results", "results", "Open the results table."))
            quant_buttons.addWidget(_dock_button("Density", "density", "Open density analysis."))
            quant_buttons.addWidget(_dock_button("Histogram", "hist", "Open histogram inspection."))
            quant_buttons.addStretch(1)
            quant_layout.addLayout(quant_buttons)
            quant_layout.addWidget(self._build_analyze_panel())
            layout.addWidget(quant_group)

            plugin_group = QtWidgets.QGroupBox("SMLM, Plugins, and Automation")
            plugin_layout = QtWidgets.QVBoxLayout(plugin_group)
            plugin_layout.setContentsMargins(8, 8, 8, 8)
            plugin_layout.setSpacing(6)
            plugin_help = QtWidgets.QLabel(
                "Run ThunderSTORM, Deep-STORM, plugin bridges, and repeatable batch workflows here. These tools should augment the same scientific review pipeline rather than create parallel truth stores."
            )
            plugin_help.setWordWrap(True)
            plugin_help.setStyleSheet("color: #4b5563;")
            plugin_layout.addWidget(plugin_help)
            plugin_buttons = QtWidgets.QHBoxLayout()
            plugin_buttons.addWidget(_dock_button("SMLM", "smlm", "Open SMLM analysis controls."))
            plugin_buttons.addWidget(
                _dock_button("Analysis", "advanced_analysis", "Open advanced analysis helpers.")
            )
            plugin_buttons.addWidget(_dock_button("Logs", "logs", "Open logs and plugin diagnostics."))
            plugin_buttons.addStretch(1)
            plugin_layout.addLayout(plugin_buttons)
            plugin_layout.addWidget(self._build_automate_panel())
            layout.addWidget(plugin_group)

            return section

        if getattr(self, "primary_combo", None) is not None:
            self.primary_combo.setVisible(True)
        if getattr(self, "support_combo", None) is not None:
            self.support_combo.setVisible(True)

        prepare_content = _stack_sections(
            self.explore_panel,
            _build_prepare_setup_section(),
            display_group,
        )
        if hasattr(self, "_update_sync_keys_hint"):
            self._update_sync_keys_hint()
        if hasattr(self, "_refresh_prepare_setup_summary"):
            self._refresh_prepare_setup_summary()

        pages.append(
            (
                "Prepare",
                QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon,
                _page_shell(
                    "Prepare",
                    "Load datasets, choose modality views, define ROI, and establish synchronized comparison before annotation begins.",
                    prepare_content,
                ),
            )
        )
        pages.append(
            (
                "Annotate",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView,
                _page_shell(
                    "Annotation",
                    "Add, edit, label, and target annotations. Use the right sidebar to inspect the annotation table and contextual review panels.",
                    self._build_annotate_panel(),
                    quick_buttons=[
                        _dock_button("Annotation Table", "annotations", "Open the annotation table dock."),
                        _dock_button("Review Queue", "review_queue", "Open the review queue dock."),
                    ],
                ),
            )
        )
        pages.append(
            (
                "Review / QC",
                QtWidgets.QStyle.StandardPixmap.SP_DialogApplyButton,
                _page_shell(
                    "Review / QC",
                    "Generate source-aware suggestions, review uncertain detections, inspect rationale, and validate quality-control issues in one workflow.",
                    _build_review_qc_workflow_section(),
                    quick_buttons=[
                        _dock_button("Review Queue", "review_queue", "Open the queue of uncertain suggestions."),
                        _dock_button("Rationale", "suggestion_explain", "Open suggestion rationale for the focused prediction."),
                        _dock_button("QC Issues", "qc_issues", "Open the QC issues dock."),
                        _dock_button("Histogram", "hist", "Open the histogram for review-time inspection."),
                    ],
                ),
            )
        )
        pages.append(
            (
                "Advanced",
                QtWidgets.QStyle.StandardPixmap.SP_DriveHDIcon,
                _page_shell(
                    "Advanced",
                    "Use segmentation, quantitative analysis, SMLM, and automation without disturbing the core annotation and review workspace. Advanced outputs should still land in the same scientific truth and review pipeline.",
                    _build_advanced_workflow_section(),
                    quick_buttons=[
                        _dock_button("Threshold", "threshold", "Open threshold controls."),
                        _dock_button("Particles", "particles", "Open particle analysis results."),
                        _dock_button("Results", "results", "Open the results table."),
                        _dock_button("Density", "density", "Open the density analysis dock."),
                        _dock_button("SMLM", "smlm", "Open SMLM analysis controls."),
                        _dock_button("Analysis", "advanced_analysis", "Open advanced analysis tools."),
                    ],
                ),
            )
        )
        pages.append(
            (
                "Export / Settings",
                QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton,
                _page_shell(
                    "Export / Settings",
                    "Finalize outputs, save projects, and configure application behavior, performance, and panel policy.",
                    _stack_sections(self._build_export_panel(), self._build_settings_panel()),
                    quick_buttons=[
                        _dock_button("Performance", "performance", "Open performance diagnostics."),
                        _dock_button("Metadata", "metadata", "Open metadata controls and batch metadata tools."),
                        _dock_button("Status Details", "status_details", "Open expanded operational status."),
                    ],
                ),
            )
        )
        if hasattr(self, "_refresh_review_qc_page_summary"):
            self._refresh_review_qc_page_summary()
        if hasattr(self, "_refresh_advanced_page_summary"):
            self._refresh_advanced_page_summary()
        return pages
