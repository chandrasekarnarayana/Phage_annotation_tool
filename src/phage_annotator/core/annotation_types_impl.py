"""Core annotation types impl helpers for the phage annotation tool.

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

from phage_annotator.core.annotation_types import PointSuggestion
from phage_annotator.core.annotation_serialization import (
    keypoints_from_csv,
    keypoints_from_json,
)

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

def keypoints_to_dataframe(
    keypoints: Iterable[Keypoint], *, include_provenance: bool = False
) -> pd.DataFrame:
    """Convert keypoints to a pandas DataFrame with standard columns.

    Tests expect exactly these columns and order:
    ["image_id", "image_name", "t", "z", "y", "x", "label"].
    """
    cols = ["image_id", "image_name", "t", "z", "y", "x", "label"]
    if include_provenance:
        cols.extend(PROVENANCE_DATAFRAME_COLUMNS)
    rows = [
        {
            "image_id": kp.image_id,
            "image_name": kp.image_name,
            "t": kp.t,
            "z": kp.z,
            "y": kp.y,
            "x": kp.x,
            "label": kp.label,
            "source": kp.source,
            "status": kp.status,
            "confidence": kp.confidence,
            "roi": kp.roi_name,
            "notes": kp.notes,
        }
        for kp in keypoints
    ]
    return pd.DataFrame(rows, columns=cols)

def save_keypoints_csv(
    keypoints: Iterable[Keypoint],
    path: Path,
    meta: dict | None = None,
    *,
    include_provenance: bool = False,
) -> None:
    """Write keypoints to CSV with standard columns."""
    df = keypoints_to_dataframe(keypoints, include_provenance=include_provenance)
    with path.open("w", encoding="utf-8") as handle:
        if meta:
            handle.write(f"# phage_annotator: {json.dumps(meta)}\n")
        df.to_csv(handle, index=False)

def save_keypoints_json(
    keypoints: Iterable[Keypoint],
    path: Path,
    meta: dict | None = None,
    *,
    include_provenance: bool = False,
) -> None:
    """Write keypoints to JSON grouped by image_name."""
    grouped: dict[str, list[dict[str, object]]] = {}
    for kp in keypoints:
        row = asdict(kp)
        if not row.get("image_key"):
            row["image_key"] = row.get("image_name", "")
        if include_provenance:
            row["status"] = kp.status
            row["confidence"] = kp.confidence
            row["roi"] = kp.roi_name
            row["notes"] = kp.notes
        grouped.setdefault(kp.image_name, []).append(row)
    payload: dict
    if meta:
        payload = {"meta": meta, "annotations": grouped}
    else:
        payload = grouped
    path.write_text(json.dumps(payload, indent=2))
