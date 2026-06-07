"""Core source protocols impl helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import json
import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd

__all__ = [
    "Keypoint",
    "PointSuggestion",
    "ANNOTATION_META_DEFAULTS",
    "PROVENANCE_DATAFRAME_COLUMNS",
    "normalize_annotation_meta",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "keypoints_from_csv",
    "keypoints_from_json",
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
