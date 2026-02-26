"""Analysis algorithms and computational methods (FIJI Layer 3).

This package implements the Algorithms Layer in the FIJI architecture,
providing stateless functions for image analysis, particle detection, ML
inference, and other computational tasks.

**Layer 3 Responsibilities**:
- Image analysis: Histograms, projections, statistics
- Particle detection: Density-based clustering, threshold analysis
- Density inference: Deep learning models (DeepSTORM, custom networks)
- ROI proposals: Automatic region suggestion from data
- SMLM processing: Localization analysis (ThunderSTORM)
- Utility functions: Cropping, resampling, masking

**Key Concepts**:
1. **Stateless functions**: No instance state, pure functions
2. **Numpy-based**: All algorithms use numpy/scipy, not frameworks
3. **GPU-optional**: ML models can run on CPU or GPU
4. **Configurable**: Options objects for algorithm parameters
5. **Composition**: Functions chain together for pipelines

**Dependencies**:
- data: For input arrays and DisplayMapping
- core: For Keypoint, ViewState, SessionState
- Not on: core.algorithms (avoid circular), ui_qt, plugins

**Design Patterns**:
- Functional decomposition: Small, testable functions
- Options objects: ParticleOptions, InferenceOptions encapsulate parameters
- Pipeline architecture: Chain analysis steps efficiently
- Progress callbacks: Long operations support cancellation

**Usage**:
    from phage_annotator.algorithms import analyze_particles, propose_roi
    from phage_annotator.algorithms.analysis import compute_mean_projection
    
    # Stateless computation on arrays
    particles = analyze_particles(image_array, threshold=0.5)
    roi = propose_roi(frame, method="density")
    
**Phase Progress**:
- Phase 2.5: Physical migration from core → algorithms
- Phase 3: GPU optimization for ML inference
- Phase 9: Full FIJI documentation complete
"""

# Import from new locations (Phase 2.5 physical migration)
# auto_roi.py
from phage_annotator.algorithms.auto_roi import propose_roi

# particles.py
from phage_annotator.algorithms.particles import (
    Particle,
    ParticleOptions,
    analyze_particles,
)

__all__ = [
    # auto_roi
    "propose_roi",
    # particles
    "Particle",
    "ParticleOptions",
    "analyze_particles",
]
