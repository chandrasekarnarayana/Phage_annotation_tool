"""Extracted method group 2 for SessionDataSource."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, TYPE_CHECKING

import numpy as np

from phage_annotator.data.sources import (
    Annotation,
    Calibration,
    ComprehensiveDataSource,
    ImageFrame,
    Projection,
)
from phage_annotator.io.data.transforms import (
    full_to_display as _full_to_display_yx,
    display_to_full as _display_to_full_yx,
)

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController



class SourceProtocolsOverlaysMixin:
    """Method group 2 extracted from SessionDataSource."""

    def get_annotations(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
        selected_only: bool = False,
    ) -> List[Annotation]:
        """Get annotations for a specific frame in display coordinates."""
        primary_id = self._session.session_state.active_primary_id
        annotations = self._session.session_state.annotations.get(primary_id, [])
        
        # Filter by frame
        filtered = [
            kp for kp in annotations
            if kp.image_id == primary_id
        ]
        
        # Filter by selection if requested
        if selected_only:
            filtered = [kp for kp in filtered if kp.selected]
        
        # Transform to display coordinates and convert to Annotation DTOs
        result = []
        for kp in filtered:
            # Transform coordinates
            full_coords = [(kp.x, kp.y)]
            display_coords = self.transform_full_to_display(
                full_coords, crop_rect, downsample
            )
            
            if not display_coords:
                continue
            
            x_disp, y_disp = display_coords[0]
            
            # Filter if outside crop rect
            if crop_rect is not None:
                if x_disp < 0 or y_disp < 0:
                    continue
                crop_x, crop_y, crop_w, crop_h = crop_rect
                if x_disp >= crop_w / downsample or y_disp >= crop_h / downsample:
                    continue
            
            result.append(Annotation(
                x=x_disp,
                y=y_disp,
                label=kp.label,
                color=kp.color,
                selected=kp.selected,
                t_idx=t_idx,
                z_idx=z_idx,
                metadata={"id": kp.id} if hasattr(kp, "id") else {},
            ))
        
        return result
    def get_annotation_count(
        self,
        t_idx: Optional[int] = None,
        z_idx: Optional[int] = None,
    ) -> int:
        """Get total annotation count, optionally filtered by frame."""
        primary_id = self._session.session_state.active_primary_id
        annotations = self._session.session_state.annotations.get(primary_id, [])
        
        if t_idx is None and z_idx is None:
            return len(annotations)
        
        # Filter by frame (simplified - assumes t_idx matches image_id)
        return len([kp for kp in annotations if kp.image_id == primary_id])
    def get_roi_overlays(
        self,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> List[Tuple[str, object, str]]:
        """Get ROI overlays in display coordinates."""
        roi = self._session.view_state.roi_spec
        if roi is None or roi.shape == "none":
            return []
        
        # Transform ROI to display coordinates
        if roi.shape == "box":
            # Transform corners
            corners = [
                (roi.x, roi.y),
                (roi.x + roi.w, roi.y + roi.h),
            ]
            display_corners = self.transform_full_to_display(
                corners, crop_rect, downsample
            )
            x1, y1 = display_corners[0]
            x2, y2 = display_corners[1]
            data = (x1, y1, x2 - x1, y2 - y1)
            color = "#00ff00"  # Green
            return [("box", data, color)]
        
        elif roi.shape == "circle":
            # Transform center and radius
            center_x = roi.x + roi.w / 2
            center_y = roi.y + roi.h / 2
            radius = roi.w / 2
            
            center_display = self.transform_full_to_display(
                [(center_x, center_y)], crop_rect, downsample
            )[0]
            radius_display = radius / downsample
            
            data = (*center_display, radius_display)
            color = "#00ff00"  # Green
            return [("circle", data, color)]
        
        return []
    def get_particle_overlays(
        self,
        t_idx: int,
        z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> List[Tuple[str, object, str, bool]]:
        """Get particle overlays in display coordinates."""
        # Session controller doesn't directly store particles in state
        # This would need to be wired up if particle rendering uses data sources
        # For now, return empty list (particles rendered separately)
        return []
    def get_calibration(self) -> Calibration:
        """Get pixel size calibration."""
        primary_id = self._session.session_state.active_primary_id
        state = self._session.session_state.image_states.get(primary_id)
        
        if state is None:
            return Calibration(
                pixel_size_um=1.0,
                unit="px",
                calibrated=False,
            )
        
        pixel_size_um = state.pixel_size_um
        calibrated = pixel_size_um > 0
        unit = "µm" if calibrated else "px"
        
        return Calibration(
            pixel_size_um=pixel_size_um if calibrated else 1.0,
            unit=unit,
            calibrated=calibrated,
        )
    def _get_primary_image(self):
        """Get the active primary LazyImage."""
        primary_id = self._session.session_state.active_primary_id
        images = self._session.session_state.images
        if 0 <= primary_id < len(images):
            return images[primary_id]
        return None
    def _get_support_image(self):
        """Get the active support LazyImage."""
        support_id = self._session.session_state.active_support_id
        images = self._session.session_state.images
        if 0 <= support_id < len(images):
            return images[support_id]
        return None
    def _extract_frame_direct(self, img, t_idx: int, z_idx: int) -> np.ndarray:
        """Extract a 2D frame from LazyImage."""
        # Handle different dimensionalities
        if len(img.shape) == 2:
            return np.asarray(img.get_full_array())
        elif len(img.shape) == 3:
            if img.has_time and not img.has_z:
                return np.asarray(img.get_full_array()[t_idx])
            elif img.has_z and not img.has_time:
                return np.asarray(img.get_full_array()[z_idx])
            else:
                return np.asarray(img.get_full_array()[t_idx])
        else:  # 4D
            return np.asarray(img.get_full_array()[t_idx, z_idx])
    def _compute_projection(
        self,
        img,
        projection_type: str,
        axes: Tuple[int, ...],
    ) -> np.ndarray:
        """Compute projection on-the-fly if no cache available."""
        data = np.asarray(img.get_full_array())
        
        if projection_type == "mean":
            return np.mean(data, axis=axes)
        elif projection_type == "median":
            return np.median(data, axis=axes)
        elif projection_type == "std":
            return np.std(data, axis=axes)
        elif projection_type == "min":
            return np.min(data, axis=axes)
        elif projection_type == "max":
            return np.max(data, axis=axes)
        elif projection_type == "sum":
            return np.sum(data, axis=axes)
        else:
            raise ValueError(f"Unknown projection type: {projection_type}")
