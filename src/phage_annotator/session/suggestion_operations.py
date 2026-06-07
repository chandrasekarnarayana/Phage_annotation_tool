"""Extracted method group 5 for SessionControllerSuggestionsMixin."""

from __future__ import annotations

import collections
import math
import time
from typing import Dict, List, Optional, TYPE_CHECKING

import numpy as np

from phage_annotator.analysis.suggestion_ranker import (
    LightweightSuggestionRanker,
    expected_calibration_error,
    feature_vector_from_suggestion,
)
from phage_annotator.annotation.core import Keypoint
from phage_annotator.session.signal_hub import emit_annotations_changed, emit_state_changed

if TYPE_CHECKING:
    from phage_annotator.core.annotation import PointSuggestion



class SuggestionOperationsMixin:
    """Method group 5 extracted from SessionControllerSuggestionsMixin."""

    def get_slice_suggestions(self, image_id: int, *, t_index: int, z_index: int) -> list["PointSuggestion"]:
        """Return slice suggestions for the current workflow."""
        image_key = int(image_id)
        t_idx = int(t_index)
        z_idx = int(z_index)
        pending = [
            suggestion for suggestion in self.session_state.suggestions.get(image_key, [])
            if int(getattr(suggestion, "t", -2)) in (t_idx, -1) and int(getattr(suggestion, "z", -2)) in (z_idx, -1)
        ]
        history_rows = [
            suggestion for suggestion in self.session_state.suggestion_history.get(image_key, [])
            if int(getattr(suggestion, "t", -2)) in (t_idx, -1) and int(getattr(suggestion, "z", -2)) in (z_idx, -1)
        ]
        seen = {str(getattr(suggestion, "suggestion_id", "")) for suggestion in pending}
        merged = list(pending)
        for suggestion in history_rows:
            sid = str(getattr(suggestion, "suggestion_id", ""))
            if sid and sid in seen:
                continue
            merged.append(suggestion)
        return merged
    def remove_annotations_for_suggestion(self, image_id: int, suggestion_id: str) -> int:
        """Remove annotations for suggestion for the current workflow."""
        image_key = int(image_id)
        sid = str(suggestion_id or "")
        rows = list(self.session_state.annotations.get(image_key, []))
        kept: List[Keypoint] = []
        removed = 0
        for ann in rows:
            meta = dict(getattr(ann, "meta", {}) or {})
            if str(meta.get("suggestion_id", "")) == sid:
                removed += 1
                continue
            kept.append(ann)
        if removed:
            self.session_state.annotations[image_key] = kept
            self.set_dirty(True)
            emit_annotations_changed(self, image_id=image_key, change_type="removed")
        return int(removed)
    def append_annotation_from_suggestion(self, suggestion: "PointSuggestion") -> bool:
        """Append annotation from suggestion for the current workflow."""
        image_id = int(getattr(suggestion, "image_id", -1))
        sid = str(getattr(suggestion, "suggestion_id", ""))
        existing = list(self.session_state.annotations.get(image_id, []))
        for ann in existing:
            meta = dict(getattr(ann, "meta", {}) or {})
            if str(meta.get("suggestion_id", "")) == sid:
                return False
        kp = Keypoint(
            image_id=image_id,
            image_name=str(getattr(suggestion, "image_name", "")),
            t=int(getattr(suggestion, "t", -1)),
            z=int(getattr(suggestion, "z", -1)),
            y=float(getattr(suggestion, "y", 0.0)),
            x=float(getattr(suggestion, "x", 0.0)),
            label=str(getattr(suggestion, "label", "")),
            source=f"suggested:{str(getattr(suggestion, 'source_model', 'model'))}",
            meta={
                "proposal_score": float(getattr(suggestion, "score", 0.0)),
                "score": float(getattr(suggestion, "score", 0.0)),
                "suggestion_id": sid,
                "source_model": str(getattr(suggestion, "source_model", "model")),
                "source_modality": str(getattr(suggestion, "source_modality", "raw")),
                "candidate_class": str(dict(getattr(suggestion, "meta", {}) or {}).get("candidate_class", "new")),
                "uncertainty_score": float(getattr(suggestion, "uncertainty_score", 0.0) or 0.0),
                "uncertainty_reason": str(getattr(suggestion, "uncertainty_reason", "") or ""),
                "supporting_modalities": list(getattr(suggestion, "supporting_modalities", []) or []),
                "cross_modality_consistency_score": getattr(suggestion, "cross_modality_consistency_score", None),
                "control_contradiction_score": getattr(suggestion, "control_contradiction_score", None),
                "density_context": dict(getattr(suggestion, "density_context", {}) or {}),
            },
        )
        kp.status = "accepted"
        kp.confidence = float(dict(getattr(suggestion, "meta", {}) or {}).get("p_accept", getattr(suggestion, "score", 0.0)))
        kp.roi_name = str(getattr(suggestion, "roi_id", "") or "")
        kp.notes = str(dict(getattr(suggestion, "meta", {}) or {}).get("notes", "") or "")
        kp.meta["supporting_modalities"] = list(getattr(suggestion, "supporting_modalities", []) or [])
        kp.meta["cross_modality_consistency_score"] = getattr(suggestion, "cross_modality_consistency_score", None)
        kp.meta["control_contradiction_score"] = getattr(suggestion, "control_contradiction_score", None)
        kp.meta["uncertainty_score"] = getattr(suggestion, "uncertainty_score", None)
        kp.meta["uncertainty_reason"] = str(getattr(suggestion, "uncertainty_reason", "") or "")
        kp.meta["density_context"] = dict(getattr(suggestion, "density_context", {}) or {})
        self.session_state.annotations.setdefault(image_id, []).append(kp)
        self.session_state.annotations_loaded[image_id] = True
        self.set_dirty(True)
        emit_annotations_changed(self, image_id=image_id, change_type="added")
        return True
    def update_suggestion_decision(self, image_id: int, suggestion_id: str, status: str) -> bool:
        """Update suggestion decision for the current workflow."""
        image_key = int(image_id)
        sid = str(suggestion_id or "").strip()
        target = str(status or "").strip().lower()
        if not sid or target not in {"accepted", "rejected", "proposed"}:
            return False
        pending = self.session_state.suggestions.setdefault(image_key, [])
        history = self.session_state.suggestion_history.setdefault(image_key, [])
        pending_idx = next((i for i, s in enumerate(pending) if str(getattr(s, "suggestion_id", "")) == sid), None)
        hist_idx = next((i for i, s in enumerate(history) if str(getattr(s, "suggestion_id", "")) == sid), None)
        pending_item = pending[pending_idx] if pending_idx is not None else None
        hist_item = history[hist_idx] if hist_idx is not None else None
        suggestion = pending_item if pending_item is not None else hist_item
        if suggestion is None:
            return False
        if target == "accepted":
            if pending_idx is not None:
                pending.pop(pending_idx)
            if hist_idx is None:
                history.append(suggestion)
                hist_idx = len(history) - 1
            history[hist_idx].status = "accepted"
            self.append_annotation_from_suggestion(history[hist_idx])
        elif target == "rejected":
            if pending_idx is not None:
                pending.pop(pending_idx)
            if hist_idx is None:
                history.append(suggestion)
                hist_idx = len(history) - 1
            history[hist_idx].status = "rejected"
            self.remove_annotations_for_suggestion(image_key, sid)
        else:
            self.remove_annotations_for_suggestion(image_key, sid)
            if hist_idx is not None:
                proposal = history.pop(hist_idx)
            else:
                proposal = suggestion
                if pending_idx is not None:
                    pending.pop(pending_idx)
            proposal.status = "proposed"
            if all(str(getattr(s, "suggestion_id", "")) != sid for s in pending):
                pending.append(proposal)
                pending.sort(key=self._stable_suggestion_sort_key)
        self.set_dirty(True)
        emit_annotations_changed(self, image_id=image_key, change_type="modified")
        return True
    def get_suggestion_calibration_samples(self) -> list[tuple[float, int]]:
        """Return suggestion calibration samples for the current workflow."""
        history = getattr(self.session_state, "suggestion_history", {}) or {}
        rows: list[tuple[float, int]] = []
        for items in history.values():
            for row in items:
                status = str(getattr(row, "status", ""))
                if status not in ("accepted", "rejected"):
                    continue
                meta = dict(getattr(row, "meta", {}) or {})
                if not bool(meta.get("confidence_available", False)):
                    continue
                p_accept = meta.get("p_accept")
                if p_accept is None:
                    continue
                try:
                    rows.append((float(p_accept), 1 if status == "accepted" else 0))
                except Exception:
                    continue
        return rows
    def update_suggestion_metrics(self, *, generated: int = 0, accepted: int = 0, rejected: int = 0, correction_distance: Optional[float] = None, **extra_counters: float) -> None:
        """Update suggestion metrics for the current workflow."""
        metrics = self.session_state.suggestion_metrics
        metrics["generated"] = float(metrics.get("generated", 0.0) + int(generated))
        metrics["accepted"] = float(metrics.get("accepted", 0.0) + int(accepted))
        metrics["rejected"] = float(metrics.get("rejected", 0.0) + int(rejected))
        if correction_distance is not None:
            prev = float(metrics.get("mean_correction_distance", 0.0))
            accepted_total = max(1.0, float(metrics.get("accepted", 1.0)))
            metrics["mean_correction_distance"] = prev + ((float(correction_distance) - prev) / accepted_total)
        for key, value in extra_counters.items():
            metric_key = str(key)
            metrics[metric_key] = float(metrics.get(metric_key, 0.0) + float(value))
        if hasattr(self, "record_workflow_event"):
            if int(generated):
                self.record_workflow_event("suggestions_generated", count=int(generated))
            if int(accepted):
                self.record_workflow_event("suggestions_accepted", count=int(accepted))
            if int(rejected):
                self.record_workflow_event("suggestions_rejected", count=int(rejected))
    def restore_suggestion_ranker(self) -> None:
        """Restore suggestion ranker for the current workflow."""
        payload = getattr(self.session_state, "suggestion_ranker_state", {})
        if isinstance(payload, dict) and payload:
            self.suggestion_ranker = LightweightSuggestionRanker.from_dict(payload)
            self.suggestion_rankers_by_space["stack"] = self.suggestion_ranker
            projection_payload = payload.get("projection_ranker")
            if isinstance(projection_payload, dict):
                self.suggestion_rankers_by_space["projection"] = LightweightSuggestionRanker.from_dict(projection_payload)
        else:
            self.suggestion_ranker = LightweightSuggestionRanker()
            self.suggestion_rankers_by_space["stack"] = self.suggestion_ranker
            self.suggestion_rankers_by_space["projection"] = LightweightSuggestionRanker()
    def save_suggestion_ranker_state(self) -> None:
        """Save suggestion ranker state for the current workflow."""
        payload = self.suggestion_rankers_by_space["stack"].to_dict()
        payload["projection_ranker"] = self.suggestion_rankers_by_space["projection"].to_dict()
        self.session_state.suggestion_ranker_state = payload
    def _context_key(self, *, suggestion, annotation_space: str) -> str:
        """Handle the context key helper flow."""
        dataset = str(getattr(suggestion, "image_name", "unknown"))
        modality = str(getattr(suggestion, "source_modality", "raw"))
        return f"{dataset}|{annotation_space}|{modality}"
    def _context_ready(self, annotation_space: str, context_key: str) -> tuple[bool, int]:
        """Handle the context ready helper flow."""
        breakdown = self.assist_need_breakdown(annotation_space=annotation_space, context_key=context_key)
        need = int(max(breakdown["need_total"], breakdown["need_pos"], breakdown["need_neg"], breakdown["need_context"]))
        return need <= 0, need
    def assist_need_breakdown(self, *, annotation_space: str, context_key: str) -> Dict[str, int]:
        """Run the assist need breakdown workflow."""
        rows = list(getattr(self.session_state, "suggestion_training_samples", []))
        total = len(rows)
        pos = sum(1 for r in rows if int(r.get("y", 0)) == 1)
        neg = max(0, total - pos)
        ctx = self.session_state.suggestion_context_stats.get(context_key, {"total": 0, "pos": 0, "neg": 0})
        need_total = max(0, int(self.session_state.assist_min_total_labels) - total)
        need_pos = max(0, int(self.session_state.assist_min_positive_labels) - pos)
        need_neg = max(0, int(self.session_state.assist_min_negative_labels) - neg)
        need_ctx = max(0, int(self.session_state.assist_min_labels_per_context) - int(ctx.get("total", 0)))
        return {"need_total": int(need_total), "need_pos": int(need_pos), "need_neg": int(need_neg), "need_context": int(need_ctx), "total": int(total), "pos": int(pos), "neg": int(neg), "context_total": int(ctx.get("total", 0))}
    def assist_status(self, *, annotation_space: str, context_key: str) -> tuple[str, str]:
        """Run the assist status workflow."""
        if not bool(self.session_state.suggestion_auto_retrain_enabled):
            return "heuristic", "Assist: Heuristic (auto-retrain disabled)"
        ready, need = self._context_ready(annotation_space, context_key)
        return ("learned", "Assist: Learned") if ready else ("unavailable", f"Assist: Unavailable (needs {need} more labels)")
