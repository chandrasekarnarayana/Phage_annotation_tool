"""Core annotation dataclasses: Keypoint and PointSuggestion."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

__all__ = [
    "ANNOTATION_META_DEFAULTS",
    "PROVENANCE_DATAFRAME_COLUMNS",
    "normalize_annotation_meta",
    "Keypoint",
    "PointSuggestion",
]

ANNOTATION_META_DEFAULTS = {
    "confidence": None,
    "status": "active",
    "roi": "",
    "notes": "",
    "annotator": "",
    "timestamp": None,
    "comment": "",
    "uncertain": False,
    "review_state": "new",
    "assignee": "",
    "reviewer": "",
    "reviewed_at": None,
}

PROVENANCE_DATAFRAME_COLUMNS = ["source", "status", "confidence", "roi", "notes"]


def normalize_annotation_meta(meta: dict | None) -> dict:
    """Normalize metadata dict to include baseline schema fields."""
    normalized = dict(meta or {})
    for key, default in ANNOTATION_META_DEFAULTS.items():
        normalized.setdefault(key, default)
    return normalized


@dataclass
class Keypoint:
    """Represents a single annotated point in a stack.

    Parameters
    ----------
    image_id : int
        Index of the image in the current session.
    image_name : str
        File name used for matching during load.
    t, z : int
        Indices for time/depth; -1 indicates "all frames".
    y, x : float
        Full-resolution coordinates in image space.
    label : str
        Annotation label/class.
    annotation_id : str
        Unique identifier for the annotation.
    image_key : str
        Stable image key (name or external id).
    source : str
        Source tag (manual | legacy_csv | thunderstorm_csv | json | project).
    meta : dict
        Extra metadata (sigma, photons, uncertainty, etc.).
    modality_idx : int, optional
        Index of the modality this annotation belongs to.
        If None, annotation is visible on all modalities (backward compatible).
        Enables modality-specific annotations for multi-view workflows.
    annotation_context : str
        Stable annotation-context key used for N-modality ownership and file
        binding. Empty values are treated as legacy image/modality-scoped rows.
    """

    image_id: int
    image_name: str
    t: int
    z: int
    y: float
    x: float
    label: str = "phage"
    annotation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    image_key: str = ""
    source: str = "manual"
    meta: dict = field(default_factory=dict)
    modality_idx: int | None = None  # Phase ζ: Multi-modality support
    annotation_context: str = ""

    def __post_init__(self) -> None:
        """Normalize derived state after dataclass initialization."""
        self.meta = normalize_annotation_meta(self.meta)

    @property
    def status(self) -> str:
        """Canonical annotation lifecycle state."""
        raw = self.meta.get("status")
        if raw is None:
            review_state = str(self.meta.get("review_state", "new")).strip().lower()
            mapping = {
                "approved": "accepted",
                "needs_changes": "conflict",
                "in_review": "suggested",
                "new": "active",
            }
            return mapping.get(review_state, "active")
        return str(raw or "active")

    @status.setter
    def status(self, value: str) -> None:
        """Return the status value."""
        self.meta["status"] = str(value or "active")

    @property
    def confidence(self) -> float | None:
        """Normalized confidence value when available."""
        raw = self.meta.get("confidence")
        if raw in (None, ""):
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    @confidence.setter
    def confidence(self, value: float | None) -> None:
        """Return the confidence value."""
        self.meta["confidence"] = None if value is None else float(value)

    @property
    def roi_name(self) -> str:
        """ROI label or identifier associated with the annotation."""
        return str(self.meta.get("roi", "") or "")

    @roi_name.setter
    def roi_name(self, value: str) -> None:
        """Return the roi name value."""
        self.meta["roi"] = str(value or "")

    @property
    def notes(self) -> str:
        """Short free-text note for audit/review workflows."""
        raw = self.meta.get("notes", self.meta.get("comment", ""))
        return str(raw or "")

    @notes.setter
    def notes(self, value: str) -> None:
        """Return the notes value."""
        text = str(value or "")
        self.meta["notes"] = text
        self.meta["comment"] = text


@dataclass
class PointSuggestion:
    """Model-generated candidate point pending user decision."""

    image_id: int
    image_name: str
    t: int
    z: int
    y: float
    x: float
    score: float
    label: str = "phage"
    suggestion_id: str = ""
    source_model: str = "local_peaks"
    source_modality: str = "raw"
    supporting_modalities: list[str] = field(default_factory=list)
    cross_modality_consistency_score: float | None = None
    control_contradiction_score: float | None = None
    scale_sigma: float = 1.0
    psf_radius: float = 6.0
    roi_id: str | None = None
    uncertainty_score: float | None = None
    uncertainty_reason: str = ""
    density_context: dict = field(default_factory=dict)
    score_components: dict = field(default_factory=dict)
    status: str = "proposed"
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize derived state after dataclass initialization."""
        if not str(self.suggestion_id or "").strip():
            payload = "|".join(
                [
                    str(self.image_id),
                    str(self.image_name),
                    str(self.t),
                    str(self.z),
                    f"{float(self.y):.4f}",
                    f"{float(self.x):.4f}",
                    str(self.label),
                    str(self.source_model),
                    str(self.source_modality),
                    str(self.roi_id or ""),
                    f"{float(self.scale_sigma):.4f}",
                    f"{float(self.psf_radius):.4f}",
                ]
            )
            self.suggestion_id = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

    @property
    def confidence(self) -> float:
        """Backward-compatible alias for legacy callers."""
        p_accept = self.meta.get("p_accept") if isinstance(self.meta, dict) else None
        if p_accept is not None:
            try:
                return float(p_accept)
            except (TypeError, ValueError):
                return float(self.score)
        return float(self.score)
