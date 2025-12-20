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
    """Container for image-scoped ROIs.
    
    P5.2 Enhancement: Supports multi-image ROI operations like copying ROI
    across images and managing ROI templates for bulk preset application.
    """

    rois_by_image: Dict[int, List[Roi]] = field(default_factory=dict)
    active_roi_id: Optional[int] = None
    roi_templates: Dict[str, Roi] = field(default_factory=dict)  # P5.2: ROI templates

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

    def copy_roi_to_images(self, source_image_id: int, roi_id: int, target_image_ids: Iterable[int]) -> int:
        """Copy a ROI from source to target images, preserving shape and position.
        
        P5.2: Multi-image ROI feature. Returns count of successfully copied ROIs.
        
        Parameters
        ----------
        source_image_id : int
            Image ID containing the source ROI
        roi_id : int
            ROI ID to copy
        target_image_ids : Iterable[int]
            List of image IDs to copy the ROI to
            
        Returns
        -------
        int
            Count of successfully copied ROIs
        """
        source_roi = self.get_active(source_image_id)
        if source_roi is None or source_roi.roi_id != roi_id:
            # Search all ROIs in source image
            for roi in self.list_rois(source_image_id):
                if roi.roi_id == roi_id:
                    source_roi = roi
                    break
        
        if source_roi is None:
            return 0
        
        copy_count = 0
        for target_id in target_image_ids:
            if target_id == source_image_id:
                continue  # Skip source image
            
            # Create new ROI with same shape but new ID
            new_roi_id = max(
                [r.roi_id for image_rois in self.rois_by_image.values() for r in image_rois],
                default=0
            ) + 1
            new_roi = Roi(
                roi_id=new_roi_id,
                name=f"{source_roi.name} (copy)",
                roi_type=source_roi.roi_type,
                points=list(source_roi.points),  # Deep copy points
                color=source_roi.color,
                visible=source_roi.visible,
            )
            self.add_roi(target_id, new_roi)
            copy_count += 1
        
        return copy_count

    def save_roi_template(self, name: str, roi: Roi) -> None:
        """Save a ROI as a template for reuse across images.
        
        P5.2: ROI template feature for bulk preset application.
        
        Parameters
        ----------
        name : str
            Template name (e.g., "Cell center", "Nucleus")
        roi : Roi
            ROI to save as template
        """
        template = Roi(
            roi_id=-1,  # Sentinel value for templates
            name=name,
            roi_type=roi.roi_type,
            points=list(roi.points),
            color=roi.color,
            visible=roi.visible,
        )
        self.roi_templates[name] = template

    def get_roi_template(self, name: str) -> Optional[Roi]:
        """Retrieve a saved ROI template by name."""
        return self.roi_templates.get(name)

    def apply_template_to_image(self, template_name: str, image_id: int) -> bool:
        """Apply a ROI template to an image.
        
        P5.2: Bulk preset application via templates.
        
        Returns
        -------
        bool
            True if successfully applied, False if template not found
        """
        template = self.get_roi_template(template_name)
        if template is None:
            return False
        
        new_roi_id = max(
            [r.roi_id for image_rois in self.rois_by_image.values() for r in image_rois],
            default=0
        ) + 1
        new_roi = Roi(
            roi_id=new_roi_id,
            name=template.name,
            roi_type=template.roi_type,
            points=list(template.points),
            color=template.color,
            visible=template.visible,
        )
        self.add_roi(image_id, new_roi)
        return True

    def list_templates(self) -> List[str]:
        """Return list of available ROI template names."""
        return list(self.roi_templates.keys())


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
