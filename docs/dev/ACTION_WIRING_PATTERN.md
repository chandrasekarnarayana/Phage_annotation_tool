# Action Wiring Pattern Reference

## Overview
This document shows the standard patterns for connecting menu actions to their handler methods in the phage_annotator codebase. This is the pattern you should follow when wiring up your new multi-image ROI actions.

---

## Two-File Architecture Pattern

### File 1: `src/phage_annotator/ui_actions.py` - Action Definition
**Location:** Menu bar creation section (~lines 120-190)

**Responsibility:** Create and define actions, return them in an actions dictionary.

**Example:**
```python
def build_menus(window):
    menubar = window.menuBar()
    
    # Create Edit menu
    edit_menu = menubar.addMenu("&Edit")
    self.copy_display_act = edit_menu.addAction("Copy Display Settings…")
    self.measure_act = edit_menu.addAction("Measure (Results)")
    self.measure_act.setShortcut("Ctrl+M")
    
    # Create Tools menu
    tools_menu = menubar.addMenu("&Tools")
    self.clear_roi_act = tools_menu.addAction("Clear ROI")
    
    # P5.2: Multi-image ROI management
    self.copy_roi_to_all_act = tools_menu.addAction("Copy ROI to all images")
    self.save_roi_template_act = tools_menu.addAction("Save ROI as template")
    self.apply_roi_template_act = tools_menu.addAction("Apply ROI template…")
    
    # Return actions dictionary for wiring in setup
    actions = {
        "copy_display": self.copy_display_act,
        "measure": self.measure_act,
        # Note: Some actions stay as self.X_act instead of in dict
    }
    return actions, dock_panels_menu
```

**Key Points:**
- Actions created with `menu.addAction("Label")`
- Store as `self.{name}_act` for later retrieval
- Add to `actions` dict if needed in `gui_ui_setup.py`, or keep as `self.{name}_act` if referenced directly
- Set keyboard shortcuts here: `action.setShortcut("Ctrl+...")`

---

### File 2: `src/phage_annotator/gui_ui_setup.py` - Signal Wiring
**Location:** End of `_setup_ui()` method (~lines 595-690, in the "Hooks for menus" section)

**Responsibility:** Connect action signals to handler methods.

**Two Patterns:**

#### Pattern A: Action from dictionary
```python
# Line 78-81: Get actions from the returned dict
copy_display_act = actions["copy_display"]
measure_act = actions["measure"]

# Line 660-661: Wire the signals
copy_display_act.triggered.connect(self._copy_display_settings)
measure_act.triggered.connect(self._results_measure_current)
```

#### Pattern B: Action from self attribute
```python
# Line 84: Direct reference to self attribute
clear_roi_act = self.clear_roi_act

# Line 617: Wire the signal
clear_roi_act.triggered.connect(self._clear_roi)
```

#### Pattern C: With conditional checking
```python
# Line 113-119: Safe attribute access
if hasattr(self, "threshold_act"):
    self.threshold_act.triggered.connect(self._show_threshold_panel)
if hasattr(self, "analyze_particles_act"):
    self.analyze_particles_act.triggered.connect(self._show_analyze_particles_panel)
```

#### Pattern D: With dict.get() for optional actions
```python
# Line 112-114: Safe dict access
clear_hist_cache_act = actions.get("clear_hist_cache")
if clear_hist_cache_act is not None:
    clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)
```

---

## Handler Method Location

Handler methods are typically in **separate mixin files** matching their domain:

| Domain | File | Examples |
|--------|------|----------|
| ROI management | `gui_roi_crop.py` | `_clear_roi()`, `_copy_roi_to_all_images()`, `_save_roi_template()` |
| Display controls | `gui_controls_display.py` | `_copy_display_settings()` |
| Results table | `gui_controls_results.py` | `_results_measure_current()`, `_results_measure_over_time()` |
| File I/O | `gui_actions.py` | `_open_files()`, `_save_csv()` |
| UI state | `ui_docks.py` | `_toggle_overlay()`, `_reset_layout()` |

