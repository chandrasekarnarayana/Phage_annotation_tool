"""Extracted method group 2 for UiAnnotationViewsMixin."""

from __future__ import annotations

import logging

from matplotlib.backends.qt_compat import QtCore, QtWidgets


logger = logging.getLogger(__name__)



class SourceProtocolsMixin:
    """Method group 2 extracted from UiAnnotationViewsMixin."""

    def _annotation_view_labels(self) -> dict[str, str]:
        """Return dynamic labels for annotation views."""
        labels = {
            "frame": "Frame",
            "mean": "Mean Projection",
            "support": "Modality 2",
            "std": "Std Projection",
        }
        manager = None
        if getattr(self, "controller", None) is not None:
            manager = getattr(self.controller.session_state, "modality_manager", None)
        if manager is not None:
            try:
                frame_modality = manager.get_modality(0)
                support_modality = manager.get_modality(1)
                if frame_modality is not None:
                    labels["frame"] = str(frame_modality.display_name or "Frame")
                if support_modality is not None:
                    labels["support"] = str(support_modality.display_name or "Modality 2")
            except Exception:
                logger.debug("Failed to read modality labels while refreshing annotation views", exc_info=True)
        panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
        for key, modality in panel_map.items():
            if str(key).startswith("modality_"):
                labels[str(key)] = str(getattr(modality, "display_name", key))
        for key in ("mean", "std"):
            cfg = dict(dict(getattr(self, "_lazy_builtin_views", {}) or {}).get(key, {}) or {})
            if cfg.get("name"):
                labels[key] = str(cfg.get("name"))
        support_cfg = dict(dict(getattr(self, "_lazy_builtin_views", {}) or {}).get("support", {}) or {})
        if support_cfg.get("name"):
            labels["support"] = str(support_cfg.get("name"))
        images = list(getattr(self, "images", []) or [])
        idx = int(getattr(self, "support_image_idx", 0))
        if 0 <= idx < len(images):
            labels["support"] = f"Modality 2 ({getattr(images[idx], 'name', f'Image {idx}')})"
        return labels
    def _refresh_annotation_target_constraints(self) -> None:
        """Enable target choices based on currently available visible views."""
        availability = self._available_annotation_views()
        combo = getattr(self, "annotate_target_combo", None)
        labels = self._annotation_view_labels()
        if combo is None:
            return
        current_target = str(getattr(self, "annotate_target", "frame")).strip().lower()
        combo.blockSignals(True)
        combo.clear()
        for key, label in self._lazy_annotation_rows():
            if not bool(availability.get(str(key), False)):
                continue
            context = (
                self.controller.ensure_annotation_context_for_panel(str(key), writable=True)
                if getattr(self, "controller", None) is not None
                and hasattr(self.controller, "ensure_annotation_context_for_panel")
                else {}
            )
            if not bool(context.get("writable", True)):
                continue
            mode = str(context.get("mode", "independent"))
            suffix = " [shared]" if mode == "shared_source" else ""
            combo.addItem(f"{labels.get(str(key), str(label))}{suffix}", str(key))
        combo.blockSignals(False)
        if combo.count() <= 0:
            combo.setEnabled(False)
            hint = getattr(self, "target_unavailable_hint_lbl", None)
            if hint is not None:
                hint.setText("No visible target view. Enable at least one view in Lazy Loading.")
                hint.setVisible(True)
            badge = getattr(self, "target_state_badge_lbl", None)
            if badge is not None:
                badge.setText("Write target: -")
            return
        combo.setEnabled(True)
        idx = combo.findData(current_target)
        if idx < 0:
            idx = 0
            self.annotate_target = str(combo.itemData(0))
        combo.blockSignals(True)
        combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        badge = getattr(self, "target_state_badge_lbl", None)
        if badge is not None:
            badge.setText(f"Write target: {combo.currentText()}")
        hint = getattr(self, "target_unavailable_hint_lbl", None)
        if hint is not None:
            hint.setVisible(False)
    def _on_annotation_panel_toggle(self, panel_key: str, checked: bool) -> None:
        """Toggle whether annotations are rendered on a specific visible panel."""
        key = str(panel_key or "").strip()
        if not key:
            return
        current_target = str(getattr(self, "annotate_target", "frame")).strip().lower()
        if key == current_target and not bool(checked):
            chk = dict(getattr(self, "_annotation_view_checkboxes", {}) or {}).get(key)
            if chk is not None:
                chk.blockSignals(True)
                chk.setChecked(True)
                chk.blockSignals(False)
            self._status_warning(
                "Target view must show points while annotating.",
                timeout_ms=3000,
                source="annotation_view.toggle",
            )
            return
        point_vis = dict(getattr(self, "_annotation_panel_visibility", {}) or {})
        point_vis[key] = bool(checked)
        self._annotation_panel_visibility = point_vis
        if hasattr(self, "_set_lazy_row_points_state"):
            self._set_lazy_row_points_state(key, bool(checked))
        if hasattr(self, "_refresh_annotation_view_controls"):
            self._refresh_annotation_view_controls()
        self._request_ui_refresh("ui-extra")
