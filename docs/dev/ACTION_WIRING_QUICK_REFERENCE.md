# Quick Reference: Action Wiring Locations

## Current Status of Your Multi-Image ROI Actions

| Action | File | Line | Status |
|--------|------|------|--------|
| `copy_roi_to_all_act` | `ui_actions.py` | 130 | ✅ Defined |
| `save_roi_template_act` | `ui_actions.py` | 131 | ✅ Defined |
| `apply_roi_template_act` | `ui_actions.py` | 132 | ✅ Defined |
| | | | |
| `_copy_roi_to_all_images()` | `gui_roi_crop.py` | 419 | ✅ Implemented |
| `_save_roi_template()` | `gui_roi_crop.py` | 461 | ✅ Implemented |
| `_apply_roi_template()` | `gui_roi_crop.py` | 494 | ✅ Implemented |
| | | | |
| Wiring in gui_ui_setup | `gui_ui_setup.py` | N/A | ⏳ **NEEDED** |

---

## What's Missing: Action Wiring

Your actions are **defined** and **handlers are implemented**, but they're not **wired to the signals** in `gui_ui_setup.py`.

### Required Addition to `gui_ui_setup.py`

**Location:** After line 617 (in the "Hooks for menus" section)

```python
# Around line 617, add:
self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
self.save_roi_template_act.triggered.connect(self._save_roi_template)
self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
```

Or use the alternative pattern if you prefer dict-based approach:

```python
# In ui_actions.py, add to returned dict (after line 180):
actions = {
    ...
    "copy_roi_to_all": self.copy_roi_to_all_act,
    "save_roi_template": self.save_roi_template_act,
    "apply_roi_template": self.apply_roi_template_act,
}

# Then in gui_ui_setup.py (line 82-84 area):
copy_roi_to_all_act = actions.get("copy_roi_to_all")
save_roi_template_act = actions.get("save_roi_template")
apply_roi_template_act = actions.get("apply_roi_template")

# Then wire (after line 617):
if copy_roi_to_all_act:
    copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
if save_roi_template_act:
    save_roi_template_act.triggered.connect(self._save_roi_template)
if apply_roi_template_act:
    apply_roi_template_act.triggered.connect(self._apply_roi_template)
```

---

## Key Files and Line Ranges

### 1. ui_actions.py - Where Actions Are Defined

**File:** `src/phage_annotator/ui_actions.py`

| Section | Lines | Pattern |
|---------|-------|---------|
| Menu creation | 100-150 | `menu.addAction("Label")` → stored as `self.{name}_act` |
| Actions dictionary | 175-190 | Optional: Add to dict if needed in setup |
| Return statement | 191+ | Return `actions` and `dock_panels_menu` |

**Your actions:** Lines 128-132 (Tools menu, already added ✅)

```python
# Line 128
self.clear_roi_act = tools_menu.addAction("Clear ROI")

# Lines 130-132 (Your new actions)
self.copy_roi_to_all_act = tools_menu.addAction("Copy ROI to all images")
self.save_roi_template_act = tools_menu.addAction("Save ROI as template")
self.apply_roi_template_act = tools_menu.addAction("Apply ROI template…")
```

### 2. gui_ui_setup.py - Where Signals Are Wired

**File:** `src/phage_annotator/gui_ui_setup.py`

| Section | Lines | Purpose |
|---------|-------|---------|
| Get actions from dict | 61-85 | Unpack actions dict: `copy_display_act = actions["copy_display"]` |
| Direct self refs | 82-84 | Get from self: `clear_roi_act = self.clear_roi_act` |
| Signal wiring | 595-700 | Connect signals to handlers: `action.triggered.connect(self._handler)` |

**Wiring location for your actions:** After line 617

Current pattern at line 617:
```python
clear_roi_act.triggered.connect(self._clear_roi)
```

Add yours after this:
```python
self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
self.save_roi_template_act.triggered.connect(self._save_roi_template)
self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
```

### 3. Handler Mixins - Where Methods Are Implemented

| Domain | File | Examples |
|--------|------|----------|
| ROI | [gui_roi_crop.py](gui_roi_crop.py) | `_clear_roi()`, `_copy_roi_to_all_images()`, `_save_roi_template()`, `_apply_roi_template()` |
| Display | `gui_controls_display.py` | `_copy_display_settings()` |
| Results | `gui_controls_results.py` | `_results_measure_current()` |
| File I/O | `gui_actions.py` | `_open_files()`, `_save_csv()` |
| UI State | `ui_docks.py` | `_toggle_overlay()`, `_reset_layout()` |
| Events | `gui_events.py` | `_bind_events()` (wires dock widget buttons) |

**Your handlers:** `gui_roi_crop.py` lines 419-534 (already implemented ✅)

