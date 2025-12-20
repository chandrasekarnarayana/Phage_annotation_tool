# Quick Reference: P3-P5 Implementation Details

## 1. Export Validation (P4.2)

**Location**: `src/phage_annotator/export_view.py`

```python
# Import
from export_view import ExportValidationResult, validate_export_preflight

# Usage
from phage_annotator.gui_export import ExportOptions

options = ExportOptions(
    panel="frame",
    region="full view",
    dpi=300,
    marker_size=50.0,
    roi_linewidth=2.0,
    format="PNG"
)

result = validate_export_preflight(
    options=options,
    has_support_image=True,
    has_roi=True,
    image_shape=(512, 512)
)

if result.is_valid:
    proceed_with_export()
else:
    for error in result.errors:
        logger.error(f"Export blocked: {error}")
    
for warning in result.warnings:
    logger.warning(f"Export warning: {warning}")
```

**Validation Bounds**:
- DPI: 72-600
- Marker size: 1.0-200.0 px
- ROI linewidth: 0.5-6.0 px
- Format: PNG, TIFF (case-insensitive)
- Panels: frame, mean, composite, support, std
- Regions: full view, crop, roi bounds, roi mask-clipped

---

## 2. Widget ObjectName Pattern (P4.4)

**Location**: `src/phage_annotator/gui_export.py` (completed for export dialog)

```python
# Pattern: {dialog_name}_{widget_type}_{purpose}

dialog = QDialog()
dialog.setObjectName("export_dialog")

combo = QComboBox()
combo.setObjectName("export_dialog_combo_panel")  # combo box for panel selection

spinbox = QSpinBox()
spinbox.setObjectName("export_dialog_spinbox_dpi")  # spinbox for DPI

checkbox = QCheckBox()
checkbox.setObjectName("export_dialog_checkbox_roi_outline")  # checkbox for ROI outline

button = QPushButton()
button.setObjectName("export_dialog_pushbutton_ok")  # push button for OK
```

**Testing with objectName**:
```python
# In test file
dialog = _export_view_dialog(session)
combo_panel = dialog.findChild(QComboBox, "export_dialog_combo_panel")
assert combo_panel is not None
combo_panel.setCurrentText("mean")
```

**Widget Types Used**:
- `combo` → QComboBox
- `spinbox` → QSpinBox
- `checkbox` → QCheckBox
- `pushbutton` → QPushButton
- `label` → QLabel
- `lineedit` → QLineEdit

---

## 3. Performance Panel (P5.1)

**Location**: `src/phage_annotator/gui_panel_performance.py`

```python
from gui_panel_performance import PerformancePanel

# Create panel
panel = PerformancePanel(parent=main_window)

# Add to dock
dock = QDockWidget("Performance", parent=main_window)
dock.setWidget(panel)
main_window.addDockWidget(Qt.RightDockWidgetArea, dock)

# Update metrics from main loop
panel.update_cache_metrics(
    hit_rate=0.85,
    memory_mb=256.5,
    max_memory_mb=512
)

panel.update_job_metrics(
    queue_length=3,
    avg_wait_time=1.2
)
```

**Real-time Metrics Displayed**:
- ✅ Cache hit rate (%)
- ✅ Buffer utilization (MB / max)
- ✅ Job queue status
- ✅ Recent evictions (timestamp, size)

**Quick Action Buttons**:
- 🔄 Clear Cache
- ❌ Cancel All Jobs
- 🔀 Reset Stats

---

## 4. Multi-image ROI Copy (P5.2)

**Location**: `src/phage_annotator/roi_manager.py`

```python
from roi_manager import ROIManager

roi_mgr = ROIManager()

# Copy ROI from image A
roi_mgr.copy_roi(source_image_id="img_001.tif")

# Paste ROI to image B
roi_mgr.paste_roi(
    target_image_id="img_002.tif",
    scale=True,  # Auto-scale if dimensions differ
    offset=(0, 0)  # Optional position offset
)

# Validate ROI fits in target
is_valid = roi_mgr.validate_roi(target_image_id="img_002.tif")
assert is_valid, "ROI extends beyond target image bounds"
```

