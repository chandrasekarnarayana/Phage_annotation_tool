"""Image loading, metadata, and calibration helpers for the session controller."""

from __future__ import annotations

import pathlib
from typing import Iterable, List, Optional, Tuple

import numpy as np

from phage_annotator.calibration import CalibrationState, resolve_calibration
from phage_annotator.io import read_metadata_bundle
from phage_annotator.session_state import ImageState


class SessionImageMixin:
    """Mixin for image loading, metadata, and calibration helpers."""

    def _build_image_state(self, img: "LazyImage") -> ImageState:
        """Create an ImageState from LazyImage metadata."""
        if len(img.shape) == 2:
            dims = (1, 1, img.shape[0], img.shape[1])
        elif len(img.shape) == 3:
            if img.has_time and not img.has_z:
                dims = (img.shape[0], 1, img.shape[1], img.shape[2])
            elif img.has_z and not img.has_time:
                dims = (1, img.shape[0], img.shape[1], img.shape[2])
            else:
                dims = (1, 1, img.shape[1], img.shape[2])
        else:
            dims = (img.shape[0], img.shape[1], img.shape[2], img.shape[3])
        return ImageState(
            image_id=img.id,
            path=img.path,
            dims=dims,
            axis_mode=img.interpret_3d_as,
            has_time=img.has_time,
            has_z=img.has_z,
            pixel_size_um=getattr(img, "pixel_size_um", 0.0),
            memmap_flag=bool(
                getattr(img, "array", None) is not None and isinstance(img.array, np.memmap)
            ),
            metadata_summary=dict(getattr(img, "metadata_summary", {}) or {}),
        )

    def refresh_image_state(self, img: "LazyImage") -> None:
        """Rebuild ImageState metadata after loading or axis changes."""
        self.session_state.image_states[img.id] = self._build_image_state(img)
        if hasattr(self, "state_changed"):
            self.state_changed.emit()

    def get_metadata_summary(self, image_id: int) -> dict:
        """Return cached metadata summary for an image."""
        state = self.session_state.image_states.get(image_id)
        return dict(state.metadata_summary) if state else {}

    def resolve_calibration_state(
        self,
        image_id: int,
        user_value_um_per_px: Optional[float],
        project_default_um_per_px: Optional[float],
    ) -> CalibrationState:
        """Resolve the calibration state for an image."""
        summary = self.get_metadata_summary(image_id)
        return resolve_calibration(summary, user_value_um_per_px, project_default_um_per_px)

    def load_metadata_bundle(self, image_id: int) -> object:
        """Load or return cached full metadata bundle for an image."""
        if image_id < 0 or image_id >= len(self.session_state.images):
            return {}
        img = self.session_state.images[image_id]
        cached = self._metadata_cache.get(img.path)
        if cached is not None:
            return cached
        bundle = read_metadata_bundle(img.path)
        self._metadata_cache[img.path] = bundle
        return bundle

    def set_images(self, images: List["LazyImage"]) -> None:
        """Replace the loaded images and reset dependent state."""
        if not images:
            raise ValueError("No images provided.")
        for idx, img in enumerate(images):
            img.id = idx
        self.session_state.images = images
        self.session_state.annotations = {img.id: [] for img in images}
        self.session_state.annotations_loaded = {img.id: False for img in images}
        self.session_state.annotation_index = {}
        self.session_state.image_states = {img.id: self._build_image_state(img) for img in images}
        self.session_state.active_primary_id = 0
        self.session_state.active_support_id = 0 if len(images) == 1 else 1
        if hasattr(self, "state_changed"):
            self.state_changed.emit()
        if hasattr(self, "annotations_changed"):
            self.annotations_changed.emit()

    def add_images(self, images: List["LazyImage"]) -> None:
        """Append images to the session and initialize empty annotations."""
        if not images:
            return
        start_idx = len(self.session_state.images)
        for offset, img in enumerate(images):
            img.id = start_idx + offset
            self.session_state.images.append(img)
            self.session_state.annotations[img.id] = []
            self.session_state.annotations_loaded[img.id] = False
            self.session_state.image_states[img.id] = self._build_image_state(img)
        if hasattr(self, "state_changed"):
            self.state_changed.emit()
        if hasattr(self, "annotations_changed"):
            self.annotations_changed.emit()

    def retain_single_image(self, keep_idx: int) -> None:
        """Keep only the selected image and its annotations."""
        if keep_idx < 0 or keep_idx >= len(self.session_state.images):
            return
        keep_img = self.session_state.images[keep_idx]
        old_id = keep_img.id
        keep_annotations = self.session_state.annotations.get(old_id, [])
        keep_img.id = 0
        self.session_state.images = [keep_img]
        self.session_state.annotations = {0: keep_annotations}
        self.session_state.annotation_index = {
            0: self.session_state.annotation_index.get(old_id, [])
        }
        self.session_state.annotations_loaded = {
            0: self.session_state.annotations_loaded.get(old_id, False)
        }
        self.session_state.image_states = {0: self._build_image_state(keep_img)}
        self.session_state.active_primary_id = 0
        self.session_state.active_support_id = 0
        if hasattr(self, "state_changed"):
            self.state_changed.emit()
        if hasattr(self, "annotations_changed"):
            self.annotations_changed.emit()

    def set_primary(self, index: int) -> None:
        """Set the active primary image index."""
        if index < 0 or index >= len(self.session_state.images):
            return
        if self.session_state.active_primary_id == index:
            return
        self.session_state.active_primary_id = index
        if hasattr(self, "state_changed"):
            self.state_changed.emit()

    def set_support(self, index: int) -> None:
        """Set the active support image index."""
        if index < 0 or index >= len(self.session_state.images):
            return
        if self.session_state.active_support_id == index:
            return
        self.session_state.active_support_id = index
        if hasattr(self, "state_changed"):
            self.state_changed.emit()

    def set_axis_interpretation(self, image_id: int, mode: str) -> None:
        """Set 3D axis interpretation for a specific image."""
        if image_id not in self.session_state.image_states:
            return
        for img in self.session_state.images:
            if img.id == image_id:
                img.interpret_3d_as = mode
                if mode != "auto":
                    img.axis_auto_used = False
                    img.axis_auto_mode = None
                else:
                    if img.ome_axes is None and len(img.shape) == 3:
                        axis0 = img.shape[0]
                        img.axis_auto_used = True
                        img.axis_auto_mode = "time" if axis0 <= 5 else "depth"
                    else:
                        img.axis_auto_used = False
                        img.axis_auto_mode = None
                break
        state = self.session_state.image_states.get(image_id)
        if state is not None:
            self.session_state.image_states[image_id] = ImageState(
                image_id=state.image_id,
                path=state.path,
                dims=state.dims,
                axis_mode=mode,
                has_time=state.has_time,
                has_z=state.has_z,
                pixel_size_um=state.pixel_size_um,
                memmap_flag=state.memmap_flag,
                metadata_summary=state.metadata_summary,
            )
        if hasattr(self, "state_changed"):
            self.state_changed.emit()
