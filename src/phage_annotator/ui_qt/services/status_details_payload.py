"""Status details payload assembly."""

from __future__ import annotations

from typing import Any

from phage_annotator.ui_qt.assist_state import AssistState, assist_state_label


def build_details_payload(owner: Any, values: dict[str, Any]) -> dict[str, str]:
    """Build label payload values for the status details panel."""
    assist_state = values["assist_state"]
    need = int(values["need"])
    return {
        "dataset_lbl": values["dataset_name"],
        "tz_lbl": values["frame_txt"],
        "scope_lbl": values["scope_state"],
        "target_lbl": values["target_state"],
        "sync_group_lbl": values["sync_group"],
        "sync_modes_lbl": values["sync_modes_label"],
        "write_mode_lbl": values["write_mode_label"],
        "write_context_lbl": values["context_key_label"],
        "binding_lbl": values["binding_label"],
        "modality_lbl": values["modality_txt"],
        "label_lbl": str(owner.current_label),
        "assist_lbl": f"{assist_state_label(assist_state)}"
        + (f" (Need {need} more labels)" if assist_state == AssistState.HEURISTIC and need > 0 else ""),
        "context_lbl": owner._effective_assist_context_line()
        if hasattr(owner, "_effective_assist_context_line")
        else "-",
        "suggestions_lbl": values["suggestions_text"],
        "qc_lbl": values["qc_label"],
        "results_lbl": "Results: empty" if int(values["results_rows"]) <= 0 else f"Results: {values['results_rows']} rows",
        "points_lbl": f"Slice {values['current']} | Total {values['total']}",
        "roi_area_lbl": f"{values['roi_total_area_um2']:.2f} um^2" if values["roi_total_area_um2"] > 0 else "n/a",
        "density_lbl": f"{values['roi_total_density']:.3f} /um^2" if values["roi_total_area_um2"] > 0 else "n/a",
        "fps_lbl": f"{int(owner.speed_slider.value())} fps",
        "autosave_lbl": values["autosave_txt"],
        "cache_lbl": f"{values['cache_mb']} MB | {values['cache_items']} items",
        "jobs_lbl": values["jobs_txt"],
        "diag_lbl": "; ".join(values["diag_flags"]) if values["diag_flags"] else "none",
    }
