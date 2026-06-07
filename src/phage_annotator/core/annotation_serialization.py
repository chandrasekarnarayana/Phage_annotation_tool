"""CSV and JSON serialization helpers for annotation keypoints."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import pandas as pd

from phage_annotator.core.annotation_types import (
    Keypoint,
    PROVENANCE_DATAFRAME_COLUMNS,
)

__all__ = [
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
    "keypoints_from_csv",
    "keypoints_from_json",
]


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
