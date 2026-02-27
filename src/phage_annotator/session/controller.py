"""Session controller for application state mutations.

This module provides the SessionController QObject that owns session, view, and
display state for the GUI. The controller emits signals back to the UI when
state changes, ensuring mutation happens in one place and the GUI only reacts
to state updates.
"""

from __future__ import annotations

import pathlib
import time
from typing import Dict, List, Optional, Sequence, TYPE_CHECKING

import numpy as np
from matplotlib.backends.qt_compat import QtCore

from phage_annotator.config.density import DensityConfig
from phage_annotator.density.model import DensityPredictor
from phage_annotator.analysis.suggestion_ranker import (
    LightweightSuggestionRanker,
    feature_vector_from_suggestion,
)
from phage_annotator.data.display_mapping import DisplayMapping
from phage_annotator.roi.manager import Roi
from phage_annotator.session.annotation_io import SessionAnnotationIOMixin
from phage_annotator.session.annotations import SessionAnnotationsMixin
from phage_annotator.session.images import SessionImageMixin
from phage_annotator.session.playback import SessionPlaybackMixin
from phage_annotator.session.project import SessionProjectMixin
from phage_annotator.session.view import SessionViewMixin
from phage_annotator.core.session_state import SessionState, ViewState

# Unified logging through service framework
try:
    from phage_annotator.framework import get_log_service
    _logger = get_log_service().get_logger(__name__)
except (ImportError, RuntimeError, AttributeError):
    # Fallback to stdlib logging if service not available
    import logging
    _logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from phage_annotator.data.models import LazyImage


