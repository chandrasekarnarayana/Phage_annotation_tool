# Phage Annotator ![PyPI](https://img.shields.io/badge/PyPI-coming--soon-lightgray) ![License](https://img.shields.io/badge/License-MIT-blue) ![Python](https://img.shields.io/badge/Python-3.9%2B-brightgreen)

Phage Annotator is an interactive, publication-grade keypoint annotation tool for fluorescence microscopy. Built with Matplotlib + Qt (no Tkinter, no Napari), it streamlines labeling of particles in 2D/3D/time TIFF and OME-TIFF datasets—designed for phage imaging but fully general for any keypoint protocol.

---

## Key Features
- Five synchronized panels: Frame, Mean, Composite/GT, Support (secondary modality), and STD with shared navigation and zoom.
- TIFF / OME-TIFF loading with automatic axis standardization to (T, Z, Y, X); per-FOV time/depth interpretation control.
- Lazy/on-demand loading; open files or folders without loading all pixels up front.
- Display crop (X,Y,W,H) and ROI (X,Y,W,H; box/circle) are independent; zoom preserved across playback and shared across panels.
- Interactive keypoint annotation (add/remove, frame/all scopes), per-panel visibility (Frame/Mean/Composite/Support), editable annotation table (changes persist), legacy x/y CSV import.
- Intensity controls (vmin/vmax), colormap selection, playback with loop, link/unlink zoom; native Matplotlib toolbar.
- Analyze menu: line profiles (raw vs corrected), ROI mean with bleaching fit, ROI mean table (per file) with CSV export.
- CSV + JSON export of all annotations; keyboard shortcuts: `r` reset zoom, `c` cycle colormap, `s` quick-save CSV.

---

## Architecture
- `src/phage_annotator/io.py` — TIFF/OME-TIFF loader, axis standardization, `ImageMeta`.
- `src/phage_annotator/annotations.py` — `Keypoint` dataclass, CSV/JSON serializers.
- `src/phage_annotator/gui_mpl.py` — Matplotlib + Qt GUI (views, sliders, labels, export).
- `src/phage_annotator/cli.py` — CLI entry (`phage-annotator -i image.tif …`).
- `src/phage_annotator/config.py` — `AppConfig` defaults (labels, suffixes, config dir).

---

## Installation

### From source (pip)
```bash
python -m venv .venv-phage
source .venv-phage/bin/activate
pip install .
```

### Layout and GUI
- Splitter-based layout prioritizes the five synchronized panels (Frame, Mean, Composite/GT, Support/epi, STD) with resizable panes for FOV list and settings.
- Compact control bar keeps T/Z sliders, autoplay/loop, vmin/vmax, colormap, label, and annotation scope/target visible; advanced tools (marker size, visibility, line/histogram, ROI details) are in a collapsible group and View menu.
- Menu bar (File/View/Help) covers opening files/folders, loading/saving annotations (CSV/JSON), toggling panels, linking zoom, and about dialog.

### System requirements
- Python 3.9+
- Qt runtime (provided via PyQt5 wheel on most platforms)
- A display environment (X11/Wayland on Linux, or run under a VNC/Xvfb session for headless)

### Optional: conda example
```bash
conda create -n phage-annotator python=3.11
conda activate phage-annotator
pip install .
```

---

## Usage

### Basic CLI
```bash
phage-annotator -i image1.tif image2.ome.tif
```

The GUI launches with the first image loaded. Use Prev/Next to switch FOVs. Annotate points, adjust contrast/colormap, and export to CSV/JSON.

### New workflow highlights
- Open files or entire folders (TIFF/OME-TIFF) via File menu; lazy/on-demand loading reduces memory usage.
- Five synchronized panels with shared ROI/navigation and shared zoom; Support panel for secondary modality.
- ROI defined by X/Y/Width/Height with Box/Circle shapes; annotations and histogram/stats respect the ROI. Display crop (X,Y,W,H) is separate to focus on subregions.
- Annotation table is editable (changes persist); load legacy x/y CSV or full CSV/JSON; per-panel visibility toggles and selectable annotation targets (Frame/Mean/Composite/Support).
- Analyze menu: line profiles (raw vs corrected), ROI mean vs frame with exponential bleaching fit, ROI mean table per file (from last opened folder or loaded images) with CSV export.
- Toggle line profile/histogram panels, link/unlink zoom (zoom preserved during playback), adjust marker size and click radius independently.
- Settings pane can be collapsed/hidden to maximize the image area; zoom linking preserves view during playback.
- Per-FOV control for interpreting 3D stacks as time or depth; override via “Interpret 3D axis as” control.

