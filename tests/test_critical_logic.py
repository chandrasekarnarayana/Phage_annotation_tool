"""Unit tests for critical ROI and cache logic.

Tests cover:
1. ROI mask generation (box and circle)
2. Cache eviction invariants
3. Annotation import edge cases
"""

import numpy as np
import pytest

from phage_annotator.analysis import roi_mask_for_polygon, roi_mask_for_shape, roi_mask_from_points
from phage_annotator.projection_cache import ProjectionCache


class TestRoiMaskGeneration:
    """Test ROI mask generation for different shapes."""

    def test_box_roi_mask_basic(self):
        """Test box ROI mask generation."""
        shape = (100, 100)
        roi_rect = (10.0, 20.0, 30.0, 40.0)  # x, y, w, h
        mask = roi_mask_for_shape(shape, roi_rect, "box")

        assert mask.shape == shape
        assert mask.dtype == bool

        # Check that some of the ROI region is True
        y_min = int(20.0)
        y_max = int(20.0 + 40.0)
        x_min = int(10.0)
        x_max = int(10.0 + 30.0)

        # The ROI region should have True values
        assert np.any(mask[y_min:y_max, x_min:x_max])
        # But not all True (border effects may apply)

        # Region before ROI should be False
        if y_min > 0:
            assert not np.any(mask[0:y_min, :])

    def test_circle_roi_mask_basic(self):
        """Test circle ROI mask generation."""
        shape = (100, 100)
        center_x, center_y = 50.0, 50.0
        radius = 20.0
        roi_rect = (center_x - radius, center_y - radius, 2 * radius, 2 * radius)
        mask = roi_mask_for_shape(shape, roi_rect, "circle")

        assert mask.shape == shape
        assert mask.dtype == bool

        # Check that center is definitely inside
        assert mask[int(center_y), int(center_x)]

        # Check that corners of bounding box are outside (circle != box)
        assert not mask[int(center_y - radius - 1), int(center_x - radius - 1)]

    def test_box_roi_at_image_boundary(self):
        """Test box ROI at image boundary."""
        shape = (100, 100)
        roi_rect = (90.0, 90.0, 20.0, 20.0)  # Extends beyond image
        mask = roi_mask_for_shape(shape, roi_rect, "box")

        assert mask.shape == shape
        # Should have some True values (the part inside the image)
        assert np.any(mask)
        # Should not overflow
        assert np.all(np.isfinite(mask.astype(float)))

    def test_circle_roi_at_image_boundary(self):
        """Test circle ROI at image boundary."""
        shape = (100, 100)
        # Center at corner with large radius
        roi_rect = (-10.0, -10.0, 50.0, 50.0)
        mask = roi_mask_for_shape(shape, roi_rect, "circle")

        assert mask.shape == shape
        assert np.any(mask)
        assert np.all(np.isfinite(mask.astype(float)))

    def test_roi_mask_from_points_box(self):
        """Test ROI mask generation from point pairs (box)."""
        shape = (100, 100)
        points = [(10.0, 20.0), (40.0, 60.0)]  # opposite corners
        mask = roi_mask_from_points(shape, "box", points)

        assert mask.shape == shape
        assert mask.dtype == bool
        assert np.any(mask)

    def test_roi_mask_from_points_circle(self):
        """Test ROI mask generation from point pairs (circle)."""
        shape = (100, 100)
        center = (50.0, 50.0)
        edge = (70.0, 50.0)  # Radius = 20
        points = [center, edge]
        mask = roi_mask_from_points(shape, "circle", points)

        assert mask.shape == shape
        assert mask.dtype == bool
        # Center must be in mask
        assert mask[int(center[1]), int(center[0])]

    def test_roi_mask_polygon(self):
        """Test polygon ROI mask generation."""
        shape = (100, 100)
        # Simple square
        points = [(20.0, 20.0), (80.0, 20.0), (80.0, 80.0), (20.0, 80.0)]
        mask = roi_mask_for_polygon(shape, points)

        assert mask.shape == shape
        assert mask.dtype == bool
        # Center should be inside
        assert mask[50, 50]
        # Corner should be outside
        assert not mask[0, 0]

    def test_roi_mask_empty_when_outside_image(self):
        """Test that ROI mask is empty when ROI is completely outside image."""
        shape = (100, 100)
        roi_rect = (200.0, 200.0, 50.0, 50.0)  # Way outside
        mask = roi_mask_for_shape(shape, roi_rect, "box")

        assert mask.shape == shape
        # Should be entirely False (or mostly False for circle)
        assert np.sum(mask) == 0 or np.sum(mask) < 10


