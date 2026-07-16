"""Project/session I/O helpers for Phage Annotator.

Projects are lightweight JSON files (extension .phageproj) that reopen a set
of images, their annotation files, and a few UI settings. The schema is kept
backward compatible by tolerating missing fields and adding defaults.

Example
-------
::

    {
      "tool": "PhageAnnotator",
      "version": "0.9.0",
      "images": [
        {"path": "/abs/path/img1.tif", "annotations": "/abs/path/img1.annotations.json"},
        {"path": "/abs/path/img2.tif", "annotations": "/abs/path/img2.annotations.json"}
      ],
      "settings": {"last_fov_index": 0, "last_support_index": 1, "fps_default": 10, "lut": "gray"}
    }
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from phage_annotator.annotation.core import (
    ANNOTATION_META_DEFAULTS,
    Keypoint,
    save_keypoints_json,
)
from phage_annotator.roi.manager import roi_to_dict

SCHEMA_VERSION = 3

DEFAULT_AXIS_CONTRACT = {
    "required_axes": ("Y", "X"),
    "supported_axes": ("T", "Z", "Y", "X", "C"),
    "heuristic_3d": "axis0<=5 => time else depth",
}


def _default_annotation_meta_schema() -> dict:
    """Handle the default annotation meta schema helper flow."""
    return {
        "fields": list(ANNOTATION_META_DEFAULTS.keys()),
        "defaults": dict(ANNOTATION_META_DEFAULTS),
    }


def migrate_project_payload(data: dict) -> dict:
    """Upgrade project payloads to the latest schema version in-place."""
    schema_version = int(data.get("schema_version", 1))
    if schema_version < 3:
        data.setdefault("axis_contract", DEFAULT_AXIS_CONTRACT)
        data.setdefault("annotation_meta_schema", _default_annotation_meta_schema())
        data["schema_version"] = SCHEMA_VERSION
    return data


def save_project(
    path: Path,
    images,
    annotations: Dict[int, List[Keypoint]],
    settings: Dict,
    display_mappings: Optional[Dict[int, Dict[str, object]]] = None,
    rois_by_image: Optional[Dict[int, List[object]]] = None,
    threshold_configs: Optional[Dict[int, Dict[str, object]]] = None,
    particles_configs: Optional[Dict[int, Dict[str, object]]] = None,
    annotation_imports: Optional[Dict[int, List[dict]]] = None,
    modality_manager: Optional[object] = None,
    channel_display_settings: Optional[Dict[str, object]] = None,
) -> None:
    """Write project JSON and save per-image annotations. Preserves axis overrides.
    
    Parameters
    ----------
    channel_display_settings : Dict, optional
        Per-channel display settings to persist in project file.
    modality_manager : ModalityManager, optional
        Multi-modality configuration to persist in project file.
    """
    images_payload: List[dict] = []
    payload = {
        "tool": "PhageAnnotator",
        "version": "0.9.0",
        "schema_version": SCHEMA_VERSION,
        "axis_contract": DEFAULT_AXIS_CONTRACT,
        "annotation_meta_schema": _default_annotation_meta_schema(),
        "images": images_payload,
        "settings": settings,
    }
    
    # Serialize channel display settings if present
    if channel_display_settings is not None:
        payload["channel_display_settings"] = channel_display_settings
    
    # Serialize modality manager if present
    if modality_manager is not None and hasattr(modality_manager, "to_dict"):
        payload["modality_manager"] = modality_manager.to_dict()
    
    for img in images:
        image_path = Path(img.path)
        ann_path = image_path.with_suffix(".annotations.json")
        include_provenance = bool(
            dict(settings or {}).get("feature_flags", {}).get("annotation_provenance_schema", False)
        )
        ann_meta = {
            "tool": "PhageAnnotator",
            "schema": "annotation_export.v1",
            "export_format": "json",
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "annotation_count": int(len(annotations.get(img.id, []))),
            "linked_image": {
                "image_id": int(getattr(img, "id", -1)),
                "image_name": str(image_path.name),
                "image_path": str(image_path.resolve()),
                "shape": list(getattr(img, "shape", ()) or ()),
                "dtype": str(getattr(img, "dtype", "")),
                "has_time": bool(getattr(img, "has_time", False)),
                "has_z": bool(getattr(img, "has_z", False)),
                "ome_axes": str(getattr(img, "ome_axes", "") or ""),
                "interpret_3d_as": str(getattr(img, "interpret_3d_as", "auto")),
            },
            "project_context": {"source": "project_save"},
        }
        save_keypoints_json(
            annotations.get(img.id, []),
            ann_path,
            meta=ann_meta,
            include_provenance=include_provenance,
        )
        images_payload.append(
            {
                "path": str(image_path.resolve()),
                "path_relative": str(image_path.relative_to(path.parent.resolve()))
                if image_path.resolve().is_relative_to(path.parent.resolve())
                else None,
                "image_name": str(image_path.name),
                "annotations": str(ann_path.resolve()),
                "annotations_relative": str(ann_path.relative_to(path.parent.resolve()))
                if ann_path.resolve().is_relative_to(path.parent.resolve())
                else None,
                "interpret_3d_as": getattr(img, "interpret_3d_as", "auto"),
                "display_mapping": (display_mappings.get(img.id, {}) if display_mappings else {}),
                "rois": (
                    [roi_to_dict(r) for r in rois_by_image.get(img.id, [])] if rois_by_image else []
                ),
                "threshold_config": (
                    threshold_configs.get(img.id, {}) if threshold_configs else {}
                ),
                "particles_config": (
                    particles_configs.get(img.id, {}) if particles_configs else {}
                ),
                "annotation_imports": (
                    annotation_imports.get(img.id, []) if annotation_imports else []
                ),
            }
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Atomic save: write to temp file first
    temp_path = path.with_suffix(".phageproj.tmp")
    backup_path = path.with_suffix(".phageproj.backup")

    try:
        # Write to temp file
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        # Create backup if project exists
        if path.exists():
            if backup_path.exists():
                backup_path.unlink()
            path.replace(backup_path)

        # Atomic rename
        temp_path.replace(path)

    except Exception as e:
        # Cleanup temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        raise IOError(f"Failed to save project: {e}") from e


def load_project(path: Path) -> Tuple[List[dict], Dict, Dict, Dict, Dict, Dict, Dict, Optional[Dict], Optional[Dict]]:
    """Load project JSON. Returns images, settings, annotation/ROI/threshold/particle/import maps, modality_manager, channel_display_settings.

    Handles backward compatibility gracefully - missing fields won't break the load.
    
    Returns
    -------
    images : List[dict]
        Image entries with paths and metadata.
    settings : Dict
        UI settings.
    ann_map : Dict[int, Path]
        Annotation file paths by image index.
    roi_map : Dict[int, List]
        ROI data by image index.
    thr_map : Dict[int, Dict]
        Threshold configs by image index.
    part_map : Dict[int, Dict]
        Particle configs by image index.
    import_map : Dict[int, List[dict]]
        Annotation imports by image index.
    modality_manager_data : Dict, optional
        Serialized modality manager data, or None if not present.
    channel_display_settings : Dict, optional
        Serialized channel display settings, or None if not present.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("tool") != "PhageAnnotator":
        raise ValueError("Not a PhageAnnotator project file.")
    data = migrate_project_payload(data)
    images = data.get("images", [])
    settings = data.get("settings", {})
    
    # Load channel display settings if present
    channel_display_settings = data.get("channel_display_settings", None)
    
    # Load modality manager if present
    modality_manager_data = data.get("modality_manager", None)
    
    ann_map: Dict[int, Path] = {}
    for idx, entry in enumerate(images):
        resolved = _resolve_annotation_path(path.parent, entry)
        if resolved is not None:
            ann_map[idx] = resolved
    roi_map = {
        idx: entry.get("rois", [])
        for idx, entry in enumerate(images)
        if entry.get("rois")
    }
    thr_map = {
        idx: entry.get("threshold_config", {})
        for idx, entry in enumerate(images)
        if entry.get("threshold_config")
    }
    part_map = {
        idx: entry.get("particles_config", {})
        for idx, entry in enumerate(images)
        if entry.get("particles_config")
    }
    import_map = {
        idx: entry.get("annotation_imports", [])
        for idx, entry in enumerate(images)
        if entry.get("annotation_imports")
    }
    return images, settings, ann_map, roi_map, thr_map, part_map, import_map, modality_manager_data, channel_display_settings


def _resolve_annotation_path(project_dir: Path, entry: dict) -> Optional[Path]:
    """Resolve annotation path for the current workflow."""
    raw = entry.get("annotations")
    if raw:
        raw_path = Path(str(raw))
        if raw_path.exists():
            return raw_path
    rel = entry.get("annotations_relative")
    if rel:
        rel_path = (project_dir / str(rel)).resolve()
        if rel_path.exists():
            return rel_path
    image_path = entry.get("path")
    if image_path:
        image_p = Path(str(image_path))
        sidecar = image_p.with_suffix(".annotations.json")
        if sidecar.exists():
            return sidecar
        stem = image_p.stem
        folder = image_p.parent
        if folder.exists():
            matches = sorted(folder.glob(f"{stem}.annotations*.json"))
            if matches:
                return matches[-1]
    return Path(str(raw)) if raw else None