---

## Implementation Checklist

- [x] Actions defined in `ui_actions.py:128-132`
- [x] Handlers implemented in `gui_roi_crop.py:419-534`
- [ ] **Signal wiring in `gui_ui_setup.py` (MISSING)**
  - Add lines after 617:
    ```python
    self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
    self.save_roi_template_act.triggered.connect(self._save_roi_template)
    self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
    ```

---

## Example: Complete Pattern from Clear ROI

Here's the complete three-step pattern using your `clear_roi` (which is fully wired):

### Step 1: Define in ui_actions.py (line 128)
```python
self.clear_roi_act = tools_menu.addAction("Clear ROI")
```

### Step 2: Wire in gui_ui_setup.py (line 617)
```python
clear_roi_act = self.clear_roi_act  # Line 84 (get the action)
clear_roi_act.triggered.connect(self._clear_roi)  # Line 617 (wire signal)
```

### Step 3: Handler in gui_roi_crop.py (line 23)
```python
def _clear_roi(self) -> None:
    """Clear the active ROI selection (P3.3: confirmation added)."""
    if self._settings.value("confirmClearROI", True, type=bool):
        reply = QtWidgets.QMessageBox.question(
            self, "Clear ROI", "Clear the current ROI selection?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
    self.controller.clear_roi()
    self._sync_roi_controls()
    self._refresh_image()
```

---

## All Action Wiring Locations in gui_ui_setup.py

### File Menu Actions (lines 598-609)
- `open_files_act` → `_open_files()`
- `open_folder_act` → `_open_folder()`
- `load_ann_current_act` → `_load_annotations_current()`
- `load_ann_multi_act` → `_load_annotations_multi()`
- `load_ann_all_act` → `_load_annotations_all()`
- `reload_ann_act` → `_reload_annotations_current()`
- `save_csv_act` → `_save_csv()`
- `save_json_act` → `_save_json()`
- `export_view_act` → `_export_view_dialog()`
- `save_proj_act` → `_save_project()`
- `load_proj_act` → `_load_project()`

### Edit Menu Actions (lines 609-610, 660-661)
- `prefs_act` → `_show_preferences_dialog()`
- `reset_confirms_act` → `_reset_confirmations()`
- `copy_display_act` → `_copy_display_settings()` (line 660)
- `measure_act` → `_results_measure_current()` (line 661)

### Tools Menu Actions (lines 616-619)
- `show_roi_handles_act` → `_toggle_roi_handles()` (with `.toggled` not `.triggered`)
- `clear_roi_act` → `_clear_roi()` (line 617)
- `clear_hist_cache_act` → `_clear_histogram_cache()` (line 619)
- **YOUR ACTIONS HERE** (need to add after line 617)

### View/Window Menu Actions (lines 621-633)
- `toggle_profile_act` → `_toggle_profile_panel()`
- `toggle_hist_act` → `_toggle_hist_panel()`
- `toggle_left_act` → `_toggle_left_pane()`
- `toggle_settings_act` → `_toggle_settings_pane()`
- `link_zoom_act` → `_on_link_zoom_menu()`
- `reset_layout_act` → `_reset_layout()`
- `save_layout_act` → `_save_layout_default()`
- `toggle_overlay_act` → `_toggle_overlay()`
- Layout preset actions (4 items)

### Analyze Menu Actions (lines 642-650)
- `show_profiles_act` → `_show_profile_dialog()`
- `show_bleach_act` → `_show_bleach_dialog()`
- `show_table_act` → `_show_table_dialog()`
- `threshold_act` → `_show_threshold_panel()` (conditional)
- `analyze_particles_act` → `_show_analyze_particles_panel()` (conditional)
- `smlm_act` → `_show_smlm_panel()` (conditional)
- `deepstorm_act` → `_show_deepstorm_panel()` (conditional)
- etc.

### Edit Actions - Undo/Redo (lines 656-657)
- `undo_act` → `undo_last_action()`
- `redo_act` → `redo_last_action()`

### Other Menu Actions (lines 611-615)
- `exit_act` → `close()`
- `about_act` → `_show_about()`
- `shortcuts_act` → `_show_keyboard_shortcuts()`

### Panel-Specific Buttons (lines 673-681+)
- `density_panel.model_browse_btn` → `_density_pick_model()` (`.clicked` signal)
- `density_panel.load_btn` → `_density_load_model()`
- etc.

---

## Summary

Your multi-image ROI actions need **one more step**: wiring in `gui_ui_setup.py`.

Add these three lines after line 617:
```python
self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
self.save_roi_template_act.triggered.connect(self._save_roi_template)
self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
```

That's all! The actions are already defined, handlers are already implemented.
