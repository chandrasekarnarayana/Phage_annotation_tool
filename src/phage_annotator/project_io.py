"""Project/session I/O helpers for Phage Annotator.

Projects are lightweight JSON files (extension .phageproj) that reopen a set
of images, their annotation files, and a few UI settings. The schema is kept
backward compatible by tolerating missing fields and adding defaults.

Example
-------
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
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from phage_annotator.annotations import Keypoint, save_keypoints_json
from phage_annotator.roi_manager import roi_to_dict


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
) -> None:
    """Write a project JSON and persist per-image annotations.

    Parameters
    ----------
    path : pathlib.Path
        Output project file path.
    images : iterable
        Collection of images with ``path`` and ``interpret_3d_as`` attributes.
    annotations : dict[int, list[Keypoint]]
        Annotation lists keyed by image id.
    settings : dict
        Serialized UI settings to restore on load.

    Notes
    -----
    Per-image ``interpret_3d_as`` values are stored to preserve axis overrides.
    """
    images_payload: List[dict] = []
    payload = {
        "tool": "PhageAnnotator",
        "version": "0.9.0",
        "images": images_payload,
        "settings": settings,
    }
    for img in images:
        ann_path = Path(img.path).with_suffix(".annotations.json")
        save_keypoints_json(annotations.get(img.id, []), ann_path)
        images_payload.append(
            {
                "path": str(Path(img.path).resolve()),
                "annotations": str(ann_path.resolve()),
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
    temp_path = path.with_suffix('.phageproj.tmp')
    backup_path = path.with_suffix('.phageproj.backup')
    
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


def load_project(path: Path) -> Tuple[List[dict], Dict, Dict, Dict, Dict, Dict, Dict]:
    """Load a project JSON and return raw image entries, settings, and annotation paths.

    Returns
    -------
    images : list[dict]
        List of image entries with path/annotations and optional overrides.
    settings : dict
        Persisted UI settings.
    ann_map : dict[int, pathlib.Path]
        Mapping from image index to annotation path.
    roi_map : dict[int, list[dict]]
        ROIs by image index.
    thr_map : dict[int, dict]
        Threshold configs by image index.
    part_map : dict[int, dict]
        Particles configs by image index.
    import_map : dict[int, list[dict]]
        Annotation imports by image index.

    Notes
    -----
    Missing fields are tolerated for backward compatibility.
    Missing image files are logged but don't fail the load.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("tool") != "PhageAnnotator":
        raise ValueError("Not a PhageAnnotator project file.")
    images = data.get("images", [])
    settings = data.get("settings", {})
    ann_map = {
        idx: Path(entry.get("annotations"))
        for idx, entry in enumerate(images)
        if entry.get("annotations")
    }
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
    return images, settings, ann_map, roi_map, thr_map, part_map, import_map
