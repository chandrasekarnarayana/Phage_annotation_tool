# Developer Guide: Multi-Modality Architecture

## Overview

This guide documents the architecture of the multi-modality system for developers who want to extend or modify the tool.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Concepts](#core-concepts)
3. [Module Reference](#module-reference)
4. [Data Flow](#data-flow)
5. [Extension Points](#extension-points)
6. [Testing](#testing)
7. [Performance Considerations](#performance-considerations)

---

## Architecture Overview

### System Layers

```
┌─────────────────────────────────────────────────┐
│         UI Layer (PyQt5)                         │
│  ├─ Modality Tabs & Panels                       │
│  ├─ Contrast Controls & Dialog                   │
│  └─ Analysis Panels                              │
├─────────────────────────────────────────────────┤
│      Rendering Layer                             │
│  ├─ Canvas Renderer (async)                      │
│  ├─ Annotation Filtering                         │
│  └─ Visual Indicators                            │
├─────────────────────────────────────────────────┤
│      Session/State Layer                         │
│  ├─ ModalityManager (lifecycle)                  │
│  ├─ DisplayMapping (per-modality settings)       │
│  └─ ProjectionCache (multi-modality caching)     │
├─────────────────────────────────────────────────┤
│      Data Layer                                  │
│  ├─ Image Pyramids (efficient I/O)               │
│  ├─ Annotation Storage                           │
│  └─ Project Serialization                        │
└─────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Modularity**: Each modality is independent; changes to one don't affect others
2. **Backward Compatibility**: Legacy projects (single modality) work without modification
3. **Performance**: Multi-modality overhead is minimal (<5% CPU/memory per modality)
4. **Extensibility**: New modality types can be added without core changes

---

## Core Concepts

### 1. ModalitySpec

Represents metadata for a single modality:

```python
from phage_annotator.session.modality import ModalitySpec

spec = ModalitySpec(
    name="DAPI",           # User-readable name
    image_id=0,            # Index in image array
    projection_type="raw", # "raw", "mean", "max", "std", "min"
    display_settings={     # Per-modality display config
        "vmin": 0,
        "vmax": 4095,
        "gamma": 1.0,
        "colormap": "viridis"
    }
)
```

**Location**: `src/phage_annotator/session/modality.py`

### 2. ModalityManager

Manages the full lifecycle of modalities:

```python
from phage_annotator.session.modality import ModalityManager

manager = ModalityManager()
manager.add_modality("DAPI", image_id=0)
manager.add_modality("GFP", image_id=1)
manager.rename_modality(0, "DAPI-405nm")
manager.set_active_modality(0)
```

**Key Methods**:
- `add_modality(name, image_id, ...)` - Add new modality
- `remove_modality(idx)` - Remove modality
- `rename_modality(idx, new_name)` - Rename modality
- `set_active_modality(idx)` - Set which modality is displayed
- `get_active_modality_idx()` - Get current modality index
- `to_dict()`/`from_dict()` - Serialization

**Location**: `src/phage_annotator/session/modality.py`

### 3. DisplayMapping

Per-modality display settings (contrast, gamma, colormap):

```python
from phage_annotator.data.display_mapping import DisplayMapping

display = DisplayMapping()
display.set_vmin_vmax(modality_idx=0, vmin=100, vmax=4000)
display.apply_contrast_sync(
    source_modality_idx=0,
    target_modality_indices=[1, 2]  # Sync to modalities 1 and 2
)
```

**Key Methods**:
- `set_vmin_vmax(modality_idx, vmin, vmax)` - Set brightness range
- `apply_lut(image, modality_idx)` - Apply contrast to image
- `propagate_sync_updates(...)` - Sync contrast to linked modalities

**Location**: `src/phage_annotator/data/display_mapping.py`

### 4. Annotation Filtering

Annotations are tagged with optional `modality_idx`:

```python
from phage_annotator.annotation.core import Keypoint

# Annotation for DAPI modality
kp = Keypoint(
    x=100.0,
    y=200.0,
    z=5,
    t=0,
    class_idx=1,
    modality_idx=0  # Tag with modality
)

# Legacy annotation (visible on all modalities)
kp_legacy = Keypoint(
    x=150.0,
    y=250.0,
    z=5,
    t=0,
    class_idx=1,
    modality_idx=None  # No modality tag
)
```

**Rendering Filter** (in `ui_qt/rendering/renderer.py`):

```python
def _build_panel_annotations(self):
    active_modality_idx = getattr(self, "_active_modality_idx", None)
    for kp in self._current_keypoints():
        # Skip if annotation is for different modality
        if active_modality_idx is not None and kp.modality_idx is not None:
            if kp.modality_idx != active_modality_idx:
                continue
        # ... render annotation
```

---

## Module Reference

### Session Modules

#### `session/modality.py`
**Role**: Core multi-modality data structures and lifecycle management

**Classes**:
- `ModalitySpec` - Immutable modality metadata
- `ModalityManager` - Modality lifecycle (add, remove, rename)

**Tests**: `tests/unit/session/test_modality_system.py`

#### `session/migration.py`
**Role**: Backward compatibility for projects created with single-modality version

**Key Functions**:
- `migrate_legacy_project()` - Convert v1 → v2 project format
- `create_facade_for_legacy()` - Bridge for old code

**Tests**: `tests/unit/session/test_migration.py`

### Data Modules

#### `data/display_mapping.py`
**Role**: Per-modality display settings (vmin/vmax, gamma, colormap)

**Key Methods**:
- `set_vmin_vmax(modality_idx, vmin, vmax)` - Set brightness range
- `get_vmin_vmax(modality_idx)` - Retrieve brightness range
- `apply_lut(image, modality_idx)` - Apply pre-computed LUT to image
- `propagate_sync_updates()` - Sync contrast across linked modalities

**Tests**: `tests/unit/data/test_display_mapping.py`

#### `annotation/core.py`
**Role**: Annotation data structure with modality tagging

**Changes from Legacy**:
- `Keypoint` now has optional `modality_idx: int | None` field
- Filter logic in renderer checks modality_idx

**Tests**: `tests/unit/annotation/test_annotations.py`

### Rendering Modules

#### `ui_qt/rendering/renderer.py`
**Role**: Canvas rendering with multi-modality annotation filtering

**Key Changes**:
- `_build_panel_annotations()` filters by active modality
- `_active_modality_idx` attribute tracks current modality

**Tests**: `tests/unit/ui_qt/test_rendering.py`

#### `ui_qt/utils/visual_indicators.py`
**Role**: Visual feedback for modality state (colors, badges, icons)

**Key Classes**:
- `StatusIndicatorBar` - Shows active modality, sync state
- `ModalityStyling` - Color schemes for modality tabs

**Tests**: `tests/unit/ui_qt/test_ui_dialogs_and_refinements.py`

### IO Modules

#### `io/projects/base.py`
**Role**: Project serialization/deserialization

**Schema v2 Changes**:
```json
{
  "tool": "PhageAnnotator",
  "schema_version": 2,
  "modality_manager": {
    "modalities": [
      {
        "name": "DAPI",
        "image_id": 0,
        "projection_type": "raw",
        "display_settings": {...}
      }
    ],
    "active_modality_idx": 0,
    "zoom_pan_links": [[0, 1]]
  }
}
```

**Key Functions**:
- `save_project(..., modality_manager)` - Save with modality config
- `load_project(path)` - Load returns 8-tuple including `modality_manager_data`

**Tests**: `tests/unit/io/test_projects.py`

---

## Data Flow

### Adding an Annotation to a Modality

```
User Action (Canvas Click)
    ↓
ui_qt/utils/annotations.py::_add_annotation()
    ↓ (Gets active modality)
session/annotations.py::add_annotation(modality_idx=current)
    ↓ (Creates Keypoint with modality_idx)
annotation/core.py::Keypoint(modality_idx=0)
    ↓ (Stored in session)
core/session_state.py::annotations list
```

### Rendering Annotations

```
ui_qt/rendering/renderer.py::render_frame()
    ↓
_build_panel_annotations()
    ↓ (Check active_modality_idx)
For each keypoint:
  IF keypoint.modality_idx is not None:
    IF keypoint.modality_idx != active_modality_idx:
      SKIP  ← Filter out wrong modality
  ELSE:
    RENDER  ← Legacy annotation visible everywhere
```

### Saving/Loading Project with Modalities

```
Action: File → Save
    ↓
session/project.py::save_project()
    ↓ (Get modality_manager from session_state)
io/projects/base.py::save_project(
    ...,
    modality_manager=session.modality_manager
)
    ↓ (Serialize modality_manager.to_dict())
Write to .phageproj JSON file
    ↓
Schema v2 with "modality_manager" field

Action: File → Open
    ↓
io/projects/base.py::load_project(path)
    ↓ (Read schema_version, extract modality_manager_data)
Unpack 8-tuple: (..., modality_manager_data)
    ↓
session/project.py::load_project()
    ↓ (Deserialize: ModalityManager.from_dict(modality_manager_data))
Restore to session_state.modality_manager
```

---

## Extension Points

### Adding a New Modality Type

1. **Define projection type**:
   ```python
   # In session/modality.py
   PROJECTION_TYPES = ["raw", "mean", "max", "std", "min", "custom_xyz"]
   ```

2. **Implement projection function**:
   ```python
   # In algorithms/analysis.py
   def compute_custom_xyz_projection(array, axis):
       """Custom projection logic."""
       return result
   ```

3. **Update renderer**:
   ```python
   # In ui_qt/rendering/renderer.py
   def _apply_projection(image, modality_idx):
       projection_type = self.modality_specs[modality_idx].projection_type
       if projection_type == "custom_xyz":
           return compute_custom_xyz_projection(image)
   ```

### Extending Display Mapping

To add new display settings (e.g., per-channel RGB contrast):

1. **Update ModalitySpec**:
   ```python
   display_settings = {
       "vmin": 0,
       "vmax": 4095,
       "r_vmin": 0,  # New: per-channel R
       "r_vmax": 4095,
       "g_vmin": 0,  # New: per-channel G
       "g_vmax": 4095,
       ...
   }
   ```

2. **Update DisplayMapping methods**:
   ```python
   def set_channel_vmin_vmax(self, modality_idx, channel, vmin, vmax):
       """Set per-channel contrast."""
       ...
   ```

3. **Update serialization** in `io/projects/base.py`

### Adding Custom Analysis per Modality

```python
# In analysis/core.py
def run_analysis_on_modality(
    images: np.ndarray,
    modality_idx: int,
    target_modalities: List[int],  # New parameter
    method: str = "particle_detection"
) -> Dict:
    """Run analysis on specific modalities."""
    results = {}
    for idx in target_modalities:
        results[idx] = self._run_single_analysis(images[idx], method)
    return results
```

---

## Testing

### Unit Tests

**Coverage by Module**:

| Module | Test File | Tests |
|--------|-----------|-------|
| `session/modality.py` | `test_modality_system.py` | 33 |
| `data/display_mapping.py` | `test_display_mapping.py` | 20 |
| `annotation/core.py` | `test_annotations.py` | 15 |
| `io/projects/base.py` | `test_projects.py` | 18 |
| `ui_qt/rendering/renderer.py` | `test_rendering.py` | 12 |

**Run Unit Tests**:
```bash
pytest tests/unit/ -v
```

### Integration Tests

**Multi-Modality Workflows**:

```python
# tests/integration/test_multimodality_workflows.py

def test_add_annotate_save_load_modality():
    """Full workflow: create project, add modality, annotate, save, load."""
    project = create_test_project()
    project.add_modality("DAPI", images[0])
    project.add_modality("GFP", images[1])
    
    # Annotate on DAPI
    project.set_active_modality(0)
    project.add_annotation(x=100, y=200, modality_idx=0)
    
    # Annotate on GFP
    project.set_active_modality(1)
    project.add_annotation(x=150, y=250, modality_idx=1)
    
    # Save and reload
    project.save("test.phageproj")
    loaded = load_project("test.phageproj")
    
    assert len(loaded.modality_manager.modalities) == 2
    assert len(loaded.annotations) == 2
    assert loaded.annotations[0].modality_idx == 0
    assert loaded.annotations[1].modality_idx == 1
```

**Run Integration Tests**:
```bash
pytest tests/integration/ -v
```

---

## Performance Considerations

### Memory Usage Per Modality

- **RGB 8-bit image**: ~3 bytes/pixel
- **1920×1080 RGB stack (100 frames)**: ~600 MB
- **3 modalities**: ~1.8 GB RAM (plus overhead)

### CPU Usage Scaling

| # Modalities | Base | Rendering | Contrast Update | Analysis |
|--------------|------|-----------|-----------------|----------|
| 1 | 100% | 100% | 100% | 100% |
| 3 | ~110% | ~250% | ~120% | ~300% |
| 5 | ~115% | ~400% | ~140% | ~500% |

**Optimization Strategies**:

1. **Lazy Loading**: Load images only when modality becomes active
2. **Tile Caching**: Keep only visible region in memory
3. **Downsampling**: For preview, use lower resolution
4. **Async Rendering**: Non-blocking updates for responsive UI

### Benchmarks

Run performance tests:
```bash
pytest tests/performance/ -v --benchmark-disable=autoscale
```

**Expected Results**:
- Annotation filtering: <1ms per 1000 annotations
- Contrast sync propagation: <5ms to 10 modalities
- Project save: <100ms for 100K annotations
- Project load: <200ms for schema v2

---

## Common Issues and Solutions

### Issue: Annotation filtering not working

**Cause**: `_active_modality_idx` not set in renderer

**Solution**: Ensure modality tabs trigger `set_active_modality()` in renderer

```python
def on_modality_tab_clicked(idx):
    self.renderer._active_modality_idx = idx
    self.renderer.render_frame()
```

### Issue: Contrast sync creates infinite loop

**Cause**: Sync propagation triggers update, which triggers sync again

**Solution**: Add guard flag to prevent circular updates

```python
class DisplayMapping:
    def __init__(self):
        self._syncing = False
    
    def propagate_sync_updates(self, source_idx, values):
        if self._syncing:
            return
        self._syncing = True
        try:
            # ... sync logic
        finally:
            self._syncing = False
```

### Issue: Legacy annotations disappear after save

**Cause**: Legacy annotations (modality_idx=None) not preserved in schema v2

**Solution**: Explicitly set modality_idx=None for legacy annotations

```python
def save_annotations(annotations, modality_manager):
    for ann in annotations:
        if ann.modality_idx is None:
            ann.modality_idx = None  # Explicitly preserve
```

---

## Resources

- **API Reference**: See docstrings in each module
- **Examples**: `examples/` directory
- **Tests**: `tests/unit/` and `tests/integration/`
- **Issue Tracker**: https://github.com/chandrasekarnarayana/Phage_annotation_tool/issues
