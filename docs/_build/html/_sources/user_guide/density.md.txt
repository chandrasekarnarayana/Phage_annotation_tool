# Density Inference

The application provides two density inference pipelines for estimating
particle density from fluorescence images: an internal PyTorch backend and
an ONNX Runtime backend for TensorFlow or cross-framework models.

Both pipelines use the same tiled inference strategy with raised-cosine
overlap blending, so they can be used interchangeably and produce comparable
density maps given equivalent model weights.

## Requirements

Install the machine learning optional dependency group:

```bash
pip install "phage-annotator[ml]"
```

For GPU acceleration on NVIDIA hardware:

```bash
pip install "phage-annotator[ml-gpu]"
```

This installs `onnxruntime-gpu` in addition to `torch`.

## PyTorch density panel

### Opening the panel

Navigate to **View → Panels → Density (PyTorch)**.

### Loading a model

Click **Browse** to select a `.pt` or `.pth` PyTorch model file.
Click **Load model** to initialise the model on the selected device.

### Inference parameters

| Parameter | Description |
| --- | --- |
| Device | cuda / cpu — auto-detected at startup |
| Tile size | Spatial tile size in pixels fed to the model |
| Overlap | Overlap between adjacent tiles for seamless blending |
| Normalisation | Per-tile intensity normalisation mode |

### Running inference

Click **Run** to process the current ROI. The resulting density map is
displayed as an overlay on the main canvas. The total estimated particle
count and the ROI-scoped count are shown in the results section.

## ONNX density panel

The ONNX panel accepts models exported from TensorFlow, Keras, or PyTorch
via the ONNX interchange format. This makes it possible to use density
estimation models trained in any framework that supports ONNX export.

### Opening the panel

Navigate to **View → Panels → ONNX Density**.

### Loading a model

Click **Browse** and select a `.onnx` model file. The model metadata
(input shape, output shape, and ONNX opset) is displayed after loading.

### Model contract

The ONNX model must satisfy the following input/output contract:

| | Specification |
| --- | --- |
| Input shape | `(batch, H, W, C)` for NHWC or `(batch, C, H, W)` for NCHW |
| Input dtype | float32 |
| Output shape | `(batch, H, W)` or `(batch, H, W, 1)` |
| Output dtype | float32, values ≥ 0 representing density per pixel |

Set **Channel format** to match the channel layout the model expects.
TensorFlow and Keras models are typically NHWC; PyTorch exports are NCHW.

### Inference parameters

| Parameter | Description |
| --- | --- |
| Execution provider | CPU, CUDA, CoreML (Apple), or auto |
| Channel format | NHWC (TensorFlow) or NCHW (PyTorch) |
| Normalisation | percentile / z-score / min-max / none |
| p_low / p_high | Percentile bounds for percentile normalisation |
| Invert | Invert intensity before inference (bright-field images) |
| Tile size | Spatial tile side length in pixels |
| Overlap | Tile overlap in pixels |
| Batch tiles | Number of tiles batched into a single model call |
| Stitch mode | weighted (raised-cosine) or average |

### Calibration

| Parameter | Description |
| --- | --- |
| Count scale | Multiply raw density map integral to convert to physical counts |
| Background threshold | Minimum density value to suppress background before integration |
| Use ROI only | Report ROI-scoped count separately |

The **count scale** maps raw model output to physical particle counts.
Determine it empirically from a sample with a known particle number.

### Running inference

Click **Run ONNX Inference**. A progress bar tracks tile batch processing.
The density map is shown as an overlay; the total and ROI counts are reported
below the progress bar.

### Export

| Button | Output |
| --- | --- |
| Export density TIFF | Single-page float32 TIFF of the density map |
| Export counts CSV | CSV with total count, ROI count, runtime, and model metadata |

## Exporting models to ONNX

**From TensorFlow / Keras:**

```python
import tf2onnx
import tensorflow as tf

model = tf.keras.models.load_model("density_model.h5")
model_proto, _ = tf2onnx.convert.from_keras(model, output_path="density_model.onnx")
```

**From PyTorch:**

```python
import torch

model = MyDensityModel()
model.load_state_dict(torch.load("density_model.pt"))
model.eval()
dummy = torch.zeros(1, 1, 256, 256)
torch.onnx.export(model, dummy, "density_model.onnx", opset_version=17)
```

After export, open the `.onnx` file in the ONNX Density panel and set the
channel format to match your model's convention (NCHW for PyTorch exports).
