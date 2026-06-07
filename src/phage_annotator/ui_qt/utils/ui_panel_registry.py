"""Dock registry and panel-factory helpers for UI setup."""

from __future__ import annotations

from typing import List, Optional, Tuple

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.panels.performance import PerformancePanel
from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.ui_qt.utils import ui_docks
from phage_annotator.ui_qt.utils.ui_setup_panels import (
    build_panel_policy_controls,
    refresh_panel_policy_controls,
)

class UiPanelRegistryMixin:
    """Panel registry, dock management, and policy controls."""

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
        """Document the build_panel_registry flow."""
        return ui_docks.build_panel_registry(self)

    def _apply_panel_defaults(self) -> None:
        """Document the apply_panel_defaults flow."""
        ui_docks.apply_panel_defaults(self)

    def _create_dock(
        self, name: str, title: str, widget: QtWidgets.QWidget
    ) -> QtWidgets.QDockWidget:
        """Document the create_dock flow."""
        return ui_docks.create_dock(self, name, title, widget)

    def _wire_dock_action(
        self,
        dock: QtWidgets.QDockWidget,
        action: QtWidgets.QAction,
        checkbox: Optional[QtWidgets.QCheckBox] = None,
    ) -> None:
        """Document the wire_dock_action flow."""
        ui_docks.wire_dock_action(self, dock, action, checkbox)

    def get_dock(self, panel_id: str) -> Optional[QtWidgets.QDockWidget]:
        """Document the get_dock flow."""
        return ui_docks.get_dock(self, panel_id)

    def open_panel(self, panel_id: str, *, reason: str = "user") -> Optional[QtWidgets.QDockWidget]:
        """Document the open_panel flow."""
        return ui_docks.open_panel(self, panel_id, reason=reason)

    def is_panel_auto_open_enabled(self, panel_id: str) -> bool:
        """Document the is_panel_auto_open_enabled flow."""
        return ui_docks.is_panel_auto_open_enabled(self, panel_id)

    def set_panel_auto_open_enabled(self, panel_id: str, enabled: bool) -> None:
        """Document the set_panel_auto_open_enabled flow."""
        ui_docks.set_panel_auto_open_enabled(self, panel_id, enabled)

    def is_panel_auto_open_enabled_for_trigger(self, panel_id: str, trigger: str) -> bool:
        """Document the is_panel_auto_open_enabled_for_trigger flow."""
        return ui_docks.is_panel_auto_open_enabled_for_trigger(self, panel_id, trigger)

    def set_panel_auto_open_enabled_for_trigger(
        self, panel_id: str, trigger: str, enabled: bool
    ) -> None:
        """Document the set_panel_auto_open_enabled_for_trigger flow."""
        ui_docks.set_panel_auto_open_enabled_for_trigger(self, panel_id, trigger, enabled)

    def is_panel_pinned(self, panel_id: str) -> bool:
        """Document the is_panel_pinned flow."""
        return ui_docks.is_panel_pinned(self, panel_id)

    def set_panel_pinned(self, panel_id: str, pinned: bool) -> None:
        """Document the set_panel_pinned flow."""
        ui_docks.set_panel_pinned(self, panel_id, pinned)

    def get_panel_opened_by(self, panel_id: str) -> str:
        """Document the get_panel_opened_by flow."""
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
