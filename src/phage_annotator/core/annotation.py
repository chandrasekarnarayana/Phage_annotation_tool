"""Keypoint models and serialization helpers for microscopy annotations.

This module defines the serialized schema for annotation data and provides
CSV/JSON helpers used by the GUI and project I/O. The schema is stable and
backward compatible with legacy x/y CSVs.

Conventions
-----------
- Coordinates are stored in full-resolution image coordinates.
- t/z are integers; -1 indicates "all frames" when applicable.
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
        self.meta["confidence"] = None if value is None else float(value)

    @property
    def roi_name(self) -> str:
        """ROI label or identifier associated with the annotation."""
        return str(self.meta.get("roi", "") or "")

    @roi_name.setter
    def roi_name(self, value: str) -> None:
        self.meta["roi"] = str(value or "")

    @property
    def notes(self) -> str:
        """Short free-text note for audit/review workflows."""
        raw = self.meta.get("notes", self.meta.get("comment", ""))
        return str(raw or "")

    @notes.setter
    def notes(self, value: str) -> None:
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


def keypoints_from_csv(path: Path) -> list[Keypoint]:
    """Load keypoints from a CSV file.

    Supports legacy two-column files (x, y) by assigning defaults.
    """
    df = pd.read_csv(path, comment="#")
    # Legacy: only x,y columns
    if set([c.lower() for c in df.columns]) in ({"x", "y"},):
        df = df.assign(
            image_id=-1,
            image_name=path.stem,
            t=-1,
            z=-1,
            label="phage",
            source="legacy_csv",
        )
    required = {"image_name", "t", "z", "y", "x"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")
    keypoints = [
        Keypoint(
            image_id=int(getattr(row, "image_id", -1)),
            image_name=str(row.image_name),
            t=int(row.t),
            z=int(row.z),
            y=float(row.y),
            x=float(row.x),
            label=str(getattr(row, "label", "phage")),
            annotation_id=str(getattr(row, "annotation_id", str(uuid.uuid4()))),
            image_key=str(getattr(row, "image_key", getattr(row, "image_name", ""))),
            source=str(getattr(row, "source", "legacy_csv")),
            meta=json.loads(getattr(row, "meta", "{}")) if hasattr(row, "meta") else {},
            annotation_context=str(getattr(row, "annotation_context", "")),
        )
        for row in df.itertuples(index=False)
    ]
    for index, row in enumerate(df.itertuples(index=False)):
        kp = keypoints[index]
        if hasattr(row, "status"):
            kp.status = str(getattr(row, "status", kp.status))
        if hasattr(row, "confidence"):
            raw_conf = getattr(row, "confidence", kp.confidence)
            kp.confidence = None if pd.isna(raw_conf) else float(raw_conf)
        if hasattr(row, "roi"):
            kp.roi_name = str(getattr(row, "roi", kp.roi_name))
        if hasattr(row, "notes"):
            kp.notes = str(getattr(row, "notes", kp.notes))
    return keypoints


def keypoints_from_json(path: Path) -> list[Keypoint]:
    """Load keypoints from a JSON file keyed by image_name."""
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "annotations" in data:
        data = data.get("annotations", {})
    keypoints: list[Keypoint] = []
    for image_name, rows in data.items():
        for row in rows:
            kp = Keypoint(
                image_id=int(row.get("image_id", -1)),
                image_name=str(image_name),
                t=int(row.get("t", -1)),
                z=int(row.get("z", -1)),
                y=float(row.get("y", 0)),
                x=float(row.get("x", 0)),
                label=str(row.get("label", "phage")),
                annotation_id=str(row.get("annotation_id", str(uuid.uuid4()))),
                image_key=str(row.get("image_key", str(image_name))),
                source=str(row.get("source", "json")),
                meta=dict(row.get("meta", {})),
                annotation_context=str(row.get("annotation_context", "")),
            )
            if "status" in row:
                kp.status = str(row.get("status", kp.status))
            if "confidence" in row:
                raw_conf = row.get("confidence")
                kp.confidence = None if raw_conf in (None, "") else float(raw_conf)
            if "roi" in row:
                kp.roi_name = str(row.get("roi", kp.roi_name))
            if "notes" in row:
                kp.notes = str(row.get("notes", kp.notes))
            keypoints.append(kp)
    return keypoints
