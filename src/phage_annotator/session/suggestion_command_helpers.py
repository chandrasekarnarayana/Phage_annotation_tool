"""Undoable commands for assisted annotation suggestions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController

from phage_annotator.core.annotation import Keypoint, PointSuggestion
from phage_annotator.session.commands import Command, CommandMemento
from phage_annotator.session.signal_hub import emit_annotations_changed


def _history_bucket(controller: "SessionController", image_id: int) -> list[PointSuggestion]:
    """Handle the history bucket helper flow."""
    history = getattr(controller.session_state, "suggestion_history", None)
    if history is None:
        history = {}
        setattr(controller.session_state, "suggestion_history", history)
    return history.setdefault(image_id, [])

def _emit_changed(controller: "SessionController", image_id: int) -> None:
    """Emit changed for the current workflow."""
    emit_annotations_changed(controller, image_id=image_id, change_type="modified")
    if hasattr(controller, "append_audit_event"):
        controller.append_audit_event("suggestion_command", image_id=image_id)

def _assist_context_for_suggestion(controller: "SessionController", suggestion: PointSuggestion) -> dict[str, object]:
    """Build a local assist context for post-decision updates."""
    return {
        "image_id": int(getattr(suggestion, "image_id", -1)),
        "t": int(getattr(suggestion, "t", getattr(controller.view_state, "t", 0))),
        "z": int(getattr(suggestion, "z", getattr(controller.view_state, "z", 0))),
        "roi_id": str(getattr(suggestion, "roi_id", "") or ""),
        "annotation_space": str(getattr(controller.session_state, "annotation_space", "stack")),
    }

def _suggestion_to_dict(s: PointSuggestion) -> dict:
    """Handle the suggestion to dict helper flow."""
    return {
        "image_id": int(s.image_id),
        "image_name": str(s.image_name),
        "t": int(s.t),
        "z": int(s.z),
        "y": float(s.y),
        "x": float(s.x),
        "score": float(s.score),
        "label": str(s.label),
        "suggestion_id": str(s.suggestion_id),
        "source_model": str(s.source_model),
        "source_modality": str(s.source_modality),
        "supporting_modalities": list(getattr(s, "supporting_modalities", []) or []),
        "cross_modality_consistency_score": getattr(s, "cross_modality_consistency_score", None),
        "control_contradiction_score": getattr(s, "control_contradiction_score", None),
        "scale_sigma": float(s.scale_sigma),
        "psf_radius": float(s.psf_radius),
        "roi_id": s.roi_id,
        "uncertainty_score": getattr(s, "uncertainty_score", None),
        "uncertainty_reason": str(getattr(s, "uncertainty_reason", "") or ""),
        "density_context": dict(getattr(s, "density_context", {}) or {}),
        "score_components": dict(s.score_components),
        "status": str(s.status),
        "meta": dict(s.meta),
    }

def _dict_to_suggestion(data: dict) -> PointSuggestion:
    """Handle the dict to suggestion helper flow."""
    return PointSuggestion(
        image_id=int(data.get("image_id", -1)),
        image_name=str(data.get("image_name", "")),
        t=int(data.get("t", -1)),
        z=int(data.get("z", -1)),
        y=float(data.get("y", 0.0)),
        x=float(data.get("x", 0.0)),
        score=float(data.get("score", data.get("confidence", 0.0))),
        label=str(data.get("label", "phage")),
        suggestion_id=str(data.get("suggestion_id", "")),
        source_model=str(data.get("source_model", "unknown")),
        source_modality=str(data.get("source_modality", "raw")),
        supporting_modalities=list(data.get("supporting_modalities", []) or []),
        cross_modality_consistency_score=data.get("cross_modality_consistency_score"),
        control_contradiction_score=data.get("control_contradiction_score"),
        scale_sigma=float(data.get("scale_sigma", 1.0)),
        psf_radius=float(data.get("psf_radius", 6.0)),
        roi_id=data.get("roi_id"),
        uncertainty_score=data.get("uncertainty_score"),
        uncertainty_reason=str(data.get("uncertainty_reason", "") or ""),
        density_context=dict(data.get("density_context", {}) or {}),
        score_components=dict(data.get("score_components", {})),
        status=str(data.get("status", "proposed")),
        meta=dict(data.get("meta", {})),
    )

def _suggestion_to_keypoint(s: PointSuggestion) -> Keypoint:
    """Handle the suggestion to keypoint helper flow."""
    kp = Keypoint(
        image_id=int(s.image_id),
        image_name=str(s.image_name),
        t=int(s.t),
        z=int(s.z),
        y=float(s.y),
        x=float(s.x),
        label=str(s.label),
        source=f"suggested:{s.source_model}",
        meta={
            "proposal_score": float(s.score),
            "score": float(s.score),
            "suggestion_id": s.suggestion_id,
            "source_model": str(s.source_model),
            "source_modality": str(s.source_modality),
            "candidate_class": str(dict(getattr(s, "meta", {}) or {}).get("candidate_class", "new")),
            "uncertainty_score": float(getattr(s, "uncertainty_score", 0.0) or 0.0),
            "uncertainty_reason": str(getattr(s, "uncertainty_reason", "") or ""),
            "supporting_modalities": list(getattr(s, "supporting_modalities", []) or []),
            "cross_modality_consistency_score": getattr(s, "cross_modality_consistency_score", None),
            "control_contradiction_score": getattr(s, "control_contradiction_score", None),
            "density_context": dict(getattr(s, "density_context", {}) or {}),
        },
    )
    kp.status = "accepted"
    kp.confidence = float(dict(getattr(s, "meta", {}) or {}).get("p_accept", s.score))
    kp.roi_name = str(getattr(s, "roi_id", "") or "")
    kp.notes = str(dict(getattr(s, "meta", {}) or {}).get("notes", "") or "")
    return kp
