"""Test ROI filtering in suggestion generation."""

import numpy as np
from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel


def test_roi_box_filtering():
    """Test that suggestions are filtered to only include points within box ROI."""
    # Create a test image with peaks at known locations
    img = np.random.rand(100, 100).astype(np.float32) * 10.0  # Add noise
    
    # Add strong peaks at specific locations (much higher than background)
    # Peak 1: (20, 20) - inside ROI
    # Peak 2: (20, 80) - outside ROI
    # Peak 3: (50, 50) - inside ROI
    # Peak 4: (80, 20) - outside ROI
    peaks_inside = [(20, 20), (50, 50)]
    peaks_outside = [(20, 80), (80, 20)]
    
    for y, x in peaks_inside + peaks_outside:
        # Create Gaussian-like peaks
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                dist = np.sqrt(dy**2 + dx**2)
                if 0 <= y+dy < 100 and 0 <= x+dx < 100:
                    img[y+dy, x+dx] = max(img[y+dy, x+dx], 500.0 * np.exp(-dist**2 / 2.0))
    
    # Define ROI: box from (10, 10) with width=50, height=50
    # This should include peaks at (20,20) and (50,50)
    # and exclude peaks at (20,80) and (80,20)
    roi_shape = "box"
    roi_rect = (10.0, 10.0, 50.0, 50.0)  # (x0, y0, w, h)
    
    model = LocalPeakSuggestionModel(
        min_distance_px=15,
        max_points=100,
        threshold_quantile=0.95,  # High threshold to get only strong peaks
    )
    
    # Generate suggestions with ROI filtering
    suggestions = model.predict(
        img,
        image_id=1,
        image_name="test",
        t=0,
        z=0,
        label="test_label",
        roi_shape=roi_shape,
        roi_rect=roi_rect,
    )
    
    # Check that only peaks within ROI are suggested
    coords = [(int(s.y), int(s.x)) for s in suggestions]
    print(f"Suggestions found at: {coords}")
    
    # Verify the coordinates are within ROI bounds
    x0, y0, w, h = roi_rect
    for s in suggestions:
        x, y = s.x, s.y
        assert x0 <= x <= (x0 + w), f"Point x={x} outside ROI x-bounds [{x0}, {x0+w}]"
        assert y0 <= y <= (y0 + h), f"Point y={y} outside ROI y-bounds [{y0}, {y0+h}]"
    
    # Check that we found the peaks inside ROI
    found_peaks = {(round(s.y), round(s.x)) for s in suggestions}
    for py, px in peaks_inside:
        # Allow ±1 pixel tolerance
        nearby = any(abs(fy - py) <= 1 and abs(fx - px) <= 1 for fy, fx in found_peaks)
        assert nearby, f"Expected peak at ({py}, {px}) not found in suggestions"
    
    # Check that peaks outside ROI are NOT in suggestions
    for py, px in peaks_outside:
        for s in suggestions:
            dist = np.sqrt((s.y - py)**2 + (s.x - px)**2)
            assert dist > 5, f"Found unexpected peak near ({py}, {px}) outside ROI"
    
    print("✓ Box ROI filtering test passed!")


def test_roi_circle_filtering():
    """Test that suggestions are filtered to only include points within circle ROI."""
    img = np.random.rand(100, 100).astype(np.float32) * 10.0
    
    # Add peaks at specific locations
    # Peak 1: (50, 50) - inside circle (center)
    # Peak 2: (50, 70) - inside circle (within radius 25)
    # Peak 3: (50, 90) - outside circle
    # Peak 4: (30, 50) - inside circle
    peaks_inside = [(50, 50), (50, 70), (30, 50)]
    peaks_outside = [(50, 90)]
    
    for y, x in peaks_inside + peaks_outside:
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                dist = np.sqrt(dy**2 + dx**2)
                if 0 <= y+dy < 100 and 0 <= x+dx < 100:
                    img[y+dy, x+dx] = max(img[y+dy, x+dx], 500.0 * np.exp(-dist**2 / 2.0))
    
    # Define ROI: circle centered at (50, 50) with radius 25
    roi_shape = "circle"
    roi_rect = (50.0, 50.0, 25.0, 0.0)  # (cx, cy, r, _)
    
    model = LocalPeakSuggestionModel(
        min_distance_px=15,
        max_points=100,
        threshold_quantile=0.95,
    )
    
    suggestions = model.predict(
        img,
        image_id=1,
        image_name="test",
        t=0,
        z=0,
        label="test_label",
        roi_shape=roi_shape,
        roi_rect=roi_rect,
    )
    
    coords = [(int(s.y), int(s.x)) for s in suggestions]
    print(f"Suggestions found at: {coords}")
    
    # Verify all points are within radius
    cx, cy, r = 50.0, 50.0, 25.0
    for s in suggestions:
        dist = np.sqrt((s.x - cx)**2 + (s.y - cy)**2)
        assert dist <= r, f"Point ({s.y}, {s.x}) outside circle (dist={dist:.1f} > r={r})"
    
    # Check that peaks outside circle are NOT in suggestions
    for py, px in peaks_outside:
        for s in suggestions:
            dist = np.sqrt((s.y - py)**2 + (s.x - px)**2)
            assert dist > 5, f"Found unexpected peak near ({py}, {px}) outside ROI"
    
    print("✓ Circle ROI filtering test passed!")


def test_roi_none_no_filtering():
    """Test that with roi_shape='none', all suggestions are returned."""
    img = np.random.rand(100, 100).astype(np.float32) * 10.0
    
    # Add 4 peaks spread across the image
    peaks = [(20, 20), (20, 80), (80, 20), (80, 80)]
    for y, x in peaks:
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                dist = np.sqrt(dy**2 + dx**2)
                if 0 <= y+dy < 100 and 0 <= x+dx < 100:
                    img[y+dy, x+dx] = max(img[y+dy, x+dx], 500.0 * np.exp(-dist**2 / 2.0))
    
    roi_shape = "none"
    roi_rect = (0.0, 0.0, 0.0, 0.0)
    
    model = LocalPeakSuggestionModel(
        min_distance_px=15,
        max_points=100,
        threshold_quantile=0.95,
    )
    
    suggestions = model.predict(
        img,
        image_id=1,
        image_name="test",
        t=0,
        z=0,
        label="test_label",
        roi_shape=roi_shape,
        roi_rect=roi_rect,
    )
    
    coords = [(int(s.y), int(s.x)) for s in suggestions]
    print(f"Suggestions found at: {coords}")
    
    # Should find all 4 peaks when no ROI is active
    found_peaks = {(round(s.y), round(s.x)) for s in suggestions}
    for py, px in peaks:
        nearby = any(abs(fy - py) <= 2 and abs(fx - px) <= 2 for fy, fx in found_peaks)
        assert nearby, f"Expected peak at ({py}, {px}) not found"
    
    print("✓ No ROI (roi_shape='none') test passed!")


if __name__ == "__main__":
    test_roi_box_filtering()
    test_roi_circle_filtering()
    test_roi_none_no_filtering()
    print("\n✅ All ROI filtering tests passed!")