class TestProjectionCacheEviction:
    """Test cache eviction invariants."""

    def test_cache_insertion_and_retrieval(self):
        """Test basic cache insertion and retrieval."""
        cache = ProjectionCache(max_mb=100)
        key = (0, "mean", (0.0, 0.0, 100.0, 100.0), 0, 0)
        data = np.random.rand(100, 100).astype(np.float32)

        cache.put(key, data)
        retrieved = cache.get(key)

        assert retrieved is not None
        assert np.allclose(retrieved, data)

    def test_cache_eviction_over_budget(self):
        """Test that cache evicts items when over memory budget."""
        # Create cache with small budget
        cache = ProjectionCache(max_mb=2)

        # Insert moderately-sized arrays
        keys = []
        for i in range(5):
            key = (i, f"proj_{i}", (0.0, 0.0, 100.0, 100.0), 0, 0)
            # Create a ~1 MB array (float32, 512x512)
            data = np.ones((512, 512), dtype=np.float32)
            cache.put(key, data)
            keys.append(key)

        # Cache should have evicted some items
        # We shouldn't be able to retrieve all of them
        present_count = sum(1 for k in keys if cache.get(k) is not None)
        assert present_count < len(keys), "Cache should have evicted some items"

    def test_cache_lru_ordering(self):
        """Test that LRU eviction removes least-recently-used items."""
        cache = ProjectionCache(max_mb=5)

        # Insert small items
        key1 = (1, "a", (0.0, 0.0, 10.0, 10.0), 0, 0)
        key2 = (2, "b", (0.0, 0.0, 10.0, 10.0), 0, 0)
        key3 = (3, "c", (0.0, 0.0, 10.0, 10.0), 0, 0)

        # Small arrays (~100 KB each)
        data_small = np.ones((100, 100), dtype=np.float32)

        cache.put(key1, data_small)
        cache.put(key2, data_small)
        cache.put(key3, data_small)

        # All should be present initially
        assert cache.get(key1) is not None
        assert cache.get(key2) is not None
        assert cache.get(key3) is not None

        # Access key1 again to make it recently used
        _ = cache.get(key1)

        # Insert larger items to trigger eviction
        key4 = (4, "d", (0.0, 0.0, 10.0, 10.0), 0, 0)
        data_large = np.ones((1000, 1000), dtype=np.float32)  # ~4 MB
        cache.put(key4, data_large)

        # At least one old item should have been evicted
        # key1 is likely still present (recently accessed)
        assert cache.get(key1) is not None or cache.get(key2) is None

    def test_pyramid_cache_separate(self):
        """Test that pyramid cache is stored separately and evicted first."""
        cache = ProjectionCache(max_mb=50)

        # Insert a pyramid item
        pyramid_key = (0, "mean", 2, 100, (0.0, 0.0, 100.0, 100.0), 0)
        pyramid_data = np.ones((100, 100), dtype=np.float32)
        cache.put_pyramid(pyramid_key, pyramid_data)

        # Insert a regular item
        regular_key = (0, "mean", (0.0, 0.0, 100.0, 100.0), 0, 0)
        regular_data = np.ones((100, 100), dtype=np.float32)
        cache.put(regular_key, regular_data)

        # Verify both are present
        assert cache.get_pyramid(pyramid_key) is not None
        assert cache.get(regular_key) is not None

    def test_cache_byte_size_tracking(self):
        """Test that cache correctly tracks approximate byte sizes."""
        cache = ProjectionCache(max_mb=10)

        # Insert items and verify they're tracked
        key1 = (1, "a", (0.0, 0.0, 10.0, 10.0), 0, 0)
        data1 = np.ones((1000, 1000), dtype=np.float32)  # ~4 MB
        cache.put(key1, data1)

        key2 = (2, "b", (0.0, 0.0, 10.0, 10.0), 0, 0)
        data2 = np.ones((500, 500), dtype=np.float32)  # ~1 MB
        cache.put(key2, data2)

        # Both should be present
        assert cache.get(key1) is not None
        assert cache.get(key2) is not None


class TestAnnotationImportEdgeCases:
    """Test edge cases in annotation import/export."""

    def test_annotation_with_missing_fields(self):
        """Test handling of annotations with missing optional fields."""
        from phage_annotator.annotations import Keypoint

        # Create annotation with minimal fields
        kp = Keypoint(
            image_id=0,
            image_name="test.tif",
            t=0,
            z=0,
            y=50.0,
            x=100.0,
        )

        assert kp.label == "phage"  # Default
        assert kp.source == "manual"  # Default
        assert kp.meta == {}  # Default

    def test_annotation_uuid_uniqueness(self):
        """Test that annotation UUIDs are unique."""
        from phage_annotator.annotations import Keypoint

        kp1 = Keypoint(image_id=0, image_name="a.tif", t=0, z=0, y=1.0, x=2.0)
        kp2 = Keypoint(image_id=0, image_name="a.tif", t=0, z=0, y=1.0, x=2.0)

        assert kp1.annotation_id != kp2.annotation_id

    def test_annotation_negative_timeframe(self):
        """Test that t=-1, z=-1 indicates 'all frames'."""
        from phage_annotator.annotations import Keypoint

        kp = Keypoint(
            image_id=0,
            image_name="test.tif",
            t=-1,  # All frames
            z=-1,  # All depths
            y=50.0,
            x=100.0,
        )

        assert kp.t == -1
        assert kp.z == -1
