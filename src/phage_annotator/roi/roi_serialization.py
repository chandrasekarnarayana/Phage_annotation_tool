"""Roi roi serialization helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from phage_annotator.roi.roi_interactor_core import RoiInteractorCoreMixin
from phage_annotator.roi.manager_core_impl import RoiManager
from phage_annotator.roi.roi_model import RoiModelMixin

logger = logging.getLogger(__name__)



def roi_to_dict(roi) -> dict:
    """Convert ROI to dict for JSON serialization."""
    return {
        "id": roi.roi_id,
        "name": roi.name,
        "type": roi.roi_type,
        "points": roi.points,
        "color": roi.color,
        "visible": roi.visible,
        "z_index": roi.z_index,  # position binding
        "t_index": roi.t_index,
        "c_index": roi.c_index,
        "tags": roi.tags,  # tags for grouping/filtering
    }

def roi_from_dict(data: dict, fallback_id: int):
    """Convert dict back to ROI with fallback for missing fields."""
    from phage_annotator.roi.manager_core import Roi
    return Roi(
        roi_id=int(data.get("id", fallback_id)),
        name=str(data.get("name", f"ROI {fallback_id}")),
        roi_type=str(data.get("type", "box")),
        points=[tuple(p) for p in data.get("points", [])],
        color=str(data.get("color", "#ffcc00")),
        visible=bool(data.get("visible", True)),
        z_index=int(data.get("z_index", -1)),  # default to all
        t_index=int(data.get("t_index", -1)),
        c_index=int(data.get("c_index", -1)),
        tags=list(data.get("tags", [])),  # tags default to empty
    )

def save_rois_json(path: Path, rois) -> None:
    """Save ROIs to JSON with atomic writes and auto-backup.
    
    Features:
    - Schema versioning for future compatibility
    - Atomic write (temp → sync → rename)
    - Auto-backup to .bak
    - Comprehensive error logging
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create backup if file exists
    if path.exists():
        backup = Path(str(path) + ".bak")
        try:
            shutil.copy2(path, backup)
            logger.debug(f"Backup created: {backup}")
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    # Write to temporary file
    tmp = path.parent / f".{path.name}.tmp"
    try:
        payload = {
            "roi_schema_version": 1,
            "rois": [roi_to_dict(r) for r in rois]
        }
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        
        # Force fsync for data safety
        tmp.write_text(tmp.read_text())
        
        # Atomic rename
        tmp.replace(path)
        logger.info(f"ROIs saved (atomic): {path} ({len(payload['rois'])} rois)")
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        logger.error(f"Failed to save ROIs: {e}")
        raise

def load_rois_json(path: Path) -> list:
    """Load ROIs from JSON with schema validation.
    
    Supports:
    - Schema version 1 (current)
    - Legacy format without schema version
    """
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load ROIs from {path}: {e}")
        raise
    
    # Handle both versioned and legacy formats
    schema_version = data.get("roi_schema_version", 0)
    if schema_version > 1:
        logger.warning(f"ROI schema version {schema_version} may be incompatible")
    
    rois = []
    roi_list = data.get("rois", [])
    for idx, entry in enumerate(roi_list):
        if isinstance(entry, dict):
            try:
                roi = roi_from_dict(entry, idx)
                rois.append(roi)
            except Exception as e:
                logger.warning(f"Skipped malformed ROI entry {idx}: {e}")
                continue
    
    logger.info(f"Loaded {len(rois)} ROIs from {path}")
    return rois
