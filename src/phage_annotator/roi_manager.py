"""ROI manager data model and JSON I/O."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class Roi:
    """ROI definition in full-resolution coordinates."""

    roi_id: int
    name: str
    roi_type: str  # box|circle|polygon|polyline
    points: List[Tuple[float, float]]
    color: str = "#ffcc00"
    visible: bool = True


@dataclass
class RoiManager:
    """Container for image-scoped ROIs."""

    rois_by_image: Dict[int, List[Roi]] = field(default_factory=dict)
    active_roi_id: Optional[int] = None

    def list_rois(self, image_id: int) -> List[Roi]:
        return list(self.rois_by_image.get(image_id, []))

    def add_roi(self, image_id: int, roi: Roi) -> None:
        self.rois_by_image.setdefault(image_id, []).append(roi)
        self.active_roi_id = roi.roi_id

    def delete_roi(self, image_id: int, roi_id: int) -> None:
        rois = self.rois_by_image.get(image_id, [])
        self.rois_by_image[image_id] = [r for r in rois if r.roi_id != roi_id]
        if self.active_roi_id == roi_id:
            self.active_roi_id = None

    def get_active(self, image_id: int) -> Optional[Roi]:
        for roi in self.rois_by_image.get(image_id, []):
            if roi.roi_id == self.active_roi_id:
                return roi
        return None

    def set_active(self, roi_id: Optional[int]) -> None:
        self.active_roi_id = roi_id


def roi_to_dict(roi: Roi) -> dict:
    return {
        "id": roi.roi_id,
        "name": roi.name,
        "type": roi.roi_type,
        "points": roi.points,
        "color": roi.color,
        "visible": roi.visible,
    }


def roi_from_dict(data: dict, fallback_id: int) -> Roi:
    return Roi(
        roi_id=int(data.get("id", fallback_id)),
        name=str(data.get("name", f"ROI {fallback_id}")),
        roi_type=str(data.get("type", "box")),
        points=[tuple(p) for p in data.get("points", [])],
        color=str(data.get("color", "#ffcc00")),
        visible=bool(data.get("visible", True)),
    )


def save_rois_json(path: Path, rois: Iterable[Roi]) -> None:
    payload = {"rois": [roi_to_dict(r) for r in rois]}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_rois_json(path: Path) -> List[Roi]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    rois = []
    for idx, entry in enumerate(data.get("rois", [])):
        if isinstance(entry, dict):
            rois.append(roi_from_dict(entry, idx))
    return rois
