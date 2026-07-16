# Deep-STORM Super-Resolution

Deep-STORM is a deep-learning-based approach to single-molecule localisation
microscopy. Instead of fitting Gaussian profiles to individual emitters, a
convolutional neural network trained on simulated or experimental data maps
raw camera frames directly to a super-resolution probability density image.
This approach is particularly effective at high emitter densities where
classical localisation algorithms fail.

## Requirements

Install the machine learning optional dependency group:

```bash
pip install "phage-annotator[ml]"
```

This installs PyTorch. GPU acceleration is used automatically if available:

- **Linux / Windows**: CUDA (NVIDIA GPU required; install `torch` with CUDA support)
- **macOS Apple Silicon**: MPS (Metal Performance Shaders, M1/M2/M3 chips)
- **All platforms**: CPU fallback (no GPU required)

A trained model file (`.pt` or `.pth`) is required. The application does not
include a pre-trained model. Obtain a model from:

- The [Deep-STORM project repository](https://github.com/EliasNehme/Deep-STORM)
- A custom training pipeline on your own experimental data

## Opening the panel

Navigate to **View → Panels → Deep-STORM** or use the side toolbar. The panel
opens as a dockable widget on the right side of the main window.

## Panel sections

### Model

| Control | Description |
| --- | --- |
| Model path | Path to the `.pt` or `.pth` model file |
| Browse | Open a file dialog to locate the model |
| Device | Compute device: auto-detected at startup (CUDA / MPS / CPU) |

Click **Load model** after selecting the file to verify the model loads
successfully. The status bar confirms the model architecture and device.

### Acquisition

| Control | Description |
| --- | --- |
| Pixel size (nm/px) | Camera pixel size at the sample plane |

This is required to report localisation coordinates in physical units (nm).

### Inference

| Control | Description |
| --- | --- |
| Patch size | Tile size fed to the model (32–256 px) |
| Overlap | Tile overlap for seamless stitching (px) |
| Upsample | SR output magnification relative to the input |
| Normalisation | Per-patch or global intensity normalisation |
| Output mode | `sr_image` (full SR reconstruction) |
| Frame window | Number of frames aggregated before inference |
| Aggregation | How frames are combined: mean or stack |

**Choosing patch size**: The model was trained on a specific patch size.
Using the same size as training gives the best results. Larger patches
produce smoother stitching; smaller patches run faster.

**Overlap**: An overlap of 10–20 % of the patch size is recommended.
Hanning-window blending is applied to suppress seam artefacts.

### Localisation extraction

| Control | Description |
| --- | --- |
| Smoothing sigma | Gaussian pre-smoothing of the SR image before peak detection |
| Detection threshold | MAD-based threshold for local maxima (multiplier σ) |

Localisation coordinates are reported in both SR pixels and physical
nanometres based on the pixel size and upsample factor.

### Run controls

Click **Run Deep-STORM** to start inference on the current ROI. A progress
bar tracks per-frame and per-tile progress. Click **Cancel** to abort a
running inference.

### Export

| Button | Output |
| --- | --- |
| Export CSV | Localisation list: SR X (px), SR Y (px), X (nm), Y (nm), score |
| Export TIFF | SR density image as single-page float32 TIFF |
| Add to Annotations | Converts localisations to keypoints in the annotation layer |

## Tips

- Start with the **CPU** device to verify the pipeline is working before
  enabling GPU acceleration.
- If the SR image shows tiling artefacts, increase the overlap or switch
  to a larger patch size.
- The frame window parameter controls how many raw frames are averaged
  before inference. For sparse emitters, `window_size = 1` is appropriate;
  for high-density frames, windowed mean projection can improve SNR.
- Localisations from Deep-STORM can be used alongside classical SMLM
  results. Add both to the annotation layer for comparison.
