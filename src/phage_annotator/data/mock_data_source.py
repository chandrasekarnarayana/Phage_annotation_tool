"""Mock data source for testing render/data separation."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np

from phage_annotator.data.source_base import (
    Annotation, Calibration, ComprehensiveDataSource, ImageFrame, Projection,
)


class MockDataSource(ComprehensiveDataSource):
    """Synthetic data source providing predictable data for isolated testing."""

    def __init__(
        self,
        shape: Tuple[int, int, int, int] = (10, 1, 100, 100),
        fill_value: float = 128.0,
        num_annotations: int = 5,
    ) -> None:
        """Document the init flow."""
        self._shape = shape
        self._fill_value = fill_value
        self._num_annotations = num_annotations
        self._annotations = self._generate_annotations()

    def get_shape(self) -> Tuple[int, int, int, int]:
        """Document the get_shape flow."""
        return self._shape

    def get_dtype(self) -> np.dtype:
        """Document the get_dtype flow."""
        return np.dtype(np.float32)

    def is_available(self) -> bool:
        """Document the is_available flow."""
        return True

    def get_frame(
        self, t_idx: int, z_idx: int,
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> ImageFrame:
        """Document the get_frame flow."""
        t, z, h, w = self._shape
        data = np.full((h, w), self._fill_value, dtype=np.float32)
        data[t_idx % h, :] = self._fill_value * 1.5
        data[:, z_idx % w] = self._fill_value * 1.5
        if crop_rect is not None:
            x, y, cw, ch = crop_rect
            data = data[int(y):int(y+ch), int(x):int(x+cw)]
        if downsample > 1:
            data = data[::downsample, ::downsample]
        return ImageFrame(data=data, t_idx=t_idx, z_idx=z_idx, full_shape=(h, w),
                          display_shape=data.shape, crop_rect=crop_rect, downsample_factor=downsample)

    def get_projection(
        self, projection_type: str, axes: Tuple[int, ...],
        crop_rect: Optional[Tuple[float, float, float, float]] = None,
        downsample: int = 1,
    ) -> Projection:
        """Document the get_projection flow."""
        t, z, h, w = self._shape
        value_map = {"mean": self._fill_value, "std": self._fill_value * 0.1,
                     "max": self._fill_value * 1.5}
        value = value_map.get(projection_type, self._fill_value)
        data = np.full((h, w), value, dtype=np.float32)
        if crop_rect is not None:
            x, y, cw, ch = crop_rect
            data = data[int(y):int(y+ch), int(x):int(x+cw)]
        if downsample > 1:
            data = data[::downsample, ::downsample]
        return Projection(data=data, projection_type=projection_type, axes=axes, full_shape=(h, w))

    def get_support_frame(self, t_idx: int, z_idx: int,
                          crop_rect: Optional[Tuple[float, float, float, float]] = None,
                          downsample: int = 1) -> Optional[ImageFrame]:
        """Document the get_support_frame flow."""
        return None

    def transform_full_to_display(
        self, coords: Sequence[Tuple[float, float]],
        crop_rect: Optional[Tuple[float, float, float, float]], downsample: int,
    ) -> List[Tuple[float, float]]:
        """Document the transform_full_to_display flow."""
        if crop_rect is None:
            return [(x / downsample, y / downsample) for x, y in coords]
        cx, cy, _, _ = crop_rect
        return [((x - cx) / downsample, (y - cy) / downsample) for x, y in coords]

    def transform_display_to_full(
        self, coords: Sequence[Tuple[float, float]],
        crop_rect: Optional[Tuple[float, float, float, float]], downsample: int,
    ) -> List[Tuple[float, float]]:
        """Document the transform_display_to_full flow."""
        if crop_rect is None:
            return [(x * downsample, y * downsample) for x, y in coords]
        cx, cy, _, _ = crop_rect
        return [(x * downsample + cx, y * downsample + cy) for x, y in coords]

    def get_annotations(self, t_idx: int, z_idx: int,
                        crop_rect: Optional[Tuple[float, float, float, float]] = None,
                        downsample: int = 1, selected_only: bool = False) -> List[Annotation]:
        """Document the get_annotations flow."""
        annotations = [a for a in self._annotations if not selected_only or a.selected]
        result = []
        for ann in annotations:
            display_coords = self.transform_full_to_display([(ann.x, ann.y)], crop_rect, downsample)
            x_disp, y_disp = display_coords[0]
            if crop_rect is not None:
                _, _, cw, ch = crop_rect
                if x_disp < 0 or y_disp < 0 or x_disp >= cw / downsample or y_disp >= ch / downsample:
                    continue
            result.append(Annotation(x=x_disp, y=y_disp, label=ann.label, color=ann.color,
                                     selected=ann.selected, t_idx=t_idx, z_idx=z_idx,
                                     metadata=ann.metadata))
        return result

    def get_annotation_count(self, t_idx: Optional[int] = None,
                             z_idx: Optional[int] = None) -> int:
        """Document the get_annotation_count flow."""
        return len(self._annotations)

    def get_roi_overlays(self, crop_rect: Optional[Tuple[float, float, float, float]] = None,
                         downsample: int = 1) -> List[Tuple[str, object, str]]:
        """Document the get_roi_overlays flow."""
        _, _, h, w = self._shape
        roi_full = (w * 0.25, h * 0.25, w * 0.5, h * 0.5)
        if crop_rect is not None:
            cx, cy, _, _ = crop_rect
            roi_disp = ((roi_full[0] - cx) / downsample, (roi_full[1] - cy) / downsample,
                        roi_full[2] / downsample, roi_full[3] / downsample)
        else:
            roi_disp = tuple(v / downsample for v in roi_full)
        return [("box", roi_disp, "#00ff00")]

    def get_particle_overlays(self, t_idx: int, z_idx: int,
                              crop_rect: Optional[Tuple[float, float, float, float]] = None,
                              downsample: int = 1) -> List[Tuple[str, object, str, bool]]:
        """Document the get_particle_overlays flow."""
        return []

    def get_calibration(self) -> Calibration:
        """Document the get_calibration flow."""
        return Calibration(pixel_size_um=0.1, unit="µm", calibrated=True)

    def _generate_annotations(self) -> List[Annotation]:
        """Document the generate_annotations flow."""
        _, _, h, w = self._shape
        return [
            Annotation(x=(i + 1) * w / (self._num_annotations + 1),
                       y=(i + 1) * h / (self._num_annotations + 1),
                       label=f"Mock_{i}", color="#ff0000" if i % 2 == 0 else "#00ff00",
                       selected=(i == 0), t_idx=0, z_idx=0, metadata={"mock_id": i})
            for i in range(self._num_annotations)
        ]
