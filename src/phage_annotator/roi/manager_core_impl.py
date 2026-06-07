"""Roi manager core impl helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RoiManager:
    """Manages ROIs per image, including templates for bulk operations."""

    rois_by_image: Dict[int, List] = field(default_factory=dict)
    active_roi_id: Optional[int] = None
    roi_templates: Dict[str, object] = field(default_factory=dict)
    _next_roi_id: int = field(default=1, init=False)
    _undo_stack: List = field(default_factory=list, init=False)
    _redo_stack: List = field(default_factory=list, init=False)

    def _new_roi_id(self) -> int:
        """Document the new_roi_id flow."""
        roi_id = self._next_roi_id
        self._next_roi_id += 1
        return roi_id

    def execute_command(self, command) -> bool:
        """Document the execute_command flow."""
        if command.execute():
            self._undo_stack.append(command)
            self._redo_stack.clear()
            return True
        return False

    def can_undo(self) -> bool:
        """Document the can_undo flow."""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Document the can_redo flow."""
        return len(self._redo_stack) > 0

    def undo(self) -> bool:
        """Document the undo flow."""
        if not self._undo_stack:
            return False
        command = self._undo_stack.pop()
        if command.undo():
            self._redo_stack.append(command)
            return True
        return False

    def redo(self) -> bool:
        """Document the redo flow."""
        if not self._redo_stack:
            return False
        command = self._redo_stack.pop()
        if command.redo():
            self._undo_stack.append(command)
            return True
        return False

    def list_rois(self, image_id: int) -> list:
        """Document the list_rois flow."""
        return list(self.rois_by_image.get(image_id, []))

    def add_roi(self, image_id: int, roi) -> None:
        """Document the add_roi flow."""
        if roi.roi_id >= self._next_roi_id:
            self._next_roi_id = roi.roi_id + 1
        self.rois_by_image.setdefault(image_id, []).append(roi)
        self.active_roi_id = roi.roi_id
        logger.info(f"ROI added: id={roi.roi_id}, name={roi.name}, type={roi.roi_type}, image_id={image_id}")

    def delete_roi(self, image_id: int, roi_id: int) -> None:
        """Document the delete_roi flow."""
        rois = self.rois_by_image.get(image_id, [])
        self.rois_by_image[image_id] = [r for r in rois if r.roi_id != roi_id]
        if self.active_roi_id == roi_id:
            self.active_roi_id = None
        logger.info(f"ROI deleted: id={roi_id}, image_id={image_id}")

    def get_active(self, image_id: int):
        """Document the get_active flow."""
        for roi in self.rois_by_image.get(image_id, []):
            if roi.roi_id == self.active_roi_id:
                return roi
        return None

    def set_active(self, roi_id: Optional[int]) -> None:
        """Document the set_active flow."""
        self.active_roi_id = roi_id
        if roi_id is not None:
            logger.debug(f"Active ROI set: {roi_id}")
        else:
            logger.debug("Active ROI cleared (deselected)")

    def get_roi_by_id(self, roi_id: int):
        """Document the get_roi_by_id flow."""
        for rois in self.rois_by_image.values():
            for roi in rois:
                if roi.roi_id == roi_id:
                    return roi
        return None

    def filter_rois_by_position(self, image_id: int, z: int = -1, t: int = -1, c: int = -1) -> list:
        """Document the filter_rois_by_position flow."""
        filtered = []
        for roi in self.list_rois(image_id):
            z_match = (roi.z_index == -1 or z == -1 or roi.z_index == z)
            t_match = (roi.t_index == -1 or t == -1 or roi.t_index == t)
            c_match = (roi.c_index == -1 or c == -1 or roi.c_index == c)
            if z_match and t_match and c_match:
                filtered.append(roi)
        return filtered

    def set_roi_position(self, roi_id: int, z: int = -1, t: int = -1, c: int = -1) -> bool:
        """Document the set_roi_position flow."""
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
        """Document the copy_roi_to_images flow."""
        from phage_annotator.roi.manager_core import Roi
        source_roi = None
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
                continue
            new_roi = Roi(
                roi_id=self._new_roi_id(),
                name=f"{source_roi.name} (copy)",
                roi_type=source_roi.roi_type,
                points=list(source_roi.points),
                color=source_roi.color,
                visible=source_roi.visible,
                z_index=source_roi.z_index,
                t_index=source_roi.t_index,
                c_index=source_roi.c_index)
            self.add_roi(target_id, new_roi)
            copy_count += 1
        logger.info(f"ROI {roi_id} copied to {copy_count} images")
        return copy_count

    def save_roi_template(self, name: str, roi) -> None:
        """Document the save_roi_template flow."""
        from phage_annotator.roi.manager_core import Roi
        template = Roi(
            roi_id=-1,
            name=name,
            roi_type=roi.roi_type,
            points=list(roi.points),
            color=roi.color,
            visible=roi.visible,
            z_index=roi.z_index,
            t_index=roi.t_index,
            c_index=roi.c_index)
        self.roi_templates[name] = template
        logger.info(f"ROI template saved: {name} (type={roi.roi_type})")

    def get_roi_template(self, name: str):
        """Document the get_roi_template flow."""
        return self.roi_templates.get(name)

    def apply_template_to_image(self, template_name: str, image_id: int) -> bool:
        """Document the apply_template_to_image flow."""
        from phage_annotator.roi.manager_core import Roi
        template = self.get_roi_template(template_name)
        if template is None:
            logger.warning(f"Template not found: {template_name}")
            return False
        new_roi = Roi(
            roi_id=self._new_roi_id(),
            name=template.name,
            roi_type=template.roi_type,
            points=list(template.points),
            color=template.color,
            visible=template.visible,
            z_index=template.z_index,
            t_index=template.t_index,
            c_index=template.c_index)
        self.add_roi(image_id, new_roi)
        logger.info(f"Template {template_name} applied to image {image_id}")
        return True

    def list_templates(self) -> List[str]:
        """Document the list_templates flow."""
        return list(self.roi_templates.keys())

    def get_all_tags(self, image_id: int) -> List[str]:
        """Document the get_all_tags flow."""
        all_tags: set = set()
        for roi in self.list_rois(image_id):
            all_tags.update(roi.tags)
        return sorted(list(all_tags))

    def filter_rois_by_tag(self, image_id: int, tag: str) -> list:
        """Document the filter_rois_by_tag flow."""
        return [roi for roi in self.list_rois(image_id) if tag in roi.tags]

    def filter_rois_by_tags(self, image_id: int, tags: List[str], match_all: bool = False) -> list:
        """Document the filter_rois_by_tags flow."""
        if not tags:
            return self.list_rois(image_id)
        if match_all:
            return [roi for roi in self.list_rois(image_id) if all(tag in roi.tags for tag in tags)]
        return [roi for roi in self.list_rois(image_id) if any(tag in roi.tags for tag in tags)]