**Features**:
- ✅ Copy ROI between images
- ✅ Auto-scale to target dimensions
- ✅ Bounds validation
- ✅ Persistent storage in .phageproj

---

## 5. Undo/Redo (P3.1)

**Location**: `src/phage_annotator/commands.py`

```python
from commands import Command, CommandStack, SetROICommand

cmd_stack = CommandStack(max_depth=50)

# Define custom command
class SetROICommand(Command):
    def __init__(self, roi_mgr, roi_data):
        self.roi_mgr = roi_mgr
        self.old_roi = roi_mgr.get_roi()
        self.new_roi = roi_data
    
    def execute(self):
        self.roi_mgr.set_roi(self.new_roi)
    
    def undo(self):
        self.roi_mgr.set_roi(self.old_roi)

# Use command
cmd = SetROICommand(roi_manager, new_roi_data)
cmd_stack.push(cmd)
cmd.execute()

# Undo
cmd_stack.undo()

# Redo
cmd_stack.redo()
```

**Supported Commands**:
- SetROICommand
- SetCropCommand
- SetDisplayMappingCommand
- SetThresholdCommand

---

## 6. Confirmation Toggles (P3.3)

**Location**: `src/phage_annotator/gui_controls_preferences.py`

```python
from QSettings import QSettings

settings = QSettings("Phage", "Annotator")

# Get confirmation setting
confirm_close = settings.value("confirmations/close_unsaved", True, type=bool)

# Set confirmation
settings.setValue("confirmations/close_unsaved", True)

# Available toggles
toggles = {
    "confirmations/close_unsaved": "Confirm on close with unsaved changes",
    "confirmations/clear_roi": "Confirm before ROI clear",
    "confirmations/clear_annotations": "Confirm before annotations clear",
    "confirmations/clear_histogram": "Confirm before histogram clear",
    "confirmations/apply_threshold": "Confirm before threshold apply"
}

# Reset all
for key in toggles:
    settings.remove(key)
```

---

## 7. Layer Export (P3.4)

**Location**: `src/phage_annotator/gui_export.py`

```python
# Export dialog with layer selection
export_options = ExportOptions(
    panel="frame",
    scope="current",
    export_as_layers=True,  # Enable layer export
    layers={
        "base": True,          # Background image
        "annotations": True,   # Annotation overlays
        "roi": True,          # ROI outline
        "particles": True,    # Particle detections
        "scalebar": True,     # Scale reference
        "text": True          # Text overlays
    }
)

# Output: individual PNG files with alpha channel
# - export_base.png
# - export_annotations.png
# - export_roi.png
# - export_particles.png
# - export_scalebar.png
# - export_text.png
# (Can be composited in image editor for WYSIWYG workflow)
```

---

## 8. Cache Telemetry (P4.3)

**Location**: `src/phage_annotator/projection_cache.py`

```python
from projection_cache import ProjectionCache

cache = ProjectionCache(max_size_mb=512)

# Get cache stats
stats = cache.get_stats()
print(f"Hit rate: {stats.hit_rate:.1%}")
print(f"Memory: {stats.memory_used_mb}/{stats.max_memory_mb} MB")
print(f"Entries: {stats.entry_count}")
print(f"Evictions: {stats.eviction_count}")

# Recent evictions
for eviction in stats.recent_evictions:
    print(f"  {eviction.timestamp}: {eviction.key} ({eviction.size_mb} MB)")

# Reset stats
cache.reset_stats()
```

**Tracked Metrics**:
- Hit count / miss count
- Memory utilization
- Eviction events (timestamp, key, reason)
- Entry count
- Average entry size

---

## 9. Deterministic Seeding (P3.2)

**Location**: Various (histogram, auto-contrast, threshold)

```python
import numpy as np

# All random sampling uses seed=42
np.random.seed(42)

# Examples where seed is applied
histogram_data = compute_histogram(image, bins=256, sampling_seed=42)
auto_contrast = compute_auto_contrast(image, sample_fraction=0.5, seed=42)
threshold = estimate_threshold(image, method="otsu", sample_seed=42)
```

**Benefit**: Reproducible results across runs (scientific rigor)

---