---

## Concrete Example: Your New Multi-Image ROI Actions

### Step 1: Define in `ui_actions.py` (lines 128-133)

```python
tools_menu = menubar.addMenu("&Tools")
self.clear_roi_act = tools_menu.addAction("Clear ROI")

# P5.2: Multi-image ROI management
self.copy_roi_to_all_act = tools_menu.addAction("Copy ROI to all images")
self.save_roi_template_act = tools_menu.addAction("Save ROI as template")
self.apply_roi_template_act = tools_menu.addAction("Apply ROI template…")
```

✅ **Status:** Already defined in `ui_actions.py`

### Step 2: Wire in `gui_ui_setup.py` 

**Option A: Add to `actions` dict** (if you want them passed through setup)
```python
# In ui_actions.py, add to returned dict:
actions = {
    ...
    "copy_roi_to_all": self.copy_roi_to_all_act,
    "save_roi_template": self.save_roi_template_act,
    "apply_roi_template": self.apply_roi_template_act,
}

# In gui_ui_setup.py (around line 82):
copy_roi_to_all_act = actions["copy_roi_to_all"]
save_roi_template_act = actions["save_roi_template"]
apply_roi_template_act = actions["apply_roi_template"]

# Then wire them (after line 617):
copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
save_roi_template_act.triggered.connect(self._save_roi_template)
apply_roi_template_act.triggered.connect(self._apply_roi_template)
```

