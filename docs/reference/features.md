# Feature Reference

## Data loading

- TIFF and OME-TIFF image loading with axis metadata normalisation.
- 2D, z-stack, time-lapse, and time–z data handling.
- Axis metadata inference and explicit override.
- Progressive LOD (level-of-detail) rendering for large stacks.

## Annotation

- Keypoint creation, editing, import, and export.
- Undo / redo through command objects (unlimited depth).
- Annotation metadata: label, certainty, review state, custom key–value pairs.
- Multi-modality annotation (separate keypoint sets per channel or modality).
- Batch accept, reject, and clear actions.
- ThunderSTORM-compatible CSV import and export.

## Assisted review

- Candidate point generation from image features.
- Suggestion scoring and ranked review queues.
- Accept, reject, clear, and batch actions.
- Interactive feedback and rescore hooks for iterative improvement.

## Quality control

- Density deviation checks per ROI.
- Metadata completeness checks.
- Image artifact detection (saturation, low SNR).
- Composite issue reporting with per-issue severity levels.

## SMLM — Single-Molecule Localisation Microscopy

Three fully independent execution paths:

### Internal Python pipeline (no Fiji required)

Implements the complete ThunderSTORM localisation algorithm in pure Python:

| Stage | Implementation |
| --- | --- |
| Image filtering | Wavelet B-spline (default) or Difference-of-Gaussians |
| Candidate detection | Local maxima with MAD-based threshold |
| Sub-pixel fitting | 2D symmetric Gaussian (least-squares) |
| Post-filtering | Min-photon count, max localisation uncertainty (nm) |
| Localisation merging | Nearest-neighbour across consecutive frames |
| SR rendering | Histogram or Gaussian scatter reconstruction |

Physical-unit results (nm) require only the camera pixel size parameter.

### Fiji subprocess bridge

Spawns a headless Fiji/ImageJ process and executes any ThunderSTORM macro:

- Auto-discovers Fiji installation on Linux, macOS, and Windows.
- Passes input TIFF, output path, and parameters via environment variables.
- Preflight CLI (`phage-annotator-smlm-preflight`) validates configuration before a full run.
- Retry logic with configurable timeout and retry count.
- Parity CLI (`phage-annotator-smlm-parity`) compares internal vs. Fiji outputs for regression testing.

### PyImageJ bridge

Runs Fiji in-process via the PyImageJ / JPype JVM bridge.
Requires `pip install "phage-annotator[fiji]"`.

### Bundled plugin support

- ThunderSTORM JAR bundled in `external_plugins/` (no separate download needed).
- Plugin descriptor manifests define parameter schemas, menus, and execution contracts.
- External plugin manifest tooling via `phage-annotator-fiji-plugin-tool`.
- Reproducibility runbook mode: captures exact parameters and macro text for audit.

## Deep-STORM super-resolution

PyTorch-based super-resolution reconstruction from sparse emitter frames:

- Tiled inference with Hanning-window overlap blending.
- Configurable patch size (32–256 px), overlap, and upsampling factor.
- Frame windowing and aggregation (mean or stack).
- Per-patch or global normalisation modes.
- Localisation extraction via MAD-threshold local maxima on the SR image.
- Device auto-selection: CUDA (NVIDIA) → MPS (Apple Silicon) → CPU.
- Requires `pip install "phage-annotator[ml]"` and a trained model file (`.pt` or `.pth`).

## ONNX density inference

Runs TensorFlow or PyTorch models exported to ONNX format for particle density estimation:

- Supports NHWC (TensorFlow default) and NCHW (PyTorch default) channel layouts.
- Tiled inference with raised-cosine stitching — handles arbitrarily large images.
- Execution providers: CPU, CUDA, CoreML (Apple), or any ONNX Runtime provider.
- Pre-processing: percentile clipping, z-score, min–max, or none.
- ROI-masked count output (total vs. ROI-scoped estimate).
- Density map export as TIFF; count data export as CSV.
- Requires `pip install "phage-annotator[ml]"` and an ONNX model file (`.onnx`).

## CNN density inference (PyTorch)

Internal PyTorch density predictor with tiled raised-cosine blending:

- Loads `.pt` or `.pth` models via `DensityPredictor.from_path()`.
- Configurable tile size, overlap, and compute device.

## Cross-platform compatibility

The application runs on Linux, macOS, and Windows.

| Feature | Linux | macOS | Windows |
| --- | --- | --- | --- |
| Internal SMLM pipeline | Yes | Yes | Yes |
| Fiji subprocess bridge | Yes | Yes | Yes |
| PyImageJ bridge | Yes | Yes | Yes (via Conda) |
| Deep-STORM CPU | Yes | Yes | Yes |
| Deep-STORM GPU | CUDA | MPS (Apple Silicon) | CUDA |
| ONNX CPU | Yes | Yes | Yes |
| ONNX GPU | CUDA | CoreML | CUDA |

Fiji auto-discovery searches platform-standard installation directories and
the `FIJI_EXECUTABLE` / `FIJI_APP` environment variables.

## Project persistence

- Project save / load with JSON schema versioning.
- Image path relinking for moved datasets.
- Schema migration for forward compatibility.
- Workspace state restoration (panel layout, ROI, zoom, LUT).

## ROI and crop

- Rectangle and circle ROI geometry.
- Auto-ROI proposal from image features.
- Per-axis crop bounds with independent controls.

## Rendering and display

- Multi-channel display with per-channel LUT and brightness / contrast.
- Orthoview (XY / XZ / YZ) for 3D data.
- Histogram panel with region-scoped computation (full image, ROI, or crop).
- Line profile overlay.
- SR image overlay from SMLM, Deep-STORM, and density pipelines.

## Performance and caching

- LRU frame cache with configurable size limit.
- Array pool to avoid repeated allocation in tiled inference.
- Benchmark suite with regression thresholds enforced in CI.
