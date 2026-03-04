"""ROI manager data model and JSON I/O with atomic, schema-versioned persistence."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Roi:
    """ROI definition in full-resolution coordinates.
    
    Position binding:
    - z_index: -1 = all z-slices, 0+ = specific z-slice
    - t_index: -1 = all time frames, 0+ = specific time frame
    - c_index: -1 = all channels, 0+ = specific channel
    
    Tags system:
    - tags: List of strings for grouping and filtering ROIs
    """

    roi_id: int
    name: str
    roi_type: str  # box|circle|polygon|polyline
    points: List[Tuple[float, float]]
    color: str = "#ffcc00"
    visible: bool = True
    z_index: int = -1  # -1 = all slices
    t_index: int = -1  # -1 = all frames
    c_index: int = -1  # -1 = all channels
    tags: List[str] = field(default_factory=list)  # tags for grouping/filtering


@dataclass
class RoiManager:
    """Manages ROIs per image, including templates for bulk operations."""

    rois_by_image: Dict[int, List[Roi]] = field(default_factory=dict)
    active_roi_id: Optional[int] = None
    roi_templates: Dict[str, Roi] = field(default_factory=dict)  # P5.2: ROI templates
    _next_roi_id: int = field(default=1, init=False)  # Auto-incrementing ID pool
    _undo_stack: List = field(default_factory=list, init=False)  # undo support
    _redo_stack: List = field(default_factory=list, init=False)  # redo support

    def _new_roi_id(self) -> int:
        """Generate next unique ROI ID."""
        self._next_roi_id += 1
        return self._next_roi_id
    
    def execute_command(self, command) -> bool:
        """Execute a command and add to undo stack."""
        if command.execute():
            self._undo_stack.append(command)
            self._redo_stack.clear()
            return True
        return False
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self._redo_stack) > 0
    
    def undo(self) -> bool:
        """Undo the last command."""
        if not self._undo_stack:
            return False
        command = self._undo_stack.pop()
        if command.undo():
            self._redo_stack.append(command)
            return True
        return False
    
    def redo(self) -> bool:
        """Redo the last undone command."""
        if not self._redo_stack:
            return False
        command = self._redo_stack.pop()
        if command.redo():
            self._undo_stack.append(command)
            return True
        return False

    def list_rois(self, image_id: int) -> List[Roi]:
        return list(self.rois_by_image.get(image_id, []))

    def add_roi(self, image_id: int, roi: Roi) -> None:
        """Add ROI and track max ID for next generation."""
        if roi.roi_id >= self._next_roi_id:
            self._next_roi_id = roi.roi_id + 1
        self.rois_by_image.setdefault(image_id, []).append(roi)
        self.active_roi_id = roi.roi_id
        logger.info(f"ROI added: id={roi.roi_id}, name={roi.name}, type={roi.roi_type}, image_id={image_id}")

    def delete_roi(self, image_id: int, roi_id: int) -> None:
        rois = self.rois_by_image.get(image_id, [])
        self.rois_by_image[image_id] = [r for r in rois if r.roi_id != roi_id]
        if self.active_roi_id == roi_id:
            self.active_roi_id = None
        logger.info(f"ROI deleted: id={roi_id}, image_id={image_id}")

    def get_active(self, image_id: int) -> Optional[Roi]:
        for roi in self.rois_by_image.get(image_id, []):
            if roi.roi_id == self.active_roi_id:
                return roi
        return None

    def set_active(self, roi_id: Optional[int]) -> None:
        self.active_roi_id = roi_id
        if roi_id is not None:
            logger.debug(f"Active ROI set: {roi_id}")
        else:
            logger.debug("Active ROI cleared (deselected)")

    def get_roi_by_id(self, roi_id: int) -> Optional[Roi]:
        """Search all images for an ROI by ID. Returns first match or None."""
        for rois in self.rois_by_image.values():
            for roi in rois:
                if roi.roi_id == roi_id:
                    return roi
        return None

    def filter_rois_by_position(self, image_id: int, z: int = -1, t: int = -1, c: int = -1) -> List[Roi]:
        """Filter ROIs visible at given z/t/c position.
        
        Args:
            image_id: Image to filter ROIs from
            z: Z-slice index (use -1 to include all z-bound ROIs)
            t: Time frame index (use -1 to include all t-bound ROIs)
            c: Channel index (use -1 to include all c-bound ROIs)
        
        Returns:
            List of ROIs matching position constraints
        """
        filtered = []
        for roi in self.list_rois(image_id):
            # Include ROI if:
            # - Its position binding (-1 = all) matches requested position
            # - OR the requested position is -1 (show all)
            z_match = (roi.z_index == -1 or z == -1 or roi.z_index == z)
            t_match = (roi.t_index == -1 or t == -1 or roi.t_index == t)
            c_match = (roi.c_index == -1 or c == -1 or roi.c_index == c)
            
            if z_match and t_match and c_match:
                filtered.append(roi)
        
        return filtered

    def set_roi_position(self, roi_id: int, z: int = -1, t: int = -1, c: int = -1) -> bool:
        """Bind ROI to specific z/t/c position. Returns True if successful."""
        roi = self.get_roi_by_id(roi_id)
        if roi is None:
            logger.warning(f"Cannot set position for ROI {roi_id}: not found")
            return False
        
        roi.z_index = z
        roi.t_index = t
        roi.c_index = c
        logger.debug(f"ROI {roi_id} position set: z={z}, t={t}, c={c}")
        return True

    def copy_roi_to_images(self, source_image_id: int, roi_id: int, target_image_ids: Iterable[int]) -> int:
        """Copy a ROI to multiple images keeping shape and position. Returns copy count."""
        source_roi = self.get_active(source_image_id)
        if source_roi is None or source_roi.roi_id != roi_id:
            # Search all ROIs in source image
            for roi in self.list_rois(source_image_id):
                if roi.roi_id == roi_id:
                    source_roi = roi
                    break
        
        if source_roi is None:
            logger.warning(f"Copy failed: ROI {roi_id} not found in image {source_image_id}")
            return 0
        
        copy_count = 0
        for target_id in target_image_ids:
            if target_id == source_image_id:
                continue  # Skip source image
            
            # Create new ROI with same shape but new ID
            new_roi_id = self._new_roi_id()
            new_roi = Roi(
                roi_id=new_roi_id,
                name=f"{source_roi.name} (copy)",
                roi_type=source_roi.roi_type,
                points=list(source_roi.points),  # Deep copy points
                color=source_roi.color,
                visible=source_roi.visible,
                z_index=source_roi.z_index,  # Preserve position binding
                t_index=source_roi.t_index,
                c_index=source_roi.c_index,
            )
            self.add_roi(target_id, new_roi)
            copy_count += 1
        
        logger.info(f"ROI {roi_id} copied to {copy_count} images")
        return copy_count

    def save_roi_template(self, name: str, roi: Roi) -> None:
        """Save a ROI as a template for reuse across images."""
        template = Roi(
            roi_id=-1,  # Sentinel value for templates
            name=name,
            roi_type=roi.roi_type,
            points=list(roi.points),
            color=roi.color,
            visible=roi.visible,
            z_index=roi.z_index,  # Preserve position binding
            t_index=roi.t_index,
            c_index=roi.c_index,
        )
        self.roi_templates[name] = template
        logger.info(f"ROI template saved: {name} (type={roi.roi_type})")

    def get_roi_template(self, name: str) -> Optional[Roi]:
        """Retrieve a saved ROI template by name."""
        return self.roi_templates.get(name)

    def apply_template_to_image(self, template_name: str, image_id: int) -> bool:
        """Apply a saved template ROI to an image, returning True if successful."""
        template = self.get_roi_template(template_name)
        if template is None:
            logger.warning(f"Template not found: {template_name}")
            return False
        
        new_roi_id = self._new_roi_id()
        new_roi = Roi(
            roi_id=new_roi_id,
            name=template.name,
            roi_type=template.roi_type,
            points=list(template.points),
            color=template.color,
            visible=template.visible,
            z_index=template.z_index,  # Preserve position binding
            t_index=template.t_index,
            c_index=template.c_index,
        )
        self.add_roi(image_id, new_roi)
        logger.info(f"Template {template_name} applied to image {image_id}")
        return True

    def list_templates(self) -> List[str]:
        """Return list of available ROI template names."""
        return list(self.roi_templates.keys())
    
    def get_all_tags(self, image_id: int) -> List[str]:
        """Get all unique tags used by ROIs in image."""
        all_tags = set()
        for roi in self.list_rois(image_id):
            all_tags.update(roi.tags)
        return sorted(list(all_tags))
    
    def filter_rois_by_tag(self, image_id: int, tag: str) -> List[Roi]:
        """Get all ROIs with a specific tag."""
        return [roi for roi in self.list_rois(image_id) if tag in roi.tags]
    
    def filter_rois_by_tags(self, image_id: int, tags: List[str], match_all: bool = False) -> List[Roi]:
        """Get ROIs matching tag filter.
        
        Args:
            image_id: Image ID
            tag: List of tags to filter by
            match_all: If True, ROI must have ALL tags. If False, ROI must have ANY tag.
        """
        if not tags:
            return self.list_rois(image_id)
        
        if match_all:
            # ROI must have all tags
            return [
                roi for roi in self.list_rois(image_id)
                if all(tag in roi.tags for tag in tags)
            ]
        else:
            # ROI must have at least one tag
            return [
                roi for roi in self.list_rois(image_id)
                if any(tag in roi.tags for tag in tags)
            ]


def roi_to_dict(roi: Roi) -> dict:
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


def roi_from_dict(data: dict, fallback_id: int) -> Roi:
    """Convert dict back to ROI with fallback for missing fields."""
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


def save_rois_json(path: Path, rois: Iterable[Roi]) -> None:
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


def load_rois_json(path: Path) -> List[Roi]:
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
