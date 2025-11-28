"""Keypoint models and serialization helpers for microscopy annotations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

import json
import pandas as pd

__all__ = [
    "Keypoint",
    "keypoints_to_dataframe",
    "save_keypoints_csv",
    "save_keypoints_json",
]


@dataclass
class Keypoint:
    """Represents a single annotated point in a stack.

    Fields capture image identity plus T/Z plane and Y/X coordinates with a label.
    """

    image_id: int
    image_name: str
    t: int
    z: int
    y: float
    x: float
    label: str = "phage"


def keypoints_to_dataframe(keypoints: Iterable[Keypoint]) -> pd.DataFrame:
    """Convert keypoints to a pandas DataFrame with standard columns."""
    cols = ["image_id", "image_name", "t", "z", "y", "x", "label"]
    rows = [asdict(kp) for kp in keypoints]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows, columns=cols)


def save_keypoints_csv(keypoints: Iterable[Keypoint], path: Path) -> None:
    """Write keypoints to CSV with standard columns."""
    df = keypoints_to_dataframe(keypoints)
    df.to_csv(path, index=False)


def save_keypoints_json(keypoints: Iterable[Keypoint], path: Path) -> None:
    """Write keypoints to JSON grouped by image_name."""
    df = keypoints_to_dataframe(keypoints)
    if df.empty:
        grouped: dict[str, list[dict[str, object]]] = {}
    else:
        grouped = {
            name: records.to_dict(orient="records")
            for name, records in df.groupby("image_name", sort=False)
        }
    path.write_text(json.dumps(grouped, indent=2))


def keypoints_from_csv(path: Path) -> list[Keypoint]:
    """Load keypoints from a CSV file.

    Supports legacy two-column files (x, y) by assigning defaults.
    """
    df = pd.read_csv(path)
    # Legacy: only x,y columns
    if set(df.columns[:2]) == {"x", "y"} or set(df.columns) == {"x", "y"}:
        df = df.rename(columns=df.iloc[0].to_dict()) if 0 else df  # no-op placeholder
        df = df.assign(
            image_id=-1,
            image_name=path.stem,
            t=0,
            z=0,
            label="phage",
        )
        df = df[["image_id", "image_name", "t", "z", "y", "x", "label"]] if "y" in df.columns else df
    required = {"image_id", "image_name", "t", "z", "y", "x", "label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")
    return [
        Keypoint(
            image_id=int(row.image_id),
            image_name=str(row.image_name),
            t=int(row.t),
            z=int(row.z),
            y=float(row.y),
            x=float(row.x),
            label=str(row.label),
        )
        for row in df.itertuples(index=False)
    ]


def keypoints_from_json(path: Path) -> list[Keypoint]:
    """Load keypoints from a JSON file keyed by image_name."""
    data = json.loads(path.read_text())
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
                )
            )
    return keypoints