class SessionController(
    QtCore.QObject,
    SessionImageMixin,
    SessionViewMixin,
    SessionPlaybackMixin,
    SessionAnnotationsMixin,
    SessionAnnotationIOMixin,
    SessionProjectMixin,
):
    """Main state controller for the GUI.

    Notes
    -----
    All state mutations should occur through this controller, which emits
    Qt signals for the GUI to react. Arrays may be memmapped; annotations
    are always stored in full-resolution pixel coordinates.
    """

    state_changed = QtCore.Signal()
    view_changed = QtCore.Signal()
    display_changed = QtCore.Signal()
    annotations_changed = QtCore.Signal()
    playback_changed = QtCore.Signal()
    error_occurred = QtCore.Signal(str)
    roi_changed = QtCore.Signal()

    def __init__(
        self,
        parent: QtCore.QObject,
        images: List["LazyImage"],
        labels: Sequence[str],
        settings: QtCore.QSettings,
        *,
        proj_cache=None,
        pyramid_cache=None,
        ring_buffer=None,
        colormaps: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(parent)
        if not images:
            raise ValueError("No images provided.")
        for idx, img in enumerate(images):
            img.id = idx
        # P3.5: Ensure label list always has defaults if empty
        label_list = list(labels) if labels else ["Point", "Region"]
        annotations = {img.id: [] for img in images}
        image_states = {img.id: self._build_image_state(img) for img in images}
        annotations_loaded = {img.id: False for img in images}
        self.session_state = SessionState(
            project_path=None,
            project_save_time=None,
            dirty=False,
            last_folder=None,
            recent_images=[],
            active_primary_id=0,
            active_support_id=0 if len(images) == 1 else 1,
            images=images,
            image_states=image_states,
            annotations=annotations,
            labels=label_list,
            current_label=label_list[0] if label_list else "",
            fps=int(settings.value("defaultFPS", 12, type=int)),
            annotations_loaded=annotations_loaded,
            suggestions={img.id: [] for img in images},
            suggestion_history={img.id: [] for img in images},
        )
        self.view_state = ViewState(
            t=0,
            z=0,
            crop_rect=(300.0, 300.0, 600.0, 600.0),
            hist_bins=int(settings.value("histBinsDefault", 100, type=int)),
        )
        self.display_mapping = DisplayMapping(0.0, 1.0)
        self.display_mapping.ensure_panels(("frame", "mean", "support", "std"))
        self.rois_by_image: Dict[int, List[Roi]] = {}
        self._settings = settings
        self._colormaps = list(colormaps) if colormaps is not None else []
        self._undo_stack: List[dict] = []
        self._redo_stack: List[dict] = []
        self.proj_cache = proj_cache
        self.pyramid_cache = pyramid_cache
        self.ring_buffer = ring_buffer
        self._metadata_cache: Dict[pathlib.Path, object] = {}
        self.density_predictor: Optional[DensityPredictor] = None
        self.density_config = DensityConfig()
        self.density_infer_options = None
        self.density_model_path: Optional[str] = None
        self.density_device: str = "auto"
        self.density_target_panel: str = "frame"
        self.suggestion_ranker = LightweightSuggestionRanker()
        self.suggestion_rankers_by_space: Dict[str, LightweightSuggestionRanker] = {
            "stack": LightweightSuggestionRanker(),
            "projection": LightweightSuggestionRanker(),
        }
        self.session_state.suggestion_auto_retrain_enabled = bool(
            settings.value("suggestionAutoRetrainEnabled", True, type=bool)
        )
        self.session_state.suggestion_auto_retrain_min_labels = int(
            settings.value("suggestionAutoRetrainMinLabels", 25, type=int)
        )
        self.session_state.assist_min_total_labels = int(
            settings.value("assistMinTotalLabels", 30, type=int)
        )
        self.session_state.assist_min_positive_labels = int(
            settings.value("assistMinPositiveLabels", 15, type=int)
        )
        self.session_state.assist_min_negative_labels = int(
            settings.value("assistMinNegativeLabels", 15, type=int)
        )
        self.session_state.assist_min_labels_per_context = int(
            settings.value("assistMinLabelsPerContext", 10, type=int)
        )
        self._ranker_retrain_timer = QtCore.QTimer(self)
        self._ranker_retrain_timer.setSingleShot(True)
        self._ranker_retrain_timer.setInterval(800)
        self._ranker_retrain_timer.timeout.connect(self._retrain_timer_fired)

    def append_audit_event(self, event_type: str, **details: object) -> None:
        """Append an immutable audit event entry to session state."""
        self.session_state.audit_log.append(
            {
                "timestamp": time.time(),
                "user": self.session_state.current_user,
                "event_type": event_type,
                "details": dict(details),
            }
        )

    def update_suggestion_metrics(
        self,
        *,
        generated: int = 0,
        accepted: int = 0,
        rejected: int = 0,
        correction_distance: Optional[float] = None,
        **extra_counters: float,
    ) -> None:
        """Update aggregate suggestion workflow metrics."""
        metrics = self.session_state.suggestion_metrics
        metrics["generated"] = float(metrics.get("generated", 0.0) + int(generated))
        metrics["accepted"] = float(metrics.get("accepted", 0.0) + int(accepted))
        metrics["rejected"] = float(metrics.get("rejected", 0.0) + int(rejected))
        if correction_distance is not None:
            prev = float(metrics.get("mean_correction_distance", 0.0))
            accepted_total = max(1.0, float(metrics.get("accepted", 1.0)))
            metrics["mean_correction_distance"] = prev + (
                (float(correction_distance) - prev) / accepted_total
            )
        for key, value in extra_counters.items():
            metric_key = str(key)
            metrics[metric_key] = float(metrics.get(metric_key, 0.0) + float(value))

    def restore_suggestion_ranker(self) -> None:
        payload = getattr(self.session_state, "suggestion_ranker_state", {})
        if isinstance(payload, dict) and payload:
            self.suggestion_ranker = LightweightSuggestionRanker.from_dict(payload)
            self.suggestion_rankers_by_space["stack"] = self.suggestion_ranker
            projection_payload = payload.get("projection_ranker")
            if isinstance(projection_payload, dict):
                self.suggestion_rankers_by_space["projection"] = LightweightSuggestionRanker.from_dict(
                    projection_payload
                )
        else:
            self.suggestion_ranker = LightweightSuggestionRanker()
            self.suggestion_rankers_by_space["stack"] = self.suggestion_ranker
            self.suggestion_rankers_by_space["projection"] = LightweightSuggestionRanker()

    def save_suggestion_ranker_state(self) -> None:
        payload = self.suggestion_rankers_by_space["stack"].to_dict()
        payload["projection_ranker"] = self.suggestion_rankers_by_space["projection"].to_dict()
        self.session_state.suggestion_ranker_state = payload

    def _context_key(self, *, suggestion, annotation_space: str) -> str:
        dataset = str(getattr(suggestion, "image_name", "unknown"))
        modality = str(getattr(suggestion, "source_modality", "raw"))
        return f"{dataset}|{annotation_space}|{modality}"

    def _context_ready(self, annotation_space: str, context_key: str) -> tuple[bool, int]:
        breakdown = self.assist_need_breakdown(
            annotation_space=annotation_space, context_key=context_key
        )
        need = int(
            max(
                breakdown["need_total"],
                breakdown["need_pos"],
                breakdown["need_neg"],
                breakdown["need_context"],
            )
        )
        return need <= 0, need

    def assist_need_breakdown(self, *, annotation_space: str, context_key: str) -> Dict[str, int]:
        rows = list(getattr(self.session_state, "suggestion_training_samples", []))
        total = len(rows)
        pos = sum(1 for r in rows if int(r.get("y", 0)) == 1)
        neg = max(0, total - pos)
        ctx = self.session_state.suggestion_context_stats.get(
            context_key, {"total": 0, "pos": 0, "neg": 0}
        )
        need_total = max(0, int(self.session_state.assist_min_total_labels) - total)
        need_pos = max(0, int(self.session_state.assist_min_positive_labels) - pos)
        need_neg = max(0, int(self.session_state.assist_min_negative_labels) - neg)
        need_ctx = max(0, int(self.session_state.assist_min_labels_per_context) - int(ctx.get("total", 0)))
        return {
            "need_total": int(need_total),
            "need_pos": int(need_pos),
            "need_neg": int(need_neg),
            "need_context": int(need_ctx),
            "total": int(total),
            "pos": int(pos),
            "neg": int(neg),
            "context_total": int(ctx.get("total", 0)),
        }

    def assist_status(self, *, annotation_space: str, context_key: str) -> tuple[str, str]:
        if not bool(self.session_state.suggestion_auto_retrain_enabled):
            return "heuristic", "Assist: Heuristic (auto-retrain disabled)"
        ready, need = self._context_ready(annotation_space, context_key)
        if ready:
            return "learned", "Assist: Learned"
        return "unavailable", f"Assist: Unavailable (needs {need} more labels)"

    def score_suggestions_for_context(self, suggestions: List, *, annotation_space: str) -> List:
        if not suggestions:
            return suggestions
        context_key = self._context_key(
            suggestion=suggestions[0],
            annotation_space=annotation_space,
        )
        ready, _ = self._context_ready(annotation_space, context_key)
        if not ready:
            for suggestion in suggestions:
                suggestion.meta["confidence_available"] = False
                suggestion.meta["confidence_note"] = "heuristic_only"
            return suggestions
        ranker = self.suggestion_rankers_by_space.get(annotation_space, self.suggestion_rankers_by_space["stack"])
        ranked = ranker.apply_to_suggestions(suggestions)
        for suggestion in ranked:
            suggestion.meta["confidence_available"] = True
        return ranked

    def observe_suggestion_feedback(self, suggestion, accepted: bool) -> None:
        """Record label for periodic offline ranker updates."""
        meta = dict(getattr(suggestion, "meta", {}) or {})
        if bool(meta.get("derived_from_accepted_area", False)) and not bool(
            meta.get("self_confirmation_marked", False)
        ):
            self.update_suggestion_metrics(training_skipped_self_confirmation=1)
            return
        try:
            features = feature_vector_from_suggestion(suggestion)
        except Exception:
            return
        row = {
            "x": [float(v) for v in features.tolist()],
            "y": int(1 if accepted else 0),
            "timestamp": time.time(),
            "image_id": int(getattr(suggestion, "image_id", -1)),
            "suggestion_id": str(getattr(suggestion, "suggestion_id", "")),
            "strategy": str(getattr(suggestion, "source_modality", "raw")),
            "derived_from_accepted_area": bool(meta.get("derived_from_accepted_area", False)),
            "annotation_space": str(getattr(self.session_state, "annotation_space", "stack")),
            "context_key": self._context_key(
                suggestion=suggestion,
                annotation_space=str(getattr(self.session_state, "annotation_space", "stack")),
            ),
        }
        self.session_state.suggestion_training_samples.append(row)
        ctx = self.session_state.suggestion_context_stats.setdefault(
            str(row["context_key"]), {"total": 0, "pos": 0, "neg": 0}
        )
        ctx["total"] = int(ctx.get("total", 0) + 1)
        if int(row["y"]) == 1:
            ctx["pos"] = int(ctx.get("pos", 0) + 1)
        else:
            ctx["neg"] = int(ctx.get("neg", 0) + 1)
        self.session_state.suggestion_training_pending = int(
            self.session_state.suggestion_training_pending + 1
        )
        # Debounce retraining to keep annotation interactions responsive.
        self._ranker_retrain_timer.start()

    def observe_suggestion_correction(self, suggestion, *, dx: float, dy: float) -> None:
        """Log a geometric correction as a positive training signal."""
        try:
            features = feature_vector_from_suggestion(suggestion)
        except Exception:
            return
        row = {
            "x": [float(v) for v in features.tolist()],
            "y": 1,
            "timestamp": time.time(),
            "image_id": int(getattr(suggestion, "image_id", -1)),
            "suggestion_id": str(getattr(suggestion, "suggestion_id", "")),
            "strategy": str(getattr(suggestion, "source_modality", "raw")),
            "annotation_space": str(getattr(self.session_state, "annotation_space", "stack")),
            "context_key": self._context_key(
                suggestion=suggestion,
                annotation_space=str(getattr(self.session_state, "annotation_space", "stack")),
            ),
            "correction_dx": float(dx),
            "correction_dy": float(dy),
            "correction_distance": float((float(dx) ** 2 + float(dy) ** 2) ** 0.5),
            "signal_type": "batch_offset",
        }
        self.session_state.suggestion_training_samples.append(row)
        ctx = self.session_state.suggestion_context_stats.setdefault(
            str(row["context_key"]), {"total": 0, "pos": 0, "neg": 0}
        )
        ctx["total"] = int(ctx.get("total", 0) + 1)
        ctx["pos"] = int(ctx.get("pos", 0) + 1)
        self.session_state.suggestion_training_pending = int(
            self.session_state.suggestion_training_pending + 1
        )
        self._ranker_retrain_timer.start()

    def _retrain_timer_fired(self) -> None:
        self._maybe_retrain_suggestion_ranker()

    def _maybe_retrain_suggestion_ranker(self, force: bool = False) -> None:
        if (not force) and (not bool(self.session_state.suggestion_auto_retrain_enabled)):
            return
        pending = int(getattr(self.session_state, "suggestion_training_pending", 0))
        min_pending = int(max(1, self.session_state.suggestion_auto_retrain_min_labels))
        if not force and pending < min_pending:
            return
        rows = list(getattr(self.session_state, "suggestion_training_samples", []))
        if len(rows) < 20:
            return
        trained_any = False
        for space in ("stack", "projection"):
            xs = []
            ys = []
            for row in rows[-4000:]:
                if str(row.get("annotation_space", "stack")) != space:
                    continue
                x = row.get("x")
                y = row.get("y")
                if not isinstance(x, list) or len(x) == 0:
                    continue
                xs.append([float(v) for v in x])
                ys.append(float(y))
            if len(xs) < 20 or len(set(ys)) < 2:
                continue
            x_arr = np.asarray(xs, dtype=np.float64)
            y_arr = np.asarray(ys, dtype=np.float64)
            pos = max(1, int(np.sum(y_arr >= 0.5)))
            neg = max(1, int(np.sum(y_arr < 0.5)))
            pos_w = float(0.5 * y_arr.shape[0] / pos)
            neg_w = float(0.5 * y_arr.shape[0] / neg)
            sample_weight = np.where(y_arr >= 0.5, pos_w, neg_w)
            self.suggestion_rankers_by_space[space].fit(
                x_arr,
                y_arr,
                sample_weight=sample_weight,
                epochs=(120 if not force else 240),
            )
            trained_any = True
            if space == "stack":
                self.suggestion_ranker = self.suggestion_rankers_by_space["stack"]
        if not trained_any:
            return
        self.session_state.suggestion_training_pending = 0
        self.save_suggestion_ranker_state()
        self.append_audit_event(
            "suggestion_ranker_trained",
            samples=len(xs),
            class_balance={"positive": pos, "negative": neg},
            trained_samples=int(self.suggestion_ranker.trained_samples),
        )

    def set_suggestion_retrain_config(
        self, *, enabled: Optional[bool] = None, min_labels: Optional[int] = None
    ) -> None:
        if enabled is not None:
            self.session_state.suggestion_auto_retrain_enabled = bool(enabled)
        if min_labels is not None:
            self.session_state.suggestion_auto_retrain_min_labels = int(max(1, min_labels))

    def set_assist_minima(
        self,
        *,
        min_total: Optional[int] = None,
        min_positive: Optional[int] = None,
        min_negative: Optional[int] = None,
        min_per_context: Optional[int] = None,
    ) -> None:
        if min_total is not None:
            self.session_state.assist_min_total_labels = int(max(1, min_total))
        if min_positive is not None:
            self.session_state.assist_min_positive_labels = int(max(1, min_positive))
        if min_negative is not None:
            self.session_state.assist_min_negative_labels = int(max(1, min_negative))
        if min_per_context is not None:
            self.session_state.assist_min_labels_per_context = int(max(1, min_per_context))

    def train_suggestion_ranker_now(self) -> bool:
        """Force ranker training using current labeled samples."""
        before = int(
            max(
                getattr(self.suggestion_rankers_by_space["stack"], "trained_samples", 0),
                getattr(self.suggestion_rankers_by_space["projection"], "trained_samples", 0),
            )
        )
        self._maybe_retrain_suggestion_ranker(force=True)
        after = int(
            max(
                getattr(self.suggestion_rankers_by_space["stack"], "trained_samples", 0),
                getattr(self.suggestion_rankers_by_space["projection"], "trained_samples", 0),
            )
        )
        return after >= before and after > 0
