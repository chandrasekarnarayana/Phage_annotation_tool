"""Unit tests for the analysis package facade modules."""

from __future__ import annotations

import numpy as np

import phage_annotator.analysis.core as analysis_core
import phage_annotator.analysis.particles as analysis_particles
import phage_annotator.analysis.threshold as analysis_threshold


def test_analysis_core_facade_compute_mean_std() -> None:
    """The analysis.core facade should expose projection helpers."""
    arr = np.arange(2 * 1 * 4 * 5, dtype=np.float32).reshape(2, 1, 4, 5)
    mean_proj, std_proj = analysis_core.compute_mean_std(arr)
    assert mean_proj.shape == (4, 5)
    assert std_proj.shape == (4, 5)
    assert mean_proj.dtype == np.float32
    assert std_proj.dtype == np.float32


def test_analysis_particles_facade_detects_component() -> None:
    """The analysis.particles facade should expose component analysis."""
    mask = np.zeros((12, 12), dtype=bool)
    mask[2:8, 3:9] = True
    opts = analysis_particles.ParticleOptions(
        min_area_px=5,
        max_circularity=2.0,
        exclude_edges=False,
    )
    particles = analysis_particles.analyze_particles(mask, frame_index=0, opts=opts)
    if analysis_particles.sk_measure is None and analysis_particles.ndi is None:
        # Without optional scipy/skimage dependencies, component labeling is unavailable.
        assert particles == []
    else:
        assert len(particles) == 1
        particle = particles[0]
        assert particle.area_px == 36
        assert particle.frame_index == 0
        assert particle.bbox[0:2] == (3, 2)


def test_analysis_threshold_facade_mask_pipeline() -> None:
    """The analysis.threshold module should produce deterministic masks."""
    image = np.array(
        [
            [0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 1.0, 1.0],
        ],
        dtype=np.float32,
    )
    threshold = analysis_threshold.compute_threshold(image, method="mean")
    mask = analysis_threshold.make_mask(image, threshold)
    cleaned = analysis_threshold.postprocess_mask(
        mask,
        analysis_threshold.PostprocessOptions(
            min_area_px=1,
            open_radius_px=0,
            close_radius_px=0,
        ),
    )
    assert threshold == 0.5
    assert mask.dtype == bool
    assert cleaned.dtype == bool
    assert cleaned.sum() == 8
    assert "Otsu" in analysis_threshold.AUTO_METHODS