**Option B: Use self attribute directly** (simpler if you don't need dict)
```python
# In gui_ui_setup.py (around line 617):
self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
self.save_roi_template_act.triggered.connect(self._save_roi_template)
self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
```

### Step 3: Implement handlers in `gui_roi_crop.py`

**Location:** `src/phage_annotator/gui_roi_crop.py` (lines 419-534)

**Signatures already exist:**
```python
def _clear_roi(self) -> None:
    """Clear the active ROI selection (P3.3: confirmation added)."""
    # Implementation...
    self.controller.clear_roi()
    self._sync_roi_controls()
    self._refresh_image()

def _copy_roi_to_all_images(self) -> None:
    """Copy the active ROI to all other images."""
    # Implementation...

def _save_roi_template(self) -> None:
    """Save active ROI as a named template for reuse."""
    # Implementation...

def _apply_roi_template(self, template_name: str = None) -> None:
    """Apply a saved ROI template to the current image."""
    # Implementation...
```

✅ **Status:** Handlers already implemented in `gui_roi_crop.py`

---

## Standard Signal Types

### `.triggered.connect()` - Menu/Action Signals
**Used for:** Menu items, toolbar actions, keyboard shortcuts (anything that inherits from `QAction`)

```python
action.triggered.connect(self._handler)
```

**Handler signature:**
```python
def _handler(self) -> None:
    ...
```

### `.clicked.connect()` - Button Signals  
**Used for:** `QPushButton`, `QToolButton`

```python
button.clicked.connect(self._handler)
```

**Handler signature:**
```python
def _handler(self) -> None:
    ...
```

### `.toggled.connect()` - Checkbox/Toggle Signals
**Used for:** `QCheckBox`, `QRadioButton`, toggle actions

```python
checkbox.toggled.connect(self._handler)
```

**Handler signature:**
```python
def _handler(self, checked: bool) -> None:
    ...
```

### `.valueChanged.connect()` - Slider/Spinner Signals
**Used for:** `QSlider`, `QSpinBox`, `QDoubleSpinBox`

```python
slider.valueChanged.connect(self._handler)
```

**Handler signature (for spinboxes):**
```python
def _handler(self, value: int | float) -> None:
    ...
```

### `.currentTextChanged.connect()` / `.currentIndexChanged.connect()` - Combo Box
**Used for:** `QComboBox`

```python
combo.currentTextChanged.connect(self._handler)
```

**Handler signature:**
```python
def _handler(self, text: str) -> None:
    ...
```

---

## Real Examples from Codebase

### 1. Clear ROI (Simple)

**Definition** (`ui_actions.py:128`):
```python
self.clear_roi_act = tools_menu.addAction("Clear ROI")
```

**Wiring** (`gui_ui_setup.py:84, 617`):
```python
clear_roi_act = self.clear_roi_act
clear_roi_act.triggered.connect(self._clear_roi)
```

**Handler** (`gui_roi_crop.py:23-36`):
```python
def _clear_roi(self) -> None:
    """Clear the active ROI selection (P3.3: confirmation added)."""
    if self._settings.value("confirmClearROI", True, type=bool):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Clear ROI",
            "Clear the current ROI selection?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
    self.controller.clear_roi()
    self._sync_roi_controls()
    self._refresh_image()
```

### 2. Copy Display Settings (Dialog-based)

**Definition** (`ui_actions.py:122`):
```python
self.copy_display_act = edit_menu.addAction("Copy Display Settings…")
```

**Wiring** (`gui_ui_setup.py:81, 660`):
```python
copy_display_act = actions["copy_display"]
copy_display_act.triggered.connect(self._copy_display_settings)
```

**Handler** (`gui_controls_display.py:234-264`):
```python
def _copy_display_settings(self) -> None:
    """Copy LUT/min/max/gamma from primary to another target."""
    mapping = self.controller.display_mapping.mapping_for(
        self.primary_image.id, "frame"
    )
    dlg = QtWidgets.QDialog(self)
    dlg.setWindowTitle("Copy Display Settings")
    layout = QtWidgets.QFormLayout(dlg)
    target_combo = QtWidgets.QComboBox()
    target_combo.addItems(["Support image", "All images"])
    layout.addRow("Target", target_combo)
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok
        | QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )
    layout.addRow(buttons)

    def _apply() -> None:
        choice = target_combo.currentText()
        if choice == "Support image":
            self._apply_display_to_image(self.support_image.id, "support", mapping)
        else:
            for img in self.images:
                self._apply_display_to_image(img.id, "frame", mapping)
        self._refresh_image()
        dlg.accept()

    buttons.accepted.connect(_apply)
    buttons.rejected.connect(dlg.reject)
    dlg.exec()
```

### 3. Measure (Results) - With Shortcut

**Definition** (`ui_actions.py:124-125`):
```python
self.measure_act = edit_menu.addAction("Measure (Results)")
self.measure_act.setShortcut("Ctrl+M")
```

**Wiring** (`gui_ui_setup.py:82, 661`):
```python
measure_act = actions["measure"]
measure_act.triggered.connect(self._results_measure_current)
```

**Handler** (`gui_controls_results.py:39-67`):
```python
def _results_measure_current(self) -> None:
    if self.primary_image.array is None or self.results_widget is None:
        return
    rois = self._results_rois()
    if not rois:
        return
    t = self.t_slider.value()
    z = self.z_slider.value()
    frame = self.primary_image.array[t, z, :, :]
    for roi in rois:
        mask = roi_mask_from_points(frame.shape, roi.roi_type, roi.points)
        mean, std, vmin, vmax, area_px = roi_stats(frame, mask)
        cal = self._get_calibration_state(self.primary_image.id)
        px_um = cal.pixel_size_um_per_px
        area_um2 = area_px * (px_um**2) if px_um else None
        self.results_widget.add_row(
            {
                "image_name": self.primary_image.name,
                "t": t,
                "z": z,
                "roi_id": roi.roi_id,
                "mean": f"{mean:.4f}",
                "std": f"{std:.4f}",
                "min": f"{vmin:.4f}",
                "max": f"{vmax:.4f}",
                "area_pixels": area_px,
                "area_um2": f"{area_um2:.4f}" if area_um2 is not None else "",
            }
        )
```

### 4. ROI Manager Button Clicks (in gui_events.py)

**Wiring** (`gui_events.py:97-103`):
```python
if self.roi_manager_widget is not None:
    widget = self.roi_manager_widget
    widget.add_btn.clicked.connect(self._roi_mgr_add)
    widget.del_btn.clicked.connect(self._roi_mgr_delete)
    widget.rename_btn.clicked.connect(self._roi_mgr_rename)
    widget.dup_btn.clicked.connect(self._roi_mgr_duplicate)
    widget.save_btn.clicked.connect(self._roi_mgr_save)
    widget.load_btn.clicked.connect(self._roi_mgr_load)
    widget.measure_btn.clicked.connect(self._roi_mgr_measure)
```

**Handlers** (`gui_controls_roi.py`):
```python
def _roi_mgr_add(self) -> None: ...
def _roi_mgr_delete(self) -> None: ...
def _roi_mgr_rename(self) -> None: ...
def _roi_mgr_duplicate(self) -> None: ...
def _roi_mgr_save(self) -> None: ...
def _roi_mgr_load(self) -> None: ...
def _roi_mgr_measure(self) -> None: ...
```

---

## Checklist for Adding New Actions

- [ ] **Definition** (`ui_actions.py`): Create action with `menu.addAction("Label")`
  - [ ] Store as `self.{name}_act`
  - [ ] Add keyboard shortcut if needed (`.setShortcut("...")`)
  - [ ] Add to `actions` dict if passing through setup, or leave as `self.*` if used directly
  
- [ ] **Wiring** (`gui_ui_setup.py`): Connect signal in "Hooks for menus" section
  - [ ] Get action from dict or self
  - [ ] Use safe access if optional (`.get()` or `hasattr()`)
  - [ ] Call `.triggered.connect(self._handler_name)`
  
- [ ] **Handler** (appropriate mixin file): Implement the handler method
  - [ ] Follow naming convention: `_handler_name(self) -> None:`
  - [ ] Use appropriate mixin class (ROI → `gui_roi_crop.py`, Display → `gui_controls_display.py`, etc.)
  - [ ] Call `self._refresh_image()` or appropriate update method if changes display

- [ ] **Testing** (optional but recommended):
  - [ ] Add to [feature_control_matrix.md](feature_control_matrix.md) with signal info
  - [ ] Document handler method signature and behavior

---

## File Cross-Reference

| Signal Type | File Patterns |
|------------|--------------|
| Menu actions | `ui_actions.py` → `gui_ui_setup.py` (~line 595-700) |
| Dock widget buttons | `ui_docks.py` → `gui_events.py` (~line 80-110) |
| ROI manager | `gui_events.py:97-103` → `gui_controls_roi.py` |
| Results buttons | `gui_events.py:104-112` → `gui_controls_results.py` |
| Scalebar settings | `gui_ui_setup.py:666-672` → `gui_controls_display.py` |
| Density panel | `gui_ui_setup.py:673-681` → `gui_controls_density.py` |

---

## Common Pitfalls

1. **Forgetting to wire** - Action defined in `ui_actions.py` but not connected in `gui_ui_setup.py`
   - **Fix:** Add `.triggered.connect()` in the "Hooks for menus" section

2. **Wrong mixin file** - Putting handler in wrong mixin class
   - **Fix:** Check where related handlers are (ROI→`gui_roi_crop.py`, etc.)

3. **Forgetting refresh** - Handler runs but display doesn't update
   - **Fix:** Call `self._refresh_image()` at end of handler if display should change

4. **Wrong signal** - Using `.triggered` for button instead of `.clicked`
   - **Fix:** Check action type; actions use `.triggered`, buttons use `.clicked`

5. **No safety check on optional items** - Wiring actions that might not exist
   - **Fix:** Use `if ... is not None:` or `if hasattr(self, ...):` before connecting
