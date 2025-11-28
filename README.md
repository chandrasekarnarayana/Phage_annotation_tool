# Phage Annotator  
![PyPI](https://img.shields.io/pypi/v/phage-annotator)  
![License](https://img.shields.io/badge/License-Custom--Permission-critical)  
![Python](https://img.shields.io/badge/Python-3.9%2B-brightgreen)

**IMPORTANT NOTICE — PLEASE READ**

> **This codebase is NOT open for reuse, modification, redistribution, or integration in any project without my explicit written permission.  
If you wish to reuse or extend any part of this software (code or GUI), please contact me directly for authorization.**  
>  
> **Email:** chandrasekarnarayana@gmail.com

The repository contains my original research software and full workflow implementation.  
Unauthorized copying or reusing any portion of this code is strictly prohibited.

---

# Phage Annotator

Phage Annotator is an interactive, publication-grade keypoint annotation tool for fluorescence microscopy.  
Built with **Matplotlib + Qt** (no Tkinter, no Napari), it supports precise annotation of particles in **2D / 3D / time** TIFF and OME-TIFF datasets.

It is designed for **single-molecule and phage imaging**, but can be used for **any keypoint-based microscopy annotation workflow**.

---

## Key Features

- **Five synchronized panels**  
  Frame, Mean projection, Composite/GT, Support (secondary modality), Standard deviation map  
  — all with shared zoom, shared ROI, and shared navigation.

- **TIFF / OME-TIFF** loading with automatic axis standardization to `(T, Z, Y, X)`  
  and manual override for ambiguous stacks.

- **Lazy, on-demand image loading**  
  (load folders without loading all images into memory).

- **Display crop vs. ROI — fully independent**  
  Crop `(X, Y, W, H)` for viewing; ROI `(X, Y, W, H)` or circle for annotation constraints.

- **Annotation system**  
  - Add/remove with click radius  
  - Per-panel visibility  
  - Annotate on Frame / Mean / Composite / Support  
  - Editable annotation table  
  - Import legacy x/y CSV or structured CSV/JSON  
  - Save CSV / JSON  
  - Quick-save with **`s`**

- **Intensity controls**  
  vmin/vmax, colormap switcher, histogram, stats, linked playback-safe zoom.

- **Analysis tools**  
  - Line profile (raw/corrected)  
  - ROI mean over frames with bleaching fit  
  - ROI mean table for all files with CSV export

- **Playback engine**  
  Time or depth slider, auto-play with FPS, optional loop  
  — zoom preserved during playback.

---

# Architecture

```

src/phage_annotator/
├── io.py              # TIFF loader, metadata, axis normalizer
├── annotations.py     # Keypoint models, CSV/JSON serializers
├── gui_mpl.py         # Full Qt + Matplotlib GUI
├── cli.py             # CLI entry point
└── config.py          # App defaults

````

---

# Installation

### **Install from PyPI**

```bash
pip install phage-annotator
````

### From source

```bash
python -m venv .venv-phage
source .venv-phage/bin/activate
pip install .
```

### System Requirements

* Python 3.9+
* PyQt5 (auto-installed)
* Linux / macOS / Windows with GUI support

---

# Usage

### Basic launch

```bash
phage-annotator -i image1.tif image2.ome.tif
```

### Folder-based workflow

Use **File → Open folder…** to populate the FOV list (lazy loading).

### Highlights

* Five synchronized views with shared ROI
* Crop view independently of ROI
* Annotate across frames / all frames
* Edit annotation table directly
* Histogram + stats + line profile
* Playback with zoom lock
* Multi-modality visualization (Primary + Support)

---

# GUI Walkthrough

### Navigation

* FOV list
* Prev / Next
* Primary / Support selector

### Playback

* Time slider (T)
* Depth slider (Z)
* FPS + Loop

### Intensity + Colormap

* vmin/vmax sliders
* Gray / Viridis / Magma / Plasma / Cividis

### Annotation

* Add: click
* Remove: click near point
* Choose label (phage/artifact/other)
* Marker size vs. click radius (separate controls)
* Show/hide annotation per panel

### Export

* Save CSV
* Save JSON
* Quick-save (`s`)

### Keyboard Shortcuts

| Key | Action         |
| --- | -------------- |
| r   | Reset zoom     |
| c   | Cycle colormap |
| s   | Save CSV       |

---

# Annotation Data Format

### CSV

```
image_id, image_name, t, z, y, x, label
```

### JSON example

```json
{
  "image_name_1": [
    {"image_id": 0, "image_name": "image_name_1", "t": 0, "z": 0, "y": 10.5, "x": 20.1, "label": "phage"}
  ]
}
```

---

# Supported Image Types

* `.tif`, `.tiff`, `.ome.tif`, `.ome.tiff`
* Automatically interpreted as:

  * 2D → (1,1,Y,X)
  * Z-stack → (1,Z,Y,X)
  * Time-stack → (T,1,Y,X)
  * Full TZ stack → (T,Z,Y,X)

---

# Troubleshooting

* Qt errors → ensure system has a display or use Xvfb
* Very large TIFFs → use lazy load and crop view
* Wrong axis interpretation → override using the “Interpret 3D axis as” control

---

# Roadmap

* Multi-channel support
* Undo/redo
* Polygon ROI
* Batch annotation presets
* Fully dockable GUI layout

---

# Contribution Policy

At this time, the project does **not** accept external code contributions.
You may file issues, but **code modifications or forks are NOT permitted without my written permission**.

---

# Custom License Notice

Although the repository includes an MIT license file for packaging compatibility, **actual reuse rights are restricted**.

> **No part of this codebase may be reused, modified, cloned, forked, or integrated into any other software — commercial or academic — without explicit written permission from the author.**

---

# Citation

If you use this tool in research, please cite (Will be updated soon):

**“Phage Annotator — Chandrasekar Subramani Narayana (2025)”**
