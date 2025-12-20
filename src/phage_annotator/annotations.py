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

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List

import json
import pandas as pd
import uuid

__all__ = [
    "Keypoint",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "keypoints_from_csv",
    "keypoints_from_json",
]


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


def keypoints_to_dataframe(keypoints: Iterable[Keypoint]) -> pd.DataFrame:
    """Convert keypoints to a pandas DataFrame with standard columns."""
    cols = [
        "annotation_id",
        "image_id",
        "image_name",
        "image_key",
        "t",
        "z",
        "y",
        "x",
        "label",
        "source",
        "meta",
    ]
    rows = []
    for kp in keypoints:
        row = asdict(kp)
        if not row.get("image_key"):
            row["image_key"] = row.get("image_name", "")
        if isinstance(row.get("meta"), dict):
            row["meta"] = json.dumps(row["meta"])
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


def save_keypoints_csv(keypoints: Iterable[Keypoint], path: Path, meta: dict | None = None) -> None:
    """Write keypoints to CSV with standard columns."""
    df = keypoints_to_dataframe(keypoints)
    with path.open("w", encoding="utf-8") as handle:
        if meta:
            handle.write(f"# phage_annotator: {json.dumps(meta)}\n")
        df.to_csv(handle, index=False)


def save_keypoints_json(keypoints: Iterable[Keypoint], path: Path, meta: dict | None = None) -> None:
    """Write keypoints to JSON grouped by image_name."""
    grouped: dict[str, list[dict[str, object]]] = {}
    for kp in keypoints:
        row = asdict(kp)
        if not row.get("image_key"):
            row["image_key"] = row.get("image_name", "")
        grouped.setdefault(kp.image_name, []).append(row)
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
    return [
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
        )
        for row in df.itertuples(index=False)
    ]


def keypoints_from_json(path: Path) -> list[Keypoint]:
    """Load keypoints from a JSON file keyed by image_name."""
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "annotations" in data:
        data = data.get("annotations", {})
    keypoints: list[Keypoint] = []
    for image_name, rows in data.items():
        for row in rows:
            keypoints.append(
                Keypoint(
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
                )
            )
    return keypoints
