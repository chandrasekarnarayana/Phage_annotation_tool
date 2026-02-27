"""Enhanced CSV serialization with full metadata preservation.

Provides CSV reading/writing that preserves annotation metadata while
maintaining backward compatibility with legacy x/y/label CSVs.

- Extended CSV format includes all metadata fields as columns
- Metadata JSON can be embedded in comment header for legacy tools compatibility
- Automatic fallback to legacy format for simple CSVs
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from phage_annotator.core.annotation import ANNOTATION_META_DEFAULTS, Keypoint


# Standard columns that appear in all CSV exports
STANDARD_COLUMNS = ["image_id", "image_name", "t", "z", "y", "x", "label", "annotation_id"]

# Baseline metadata field names (from schema)
BASELINE_METADATA_FIELDS = list(ANNOTATION_META_DEFAULTS.keys())


def save_keypoints_csv_with_metadata(
    keypoints: Iterable[Keypoint],
    path: Path,
    include_metadata: bool = True,
    meta: Optional[dict] = None,
) -> None:
    """Write keypoints to CSV preserving full metadata.
    
    Parameters
    ----------
    keypoints : Iterable[Keypoint]
        Annotations to save.
    path : Path
        Output CSV file path.
    include_metadata : bool, optional
        If True, include metadata columns and embed in header comment.
        If False, write legacy format (image_id, image_name, t, z, y, x, label).
    meta : dict, optional
        Top-level metadata (project info, schema version, etc.) to embed in comment.
    """
    keypoints_list = list(keypoints)
    if not keypoints_list:
        # Empty file
        path.write_text("")
        return
    
    if not include_metadata:
        # Legacy format - no metadata columns
        _save_keypoints_csv_legacy(keypoints_list, path, meta)
        return
    
    # Extended format with metadata
    _save_keypoints_csv_extended(keypoints_list, path, meta)


def _save_keypoints_csv_legacy(
    keypoints: list[Keypoint],
    path: Path,
    meta: Optional[dict] = None,
) -> None:
    """Write legacy CSV format (no metadata columns)."""
    rows = []
    for kp in keypoints:
        rows.append({
            "image_id": kp.image_id,
            "image_name": kp.image_name,
            "t": kp.t,
            "z": kp.z,
            "y": kp.y,
            "x": kp.x,
            "label": kp.label,
        })
    
    df = pd.DataFrame(rows, columns=STANDARD_COLUMNS[:-1])  # Exclude annotation_id
    
    with path.open("w", encoding="utf-8") as f:
        if meta:
            f.write(f"# phage_annotator_meta: {json.dumps(meta)}\n")
        df.to_csv(f, index=False)


def _save_keypoints_csv_extended(
    keypoints: list[Keypoint],
    path: Path,
    meta: Optional[dict] = None,
) -> None:
    """Write extended CSV format with metadata columns."""
    rows = []
    all_metadata_keys = set()
    
    # First pass: collect all metadata keys
    for kp in keypoints:
        all_metadata_keys.update(kp.meta.keys())
    
    # Sort metadata keys for consistent column order
    sorted_metadata_keys = sorted(all_metadata_keys)
    
    # Second pass: build rows
    for kp in keypoints:
        row = {
            "image_id": kp.image_id,
            "image_name": kp.image_name,
            "t": kp.t,
            "z": kp.z,
            "y": kp.y,
            "x": kp.x,
            "label": kp.label,
            "annotation_id": kp.annotation_id,
        }
        
        # Add metadata columns
        for key in sorted_metadata_keys:
            value = kp.meta.get(key)
            # Serialize complex types to JSON
            if isinstance(value, (dict, list)):
                row[key] = json.dumps(value)
            else:
                row[key] = value
        
        rows.append(row)
    
    # Build column order: standard columns first, then metadata
    columns = STANDARD_COLUMNS + sorted_metadata_keys
    df = pd.DataFrame(rows, columns=columns)
    
    # Write with metadata header
    with path.open("w", encoding="utf-8") as f:
        # Embed project metadata in comment
        if meta:
            f.write(f"# phage_annotator_meta: {json.dumps(meta)}\n")
        
        # Embed metadata schema in comment for transparency
        f.write(f"# metadata_fields: {json.dumps(sorted_metadata_keys)}\n")
        
        # Write CSV data
        df.to_csv(f, index=False)


def load_keypoints_csv_with_metadata(path: Path) -> tuple[list[Keypoint], Optional[dict]]:
    """Load keypoints from CSV with metadata preservation.
    
    Parameters
    ----------
    path : Path
        Input CSV file path.
    
    Returns
    -------
    keypoints : List[Keypoint]
        Loaded annotations.
    meta : dict or None
        Project-level metadata from comment header, or None.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.strip().split("\n")
    
    # Extract metadata from comment lines
    meta = None
    metadata_fields = []
    comment_lines = []
    data_start = 0
    
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            data_start = i
            break
        
        comment_lines.append(line)
        
        # Try to extract project metadata
        if "phage_annotator_meta:" in line:
            try:
                json_str = line.split("phage_annotator_meta:", 1)[1].strip()
                meta = json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass
        
        # Try to extract metadata field list
        if "metadata_fields:" in line:
            try:
                json_str = line.split("metadata_fields:", 1)[1].strip()
                metadata_fields = json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass
    
    # Read CSV data
    df = pd.read_csv(path, comment="#")
    
    keypoints = []
    for row in df.itertuples(index=False):
        # Standard fields
        kp = Keypoint(
            image_id=int(getattr(row, "image_id", -1)),
            image_name=str(getattr(row, "image_name", "")),
            t=int(getattr(row, "t", -1)),
            z=int(getattr(row, "z", -1)),
            y=float(getattr(row, "y", 0.0)),
            x=float(getattr(row, "x", 0.0)),
            label=str(getattr(row, "label", "phage")),
            annotation_id=str(getattr(row, "annotation_id", "")),
            image_key=str(getattr(row, "image_key", getattr(row, "image_name", ""))),
            source=str(getattr(row, "source", "csv")),
        )
        
        # Extract metadata
        metadata = {}
        for field in df.columns:
            if field not in STANDARD_COLUMNS and field != "image_key" and field != "source":
                value = getattr(row, field, None)
                
                # Try to deserialize JSON if it looks like JSON
                if isinstance(value, str) and value.startswith(("{", "[")):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass
                
                metadata[field] = value
        
        kp.meta = metadata
        keypoints.append(kp)
    
    return keypoints, meta