## 10. Tests Organization

**P4.1 UI Wiring Tests** (`tests/test_ui_wiring.py`):
```
test_file_menu_wiring()
  - Validates Open, Recent, Save, Export, Exit actions
test_edit_menu_wiring()
  - Validates Undo, Redo, Copy Display, Measure
test_view_menu_wiring()
  - Validates panel/dock toggles
test_analyze_menu_wiring()
  - Validates ROI stats, Particles, Threshold dialogs
test_help_menu_wiring()
  - Validates Shortcuts, About dialogs
```

**P4.2 Export Validation Tests** (`tests/test_export.py`):
```
test_dpi_validation()  # 6 cases
test_marker_size_validation()  # 5 cases
test_roi_linewidth_validation()  # 5 cases
test_format_validation()  # 6 cases
test_valid_panels()  # 5 cases
test_valid_regions()  # 4 cases
test_roi_requirement()  # 2 cases
test_overlay_warning()  # 1 case
test_invalid_panel()  # 1 case
test_invalid_region()  # 1 case
# Total: 35 tests, 100% passing
```

**Run Tests**:
```bash
# All tests except UI wiring (requires display)
pytest tests/ --ignore=tests/test_ui_wiring.py

# Only export validation
pytest tests/test_export.py -v

# Only UI wiring (requires Qt application context)
pytest tests/test_ui_wiring.py -v
```

---

## File Structure

```
src/phage_annotator/
├── export_view.py (ExportValidationResult, validate_export_preflight)
├── gui_export.py (objectName for widgets)
├── gui_panel_performance.py (P5.1 - NEW)
├── commands.py (P3.1 - NEW)
├── roi_manager.py (multi-image ROI copy)
├── projection_cache.py (cache telemetry)
├── gui_controls_preferences.py (confirmation toggles)
└── ... (other files)

tests/
├── test_export.py (P4.2 - NEW, 35 tests)
├── test_ui_wiring.py (P4.1 - NEW, 11 tests)
└── ... (original tests)

docs/dev/
├── feature_control_matrix.md (UPDATED - P3-P5 completion summary)
└── COMPLETION_SUMMARY_P3_P4_P5.md (NEW - detailed summary)
```

---

## Quick Start Examples

### Example 1: Safe Export with Validation
```python
from export_view import validate_export_preflight, ExportOptions

# Create export options
options = ExportOptions.from_dialog(export_dialog)

# Validate
result = validate_export_preflight(
    options=options,
    has_support_image=has_support_image,
    has_roi=has_active_roi,
    image_shape=image.shape
)

# Check result
if not result.is_valid:
    for error in result.errors:
        show_error_dialog(error)
    return  # Abort export
else:
    for warning in result.warnings:
        show_warning_dialog(warning)  # Warn but proceed
    
    # Proceed with export
    perform_export(options)
```

### Example 2: Test Widget Access
```python
from PyQt5.QtWidgets import QComboBox
from gui_export import _export_view_dialog

dialog = _export_view_dialog(session)
panel_combo = dialog.findChild(QComboBox, "export_dialog_combo_panel")
assert panel_combo is not None

# Test interaction
panel_combo.setCurrentText("mean")
assert panel_combo.currentText() == "mean"
```

### Example 3: Monitor Cache Health
```python
from gui_panel_performance import PerformancePanel

perf_panel = PerformancePanel()

# In main event loop
cache_stats = projection_cache.get_stats()
if cache_stats.hit_rate < 0.5:
    logger.warning("Low cache hit rate - consider expanding cache size")

if cache_stats.memory_used_mb > cache_stats.max_memory_mb * 0.9:
    perf_panel.show_cache_pressure_warning()
```

---

## References

- Full documentation: [docs/dev/feature_control_matrix.md](docs/dev/feature_control_matrix.md)
- Detailed summary: [COMPLETION_SUMMARY_P3_P4_P5.md](COMPLETION_SUMMARY_P3_P4_P5.md)
- Architecture: [docs/dev/architecture.md](docs/dev/architecture.md)

---

*Updated: 2024*  
*Python: 3.12.9 | PyQt5: 5.15.11 | pytest: 9.0.1*
