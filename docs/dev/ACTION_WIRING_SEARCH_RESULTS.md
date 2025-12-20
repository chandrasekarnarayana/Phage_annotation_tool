# Action Wiring Search Results Summary

## Summary
Found all the patterns for wiring menu actions to handlers in phage_annotator. Your multi-image ROI actions are **defined** and **implemented** but need **signal wiring**.

---

## Key Findings

### 1. Where Actions are Created: `ui_actions.py`

**File:** [src/phage_annotator/ui_actions.py](src/phage_annotator/ui_actions.py)

**Your actions (lines 128-132):**
```python
tools_menu = menubar.addMenu("&Tools")
self.clear_roi_act = tools_menu.addAction("Clear ROI")
# P5.2: Multi-image ROI management
self.copy_roi_to_all_act = tools_menu.addAction("Copy ROI to all images")
self.save_roi_template_act = tools_menu.addAction("Save ROI as template")
self.apply_roi_template_act = tools_menu.addAction("Apply ROI template…")
```

✅ **Status:** Already defined

---

### 2. Where Actions are Wired: `gui_ui_setup.py`

**File:** [src/phage_annotator/gui_ui_setup.py](src/phage_annotator/gui_ui_setup.py)

**Wiring section begins at line 595** with comment `# Hooks for menus`

**Your wiring should go around line 617** (after `clear_roi_act` wiring):

```python
615:  exit_act.triggered.connect(self.close)
616:  show_roi_handles_act.toggled.connect(self._toggle_roi_handles)
617:  clear_roi_act.triggered.connect(self._clear_roi)
618:  if clear_hist_cache_act is not None:
619:      clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)
```

⏳ **Status:** MISSING - You need to add these 3 lines after line 619:
```python
self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
self.save_roi_template_act.triggered.connect(self._save_roi_template)
self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
```

---

### 3. Where Handlers are Implemented: `gui_roi_crop.py`

**File:** [src/phage_annotator/gui_roi_crop.py](src/phage_annotator/gui_roi_crop.py)

**Handler locations (lines 23-534):**

| Handler | Line | Signature |
|---------|------|-----------|
| `_clear_roi()` | 23 | `def _clear_roi(self) -> None:` |
| `_copy_roi_to_all_images()` | 419 | `def _copy_roi_to_all_images(self) -> None:` |
| `_save_roi_template()` | 461 | `def _save_roi_template(self) -> None:` |
| `_apply_roi_template()` | 494 | `def _apply_roi_template(self, template_name: str = None) -> None:` |

✅ **Status:** All implemented

---

## All `.triggered.connect()` Patterns Found

### In ui_actions.py (Global Actions)
Line 154: `self.command_palette_act.triggered.connect(self._show_command_palette)`
Line 157: `self.reset_view_act.triggered.connect(self.reset_all_view)`
Line 160: `self._dev_demo_job_act.triggered.connect(self._run_demo_job)`

### In ui_docks.py (Dock-specific Actions)
Line 115: `self.view_overlay_act.triggered.connect(self._toggle_overlay)`
Line 116: `self.reset_layout_act.triggered.connect(self._reset_layout)`
Line 117: `self.save_layout_default_act.triggered.connect(self._save_layout_default)`
Line 118-121: Preset layout actions with lambdas

### In gui_ui_setup.py (Main Window Wiring) - **YOUR TARGET**
Lines 598-619: File/Tools/Edit menu actions
Lines 621-633: View/Window menu actions
Lines 642-650: Analyze menu actions
Lines 656-662: Undo/redo and display actions
Lines 666-681+: Panel-specific button wiring

### In recorder.py (Dynamic Action Creation)
Line 50: `action.triggered.connect(lambda _checked=False, n=name: self.record(n))`

---

## All `.clicked.connect()` Patterns Found

### In gui_events.py (Widget Button Wiring)

**ROI Manager Buttons (lines 97-103):**
```python
widget.add_btn.clicked.connect(self._roi_mgr_add)
widget.del_btn.clicked.connect(self._roi_mgr_delete)
widget.rename_btn.clicked.connect(self._roi_mgr_rename)
widget.dup_btn.clicked.connect(self._roi_mgr_duplicate)
widget.save_btn.clicked.connect(self._roi_mgr_save)
widget.load_btn.clicked.connect(self._roi_mgr_load)
widget.measure_btn.clicked.connect(self._roi_mgr_measure)
```

**Results Widget Buttons (lines 104-112):**
```python
rw.measure_btn.clicked.connect(self._results_measure_current)
rw.measure_t_btn.clicked.connect(self._results_measure_over_time)
rw.clear_btn.clicked.connect(self._results_clear)
rw.copy_btn.clicked.connect(self._results_copy)
rw.export_btn.clicked.connect(self._results_export)
```

### In ui_docks.py (Log Panel Buttons)
Line 549: `copy_btn.clicked.connect(_copy_logs)`
Line 550: `save_btn.clicked.connect(_save_logs)`
Line 551: `clear_btn.clicked.connect(_clear_logs)`

