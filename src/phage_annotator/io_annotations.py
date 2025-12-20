"""Helpers for loading annotations from multiple CSV formats."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from phage_annotator.annotations import Keypoint


def detect_format(csv_path: Path) -> str:
    """Detect CSV format (thunderstorm | legacy | other)."""
    df = pd.read_csv(csv_path, nrows=1, comment="#")
    cols = [c.strip().lower() for c in df.columns]
    if any("x [nm]" in c or "y [nm]" in c for c in cols):
        return "thunderstorm"
    if any("x [px]" in c or "y [px]" in c for c in cols):
        return "thunderstorm"
    if "frame" in cols or "frame number" in cols:
        if "x" in cols and "y" in cols:
            return "thunderstorm"
    if set(cols) == {"x", "y"} or set(cols[:2]) == {"x", "y"}:
        return "legacy"
    return "other"


def parse_legacy_csv(csv_path: Path, image_name: str, label: str = "phage") -> List[Keypoint]:
    """Parse legacy CSVs containing only x/y."""
    df = pd.read_csv(csv_path, comment="#")
    cols = [c.lower() for c in df.columns]
    if "x" not in cols or "y" not in cols:
        raise ValueError("Legacy CSV must include x,y columns.")
    x_col = df.columns[cols.index("x")]
    y_col = df.columns[cols.index("y")]
    points = []
    img_col = None
    if "image_name" in cols:
        img_col = df.columns[cols.index("image_name")]
    for row in df.itertuples(index=False):
        x = float(getattr(row, x_col))
        y = float(getattr(row, y_col))
        name = str(getattr(row, img_col)) if img_col else image_name
        points.append(
            Keypoint(
                image_id=-1,
                image_name=name,
                t=-1,
                z=-1,
                y=y,
                x=x,
                label=label,
                image_key=name,
                source="legacy_csv",
                meta={},
            )
        )
    return points


def parse_thunderstorm_csv(
    csv_path: Path,
    image_name: str,
    *,
    pixel_size_nm: Optional[float],
    default_label: str = "localization",
) -> List[Keypoint]:
    """Parse ThunderSTORM CSV into normalized keypoints."""
    df = pd.read_csv(csv_path, comment="#")
    col_map = _build_thunderstorm_mapping(df.columns)
    x_col = col_map.get("x")
    y_col = col_map.get("y")
    if x_col is None or y_col is None:
        raise ValueError("ThunderSTORM CSV missing x/y columns.")
    x_unit = col_map.get("x_unit", "px")
    y_unit = col_map.get("y_unit", "px")
    frame_col = col_map.get("frame")
    z_col = col_map.get("z")
    points: List[Keypoint] = []
    img_col = None
    cols_lower = [c.lower() for c in df.columns]
    if "image_name" in cols_lower:
        img_col = df.columns[cols_lower.index("image_name")]
    frame_vals = df[frame_col] if frame_col else None
    base = _frame_base(frame_vals) if frame_vals is not None else 0
    for row in df.itertuples(index=False):
        x_val = float(getattr(row, x_col))
        y_val = float(getattr(row, y_col))
        meta: Dict[str, object] = {col: getattr(row, col) for col in df.columns if hasattr(row, col)}
        name = str(getattr(row, img_col)) if img_col else image_name
        if x_unit == "nm" or y_unit == "nm":
            if pixel_size_nm:
                x_px = x_val / pixel_size_nm
                y_px = y_val / pixel_size_nm
            else:
                x_px = x_val
                y_px = y_val
                meta["needs_calibration"] = True
                meta["coord_unit"] = "nm"
        else:
            x_px, y_px = x_val, y_val
        t = -1
        if frame_col:
            t_val = int(getattr(row, frame_col))
            t = t_val - base
            meta["frame_base"] = base
        z = -1
        if z_col:
            z = int(getattr(row, z_col))
        points.append(
            Keypoint(
                image_id=-1,
                image_name=name,
                t=t,
                z=z,
                y=y_px,
                x=x_px,
                label=default_label,
                image_key=name,
                source="thunderstorm_csv",
                meta=meta,
            )
        )
    return points


def _build_thunderstorm_mapping(columns: Iterable[str]) -> Dict[str, str]:
    cols = {c.strip().lower(): c for c in columns}
    mapping: Dict[str, str] = {}
    for key in ("x [nm]", "x(nm)", "x_nm"):
        if key in cols:
            mapping["x"] = cols[key]
            mapping["x_unit"] = "nm"
            break
    for key in ("x [px]", "x(px)", "x_px", "x"):
        if "x" not in mapping and key in cols:
            mapping["x"] = cols[key]
            mapping["x_unit"] = "px"
            break
    for key in ("y [nm]", "y(nm)", "y_nm"):
        if key in cols:
            mapping["y"] = cols[key]
            mapping["y_unit"] = "nm"
            break
    for key in ("y [px]", "y(px)", "y_px", "y"):
        if "y" not in mapping and key in cols:
            mapping["y"] = cols[key]
            mapping["y_unit"] = "px"
            break
    if "frame" in cols:
        mapping["frame"] = cols["frame"]
    elif "frame number" in cols:
        mapping["frame"] = cols["frame number"]
    if "z" in cols:
        mapping["z"] = cols["z"]
    return mapping


def _frame_base(series: Optional[pd.Series]) -> int:
    if series is None or series.empty:
        return 0
    vals = series.dropna().astype(int)
    if vals.empty:
        return 0
    if vals.min() == 1 and 0 not in set(vals.values):
        return 1
    return 0
