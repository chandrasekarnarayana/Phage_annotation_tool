"""Post-render GUI control synchronization helpers."""

from __future__ import annotations

from phage_annotator.ui_qt.rendering.lut_manager import LUTS


def sync_render_controls(owner: object, primary_mapping: object, level: int) -> None:
    """Synchronize LUT, gamma, log, projection, and render-level controls."""
    _sync_lut_controls(owner, primary_mapping)
    _sync_gamma_controls(owner, primary_mapping)
    _sync_log_control(owner, primary_mapping)
    _sync_projection_control(owner)
    if owner.render_level_label is not None:
        owner.render_level_label.setText(f"Render: L{level}")


def _sync_lut_controls(owner: object, primary_mapping: object) -> None:
    """Update LUT combo and inversion checkbox from the active mapping."""
    if owner.lut_combo is not None and 0 <= primary_mapping.lut < owner.lut_combo.count():
        owner.lut_combo.blockSignals(True)
        owner.lut_combo.setCurrentIndex(primary_mapping.lut)
        owner.lut_combo.blockSignals(False)
    if owner.lut_invert_chk is None:
        return
    invert_supported = True
    if 0 <= primary_mapping.lut < len(LUTS):
        invert_supported = LUTS[primary_mapping.lut].invert_supported
    owner.lut_invert_chk.blockSignals(True)
    owner.lut_invert_chk.setChecked(primary_mapping.invert)
    owner.lut_invert_chk.setEnabled(invert_supported)
    owner.lut_invert_chk.blockSignals(False)


def _sync_gamma_controls(owner: object, primary_mapping: object) -> None:
    """Update gamma slider and label without emitting feedback."""
    if owner.gamma_slider is None or owner.gamma_label is None:
        return
    gamma_val = max(0.2, min(5.0, float(primary_mapping.gamma)))
    owner.gamma_slider.blockSignals(True)
    owner.gamma_slider.setValue(int(round(gamma_val * 10)))
    owner.gamma_slider.blockSignals(False)
    owner.gamma_label.setText(f"{gamma_val:.2f}")


def _sync_log_control(owner: object, primary_mapping: object) -> None:
    """Update the log-display checkbox without emitting feedback."""
    if owner.log_chk is None:
        return
    owner.log_chk.blockSignals(True)
    owner.log_chk.setChecked(primary_mapping.mode == "log")
    owner.log_chk.blockSignals(False)


def _sync_projection_control(owner: object) -> None:
    """Refresh the modern projection selector or legacy axis combo."""
    if getattr(owner, "projection_selector", None) is not None:
        manager = getattr(owner.controller.session_state, "modality_manager", None)
        if manager is None:
            return
        for modality in manager.get_all_modalities():
            if modality.image_id == owner.primary_image.id:
                owner.projection_selector.blockSignals(True)
                owner.projection_selector.set_modality(modality)
                owner.projection_selector.blockSignals(False)
                break
    elif getattr(owner, "projection_axis_combo", None) is not None:
        axis = "t"
        manager = getattr(owner.controller.session_state, "modality_manager", None)
        if manager is not None:
            for modality in manager.get_all_modalities():
                if modality.image_id == owner.primary_image.id:
                    axis = modality.display_settings.projection_axis
                    break
        owner.projection_axis_combo.blockSignals(True)
        owner.projection_axis_combo.setCurrentText(axis.upper())
        owner.projection_axis_combo.blockSignals(False)