### In gui_ui_setup.py (Panel Buttons)
Lines 673-681+: Density panel buttons
```python
self.density_panel.model_browse_btn.clicked.connect(self._density_pick_model)
self.density_panel.load_btn.clicked.connect(self._density_load_model)
self.density_panel.run_btn.clicked.connect(self._density_run)
self.density_panel.cancel_btn.clicked.connect(self._density_cancel)
...
```

### In other files
`performance_panel.py:76`: `refresh_btn.clicked.connect(self._update_metrics)`
`gui_controls_recorder.py:19-20`: Recorder widget buttons
`metadata_dock.py:50-51`: Metadata dock buttons

---

## Connection Pattern Summary

### Template 1: Simple Menu Action (Most Common)

**File 1 - ui_actions.py:**
```python
menu = menubar.addMenu("&Category")
self.my_action = menu.addAction("Action Label")
self.my_action.setShortcut("Ctrl+K")  # Optional
```

**File 2 - gui_ui_setup.py:**
```python
# Line ~80 (if using dict):
my_action = actions.get("my_action")
# OR
# Line ~84 (direct self):
my_action = self.my_action

# Line ~600+ (wiring):
my_action.triggered.connect(self._my_handler)
```

**File 3 - Appropriate Mixin:**
```python
def _my_handler(self) -> None:
    # Do work
    self._refresh_image()  # If display changed
```

### Template 2: Dialog-Based Action

**Same as Template 1, but handler creates a dialog:**
```python
def _copy_display_settings(self) -> None:
    dlg = QtWidgets.QDialog(self)
    # ... setup dialog ...
    def _apply():
        # Apply changes
        self._refresh_image()
        dlg.accept()
    buttons.accepted.connect(_apply)
    dlg.exec()
```

### Template 3: Optional/Conditional Action

**In gui_ui_setup.py:**
```python
clear_hist_cache_act = actions.get("clear_hist_cache")
if clear_hist_cache_act is not None:
    clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)
```

### Template 4: Widget Button (Not Menu Action)

**In gui_events.py or gui_ui_setup.py:**
```python
self.my_button.clicked.connect(self._my_handler)
```

### Template 5: Toggle/Checkbox

**In gui_ui_setup.py:**
```python
self.my_checkbox.toggled.connect(self._handle_toggle)

def _handle_toggle(self, checked: bool) -> None:
    ...
```

---

## Your Action Implementation Status

### ✅ Completed
1. **Define actions** in `ui_actions.py:128-132`
2. **Implement handlers** in `gui_roi_crop.py:23-534`
3. **Handler method signatures correct** - all take `self` only (or `self, template_name` for apply)

### ⏳ Missing
1. **Wire signals** in `gui_ui_setup.py` after line 619

---

## Code Locations Quick Map

```
src/phage_annotator/
├── ui_actions.py          ← Action definitions (line 128-132)
├── gui_ui_setup.py        ← Signal wiring (line 617, add yours after line 619)
└── gui_roi_crop.py        ← Handler implementations (lines 23-534)
```

---

## Exact Code to Add

**File:** `src/phage_annotator/gui_ui_setup.py`
**Location:** After line 619 (after the `clear_hist_cache_act` block)
**Add:**

```python
self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
self.save_roi_template_act.triggered.connect(self._save_roi_template)
self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
```

---

## Why This Pattern Works

1. **Separation of concerns**: Actions defined in `ui_actions.py`, wiring in `gui_ui_setup.py`, handlers in domain-specific mixins
2. **Reusability**: Actions can be referenced from menus, toolbars, keyboard shortcuts
3. **Testability**: Handlers are pure methods that can be tested separately
4. **Maintainability**: All signal connections in one place (gui_ui_setup.py) makes debugging easy
5. **Qt signal/slot mechanism**: `.triggered.connect()` uses Qt's meta-object system for late binding

---

## Related Files Referenced

| File | Purpose | Your Relevance |
|------|---------|---|
| `src/phage_annotator/ui_actions.py` | Central menu/action definitions | ✅ Your actions defined here |
| `src/phage_annotator/gui_ui_setup.py` | UI construction and signal wiring | ⏳ Add wiring here |
| `src/phage_annotator/gui_roi_crop.py` | ROI-related handlers | ✅ Your handlers here |
| `src/phage_annotator/gui_events.py` | Widget button wiring | Reference for pattern |
| `src/phage_annotator/gui_controls_display.py` | Display handlers | Reference for dialog pattern |
| `src/phage_annotator/gui_controls_results.py` | Results handlers | Reference pattern |
| `src/phage_annotator/gui_controls_roi.py` | ROI manager handlers | Related domain |

---

## Testing Your Implementation

After adding the wiring, verify by:

1. **Check that menus appear**: Tools menu should show your 3 new actions
2. **Click and check**: Each should trigger without errors
3. **Check logs**: Any Python errors will appear in the log panel
4. **Verify functionality**: 
   - Copy ROI to all should work on multiple images
   - Save template should store in roi_manager
   - Apply template should load and apply

---

## Next Steps

1. ✅ Read this document (you're here)
2. ⏳ Add signal wiring to `gui_ui_setup.py` line 620
3. Test the menu items
4. Check [ACTION_WIRING_PATTERN.md](ACTION_WIRING_PATTERN.md) for detailed reference
