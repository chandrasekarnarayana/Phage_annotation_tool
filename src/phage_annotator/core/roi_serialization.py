"""Core roi serialization helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import List

import pandas as pd


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


def keypoints_from_csv(path: Path) -> list:
    """Load keypoints from a CSV file. Supports legacy two-column (x, y) files."""
    from phage_annotator.core.annotation import Keypoint
    df = pd.read_csv(path, comment="#")
    if set([c.lower() for c in df.columns]) in ({"x", "y"}):
        df = df.assign(image_id=-1, image_name=path.stem, t=-1, z=-1, label="phage", source="legacy_csv")
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
            annotation_context=str(getattr(row, "annotation_context", "")))
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


def keypoints_from_json(path: Path) -> list:
    """Load keypoints from a JSON file keyed by image_name."""
    from phage_annotator.core.annotation import Keypoint
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "annotations" in data:
        data = data.get("annotations", {})
    keypoints: list = []
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
                annotation_context=str(row.get("annotation_context", "")))
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
