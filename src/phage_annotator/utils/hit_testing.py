"""Hit testing and spatial utilities for context actions (M5).

Utilities for finding nearest annotations and snapping to local maxima.
"""

from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from phage_annotator.core.annotation import Keypoint


class HitTester:
    """Finds nearest annotations to a point."""
    
    @staticmethod
    def find_nearest(
        annotations: List["Keypoint"],
        x: float,
        y: float,
        radius: float = 20.0,
    ) -> Optional[Tuple["Keypoint", float]]:
        """Find the nearest annotation to a point within a radius.
        
        Parameters
        ----------
        annotations : list of Keypoint
            Annotations to search.
        x, y : float
            Query point in display space.
        radius : float, default 20.0
            Search radius in display pixels.
        
        Returns
        -------
        (Keypoint, distance) or None
            Nearest annotation and distance, or None if no annotation
            within radius.
        """
        if not annotations:
            return None
        
        nearest = None
        nearest_dist = radius
        
        for ann in annotations:
            dx = ann.x - x
            dy = ann.y - y
            dist = (dx * dx + dy * dy) ** 0.5
            
            if dist < nearest_dist:
                nearest = ann
                nearest_dist = dist
        
        if nearest is None:
            return None
        
        return nearest, nearest_dist
    
    @staticmethod
    def find_all_within(
        annotations: List["Keypoint"],
        x: float,
        y: float,
        radius: float = 20.0,
    ) -> List[Tuple["Keypoint", float]]:
        """Find all annotations within a radius, sorted by distance.
        
        Parameters
        ----------
        annotations : list of Keypoint
            Annotations to search.
        x, y : float
            Query point in display space.
        radius : float, default 20.0
            Search radius in display pixels.
        
        Returns
        -------
        list of (Keypoint, distance)
            Annotations within radius, sorted nearest first.
        """
        results = []
        
        for ann in annotations:
            dx = ann.x - x
            dy = ann.y - y
            dist = (dx * dx + dy * dy) ** 0.5
            
            if dist <= radius:
                results.append((ann, dist))
        
        results.sort(key=lambda x: x[1])
        return results
    
    @staticmethod
    def hit_test_box(
        annotations: List["Keypoint"],
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> List["Keypoint"]:
        """Find all annotations within a rectangular region.
        
        Parameters
        ----------
        annotations : list of Keypoint
            Annotations to search.
        x0, y0, x1, y1 : float
            Bounding box corners (can be in any order).
        
        Returns
        -------
        list of Keypoint
            Annotations within the box.
        """
        xmin = min(x0, x1)
        xmax = max(x0, x1)
        ymin = min(y0, y1)
        ymax = max(y0, y1)
        
        results = []
        for ann in annotations:
            if xmin <= ann.x <= xmax and ymin <= ann.y <= ymax:
                results.append(ann)
        
        return results
    
    @staticmethod
    def hit_test_circle(
        annotations: List["Keypoint"],
        cx: float,
        cy: float,
        radius: float,
    ) -> List["Keypoint"]:
        """Find all annotations within a circular region.
        
        Parameters
        ----------
        annotations : list of Keypoint
            Annotations to search.
        cx, cy : float
            Circle center.
        radius : float
            Circle radius.
        
        Returns
        -------
        list of Keypoint
            Annotations within the circle.
        """
        results = []
        r_sq = radius * radius
        
        for ann in annotations:
            dx = ann.x - cx
            dy = ann.y - cy
            if dx * dx + dy * dy <= r_sq:
                results.append(ann)
        
        return results


class LocalMaxSnapper:
    """Snaps annotations to local maxima in image data."""
    
    @staticmethod
    def snap_to_local_max(
        image: np.ndarray,
        x: float,
        y: float,
        search_radius: float = 10.0,
        threshold: Optional[float] = None,
    ) -> Tuple[float, float]:
        """Snap a point to the local maximum within the image.
        
        Parameters
        ----------
        image : np.ndarray
            Image data (2D, single channel).
        x, y : float
            Initial coordinate.
        search_radius : float, default 10.0
            Search radius in pixels (max distance to consider).
        threshold : float, optional
            Minimum intensity threshold. If None, uses mean of image.
        
        Returns
        -------
        (new_x, new_y) : tuple of float
            New position of local maximum. Returns (x, y) if no
            local max found within search radius.
        """
        if image is None or len(image) == 0:
            return x, y
        
        # Ensure point is within image bounds
        h, w = image.shape[:2]
        x_int = int(np.clip(x, 0, w - 1))
        y_int = int(np.clip(y, 0, h - 1))
        
        # Define search box
        x0 = max(0, int(x_int - search_radius))
        x1 = min(w, int(x_int + search_radius) + 1)
        y0 = max(0, int(y_int - search_radius))
        y1 = min(h, int(y_int + search_radius) + 1)
        
        if x0 >= x1 or y0 >= y1:
            return x, y
        
        # Extract region
        region = image[y0:y1, x0:x1]
        
        # Set threshold if not provided
        if threshold is None:
            threshold = np.mean(region)
        
        # Find maximum intensity position
        max_pos = np.argmax(region)
        max_y, max_x = np.unravel_index(max_pos, region.shape)
        
        # Convert back to original image coordinates
        new_x = x0 + max_x
        new_y = y0 + max_y
        
        return float(new_x), float(new_y)
    
    @staticmethod
    def snap_to_centroid(
        image: np.ndarray,
        x: float,
        y: float,
        search_radius: float = 10.0,
        threshold: Optional[float] = None,
    ) -> Tuple[float, float]:
        """Snap a point to the intensity-weighted centroid.
        
        Parameters
        ----------
        image : np.ndarray
            Image data (2D, single channel).
        x, y : float
            Initial coordinate.
        search_radius : float, default 10.0
            Search radius in pixels.
        threshold : float, optional
            Minimum intensity threshold for centroid calculation.
        
        Returns
        -------
        (new_x, new_y) : tuple of float
            Centroid position.
        """
        if image is None or len(image) == 0:
            return x, y
        
        h, w = image.shape[:2]
        x_int = int(np.clip(x, 0, w - 1))
        y_int = int(np.clip(y, 0, h - 1))
        
        # Define search box
        x0 = max(0, int(x_int - search_radius))
        x1 = min(w, int(x_int + search_radius) + 1)
        y0 = max(0, int(y_int - search_radius))
        y1 = min(h, int(y_int + search_radius) + 1)
        
        if x0 >= x1 or y0 >= y1:
            return x, y
        
        # Extract region
        region = image[y0:y1, x0:x1]
        
        # Apply threshold if provided
        if threshold is not None:
            region = region * (region >= threshold)
        
        # Calculate centroid
        intensity_sum = np.sum(region)
        if intensity_sum <= 0:
            return x, y
        
        yy, xx = np.mgrid[y0:y1, x0:x1]
        centroid_x = np.sum(xx * region) / intensity_sum
        centroid_y = np.sum(yy * region) / intensity_sum
        
        return centroid_x, centroid_y