---

## GUI Walkthrough

### Loading images
- Pass one or more TIFF/OME-TIFF paths via CLI (`-i`).
- Use File → Open files… or Open folder… to add FOVs; only active FOVs load into memory.

### Navigating FOVs
- FOV list + Primary/Support selectors
- Buttons: **Prev FOV** / **Next FOV** (via list selection)
- FOV label shows current index and filename.

### Time / Depth sliders
- **T slider** (time) and **Z slider** (depth) enable only if the axis exists.
- Current slice view shows data at (T, Z).

### Brightness and colormap
- **Vmin/Vmax sliders** adjust contrast percentiles.
- Colormap radio buttons: gray, viridis, magma, plasma, cividis.
- Zoom/pan/home via Matplotlib toolbar.

### Adding / removing annotations
- Left-click in the slice view to add a keypoint at (y, x) for the current (T, Z).
- Click near an existing point on the same slice to remove it (distance threshold).
- Choose the active label via radio buttons (phage/artifact/other). Annotations can target Frame/Mean/Composite/Support; visibility per panel is toggled in Advanced.
- Edit annotations directly in the table (T/Z/Y/X/Label) and changes persist; selecting a row highlights points.
- Legacy two-column x/y CSV imports are supported (defaults applied for missing fields).

### Projection view
- Mean projection over T and Z shown on the right; all points for the current image are displayed.

### Exporting
- Buttons: **Save CSV**, **Save JSON**.
- Quick-save CSV: press `s` (saves alongside the first image).
- CSV/JSON include all points across all images.

### Keyboard shortcuts
| Key | Action              |
| --- | ------------------- |
| r   | Reset zoom          |
| c   | Cycle colormap      |
| s   | Quick-save CSV      |

### Screenshot placeholder
- _Insert GUI screenshot here (slice + projection, controls, labels)._

---

## Annotation Data Format

### CSV schema
Columns: `image_id, image_name, t, z, y, x, label`

### JSON schema
```json
{
  "image_name_1": [
    {"image_id": 0, "image_name": "image_name_1", "t": 0, "z": 0, "y": 10.5, "x": 20.1, "label": "phage"}
  ],
  "image_name_2": [
    {"image_id": 1, "image_name": "image_name_2", "t": 3, "z": 1, "y": 5.0, "x": 12.3, "label": "artifact"}
  ]
}
```

---

## Supported Image Types
- TIFF and OME-TIFF.
- Dimensionality handled:
  - 2D (Y, X) → (1, 1, Y, X)
  - Z stacks (Z, Y, X) → (1, Z, Y, X)
  - Time stacks (T, Y, X; T<20 heuristic) → (T, 1, Y, X)
  - T/Z stacks (T, Z, Y, X) → unchanged

---

## Troubleshooting
- **Qt backend errors**: Ensure a Qt-capable backend; launching via the CLI will set `Qt5Agg` automatically.
- **No display on Linux**: Use X11/Wayland or run under Xvfb/VNC for headless environments.
- **Large TIFFs**: Loading full stacks can be memory-intensive; consider downsampling externally if needed.

---

## Roadmap
- Multi-channel support and channel selector
- Undo/redo for annotations
- ROI masks and polygon tools
- Batch export presets
- Configurable distance thresholds and label sets
- Optional multi-window or tabbed FOV layout

---

## Contributing
- Run tests: `pytest`
- Code style: keep docstrings concise; add comments only for non-obvious logic; prefer type hints.
- Issues and PRs are welcome.

---

## License
MIT with attribution. See `LICENSE`.

---

## Citation
If you use this tool in your work, please cite “Phage Annotator” (citation details to be provided).
