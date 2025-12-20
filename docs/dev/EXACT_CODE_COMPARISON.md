# Exact Code Comparison: What Exists vs. What You Need

## Summary
This document shows **exactly** where your actions are and what's missing.

---

## File 1: ui_actions.py - Action Definitions ✅ COMPLETE

### Exact Location: Lines 128-132

**Current Code:**
```python
120:     self.undo_act.setEnabled(False)
121:     self.redo_act.setEnabled(False)
122:     self.copy_display_act = edit_menu.addAction("Copy Display Settings…")
123:     self.reset_confirms_act = edit_menu.addAction("Reset confirmations")
124:     self.measure_act = edit_menu.addAction("Measure (Results)")
125:     self.measure_act.setShortcut("Ctrl+M")
126:
127:     tools_menu = menubar.addMenu("&Tools")
128:     self.clear_roi_act = tools_menu.addAction("Clear ROI")
129:     # P5.2: Multi-image ROI management
130:     self.copy_roi_to_all_act = tools_menu.addAction("Copy ROI to all images")
131:     self.save_roi_template_act = tools_menu.addAction("Save ROI as template")
132:     self.apply_roi_template_act = tools_menu.addAction("Apply ROI template…")
133:     tools_menu.addSeparator()
134:     self.clear_hist_cache_act = tools_menu.addAction("Clear histogram cache")
```

✅ **Status:** All three actions are already defined at lines 130-132

---

## File 2: gui_ui_setup.py - Signal Wiring ⏳ INCOMPLETE

### Location: Line 617 onwards in the "Hooks for menus" section

#### What EXISTS (lines 615-625):

```python
615:     exit_act.triggered.connect(self.close)
616:     show_roi_handles_act.toggled.connect(self._toggle_roi_handles)
617:     clear_roi_act.triggered.connect(self._clear_roi)
618:     if clear_hist_cache_act is not None:
619:         clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)
620:
621:     self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
622:     self.toggle_hist_act.triggered.connect(self._toggle_hist_panel)
623:     self.toggle_left_act.triggered.connect(self._toggle_left_pane)
624:     self.toggle_settings_act.triggered.connect(self._toggle_settings_pane)
625:     self.link_zoom_act.triggered.connect(self._on_link_zoom_menu)
```

#### What's MISSING (insert at line 620):

```python
620:     # Multi-image ROI management (P5.2)
621:     self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
622:     self.save_roi_template_act.triggered.connect(self._save_roi_template)
623:     self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
624:
```

#### What it should look like AFTER changes:

```python
615:     exit_act.triggered.connect(self.close)
616:     show_roi_handles_act.toggled.connect(self._toggle_roi_handles)
617:     clear_roi_act.triggered.connect(self._clear_roi)
618:     if clear_hist_cache_act is not None:
619:         clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)
620:
621:     # Multi-image ROI management (P5.2)
622:     self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
623:     self.save_roi_template_act.triggered.connect(self._save_roi_template)
624:     self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
625:
626:     self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
627:     self.toggle_hist_act.triggered.connect(self._toggle_hist_panel)
628:     self.toggle_left_act.triggered.connect(self._toggle_left_pane)
629:     self.toggle_settings_act.triggered.connect(self._toggle_settings_pane)
630:     self.link_zoom_act.triggered.connect(self._on_link_zoom_menu)
```

⏳ **Status:** Missing lines 621-624. All subsequent line numbers shift by 4.

---

## File 3: gui_roi_crop.py - Handler Implementations ✅ COMPLETE

### Location: Lines 23-534

#### Handler 1: `_clear_roi()` (Line 23)

```python
23:     def _clear_roi(self) -> None:
24:         """Clear the active ROI selection (P3.3: confirmation added)."""
25:         # Check if confirmation is needed
26:         if self._settings.value("confirmClearROI", True, type=bool):
27:             reply = QtWidgets.QMessageBox.question(
28:                 self,
29:                 "Clear ROI",
30:                 "Clear the current ROI selection?",
31:                 QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
32:                 QtWidgets.QMessageBox.StandardButton.No
33:             )
34:             if reply != QtWidgets.QMessageBox.StandardButton.Yes:
35:                 return
36:         self.controller.clear_roi()
37:         self._sync_roi_controls()
38:         self._refresh_image()
```

✅ **Status:** Fully implemented

#### Handler 2: `_copy_roi_to_all_images()` (Line 419)

```python
419:     def _copy_roi_to_all_images(self) -> None:
420:         """Copy the active ROI to all other images (P5.2)."""
421:         # Get active ROI for current image
422:         active = self.roi_manager.get_active(self.primary_image.id)
423:         if active is None:
423:             return
424:         # Apply to all images except current
425:         count = 0
426:         for img in self.images:
427:             if img.id != self.primary_image.id:
428:                 self.roi_manager.add_roi(img.id, deepcopy(active))
429:                 count += 1
430:         self._set_status(f"Copied ROI to {count} images")
431:         self._refresh_roi_manager()
432:         self.recorder.record("copy_roi_to_all_images", {"count": count})
```

✅ **Status:** Fully implemented

#### Handler 3: `_save_roi_template()` (Line 461)

```python
461:     def _save_roi_template(self) -> None:
462:         """Save active ROI as a named template for reuse across images (P5.2)."""
463:         active = self.roi_manager.get_active(self.primary_image.id)
464:         if active is None:
465:             self._set_status("No active ROI to save as template")
466:             return
467:         # Dialog for template name
468:         name, ok = QtWidgets.QInputDialog.getText(
469:             self, "Save ROI Template", "Template name:", text=active.name
470:         )
471:         if ok and name:
472:             self.roi_manager.save_roi_template(name, active)
473:             self.recorder.record("save_roi_template", {"name": name})
474:             self._set_status(f"Saved ROI template: {name}")
475:         else:
476:             self._set_status("Save cancelled")
```

✅ **Status:** Fully implemented

#### Handler 4: `_apply_roi_template()` (Line 494)

```python
494:     def _apply_roi_template(self, template_name: str = None) -> None:
495:         """Apply a saved ROI template to the current image (P5.2)."""
496:         templates = self.roi_manager.list_roi_templates()
497:         if not templates:
497:             self._set_status("No ROI templates available")
498:             return
499:         # Dialog to select template if not provided
500:         if template_name is None:
501:             choice, ok = QtWidgets.QInputDialog.getItem(
502:                 self, "Apply ROI Template", "Select template:",
503:                 templates, editable=False
504:             )
505:             if not ok or not choice:
506:                 self._set_status("Apply template cancelled")
506:                 return
507:             template_name = choice
508:         # Load and apply template
509:         template = self.roi_manager.load_roi_template(template_name)
510:         if template is None:
511:             self._set_status(f"Template not found: {template_name}")
512:             return
513:         self.roi_manager.add_roi(self.primary_image.id, deepcopy(template))
514:         self._set_status(f"Applied template: {template_name}")
515:         self._sync_active_roi(template)
516:         self._refresh_roi_manager()
517:         self._refresh_image()
518:         self.recorder.record("apply_roi_template", {"template": template_name})
```

✅ **Status:** Fully implemented

---

## Summary Table

| Item | File | Line(s) | Status | Details |
|------|------|---------|--------|---------|
| **Define: clear_roi_act** | ui_actions.py | 128 | ✅ Done | Already in Tools menu |
| **Define: copy_roi_to_all_act** | ui_actions.py | 130 | ✅ Done | Already in Tools menu |
| **Define: save_roi_template_act** | ui_actions.py | 131 | ✅ Done | Already in Tools menu |
| **Define: apply_roi_template_act** | ui_actions.py | 132 | ✅ Done | Already in Tools menu |
| | | | | |
| **Wire: clear_roi** | gui_ui_setup.py | 617 | ✅ Done | Already connected |
| **Wire: copy_roi_to_all** | gui_ui_setup.py | 620* | ⏳ Missing | Need to add |
| **Wire: save_roi_template** | gui_ui_setup.py | 621* | ⏳ Missing | Need to add |
| **Wire: apply_roi_template** | gui_ui_setup.py | 622* | ⏳ Missing | Need to add |
| | | | | |
| **Implement: _clear_roi()** | gui_roi_crop.py | 23-38 | ✅ Done | Full implementation |
| **Implement: _copy_roi_to_all_images()** | gui_roi_crop.py | 419-432 | ✅ Done | Full implementation |
| **Implement: _save_roi_template()** | gui_roi_crop.py | 461-476 | ✅ Done | Full implementation |
| **Implement: _apply_roi_template()** | gui_roi_crop.py | 494-518 | ✅ Done | Full implementation |

*Line numbers for wiring will shift by 4 after insertion (620, 621, 622 become 624, 625, 626)

---

## The Exact Edit Needed

**File:** `src/phage_annotator/gui_ui_setup.py`

**Find this code block (lines 615-625):**
```python
        exit_act.triggered.connect(self.close)
        show_roi_handles_act.toggled.connect(self._toggle_roi_handles)
        clear_roi_act.triggered.connect(self._clear_roi)
        if clear_hist_cache_act is not None:
            clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)

        self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
```

**Replace with this (adds 4 lines):**
```python
        exit_act.triggered.connect(self.close)
        show_roi_handles_act.toggled.connect(self._toggle_roi_handles)
        clear_roi_act.triggered.connect(self._clear_roi)
        if clear_hist_cache_act is not None:
            clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)

        # Multi-image ROI management (P5.2)
        self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
        self.save_roi_template_act.triggered.connect(self._save_roi_template)
        self.apply_roi_template_act.triggered.connect(self._apply_roi_template)

        self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
```

That's it!

---

## Validation Checklist

After making the change, verify:

- [ ] File `gui_ui_setup.py` still has valid Python syntax
- [ ] Line count increased by 4
- [ ] Indentation matches surrounding code (8 spaces)
- [ ] No syntax errors (red squiggles)
- [ ] Application launches without import errors
- [ ] Tools menu displays all items
- [ ] Clicking each item doesn't crash
- [ ] Handlers execute correctly

---

## Pattern Confirmation

Your change follows the exact same pattern as the existing line 617:

**Existing Pattern:**
```python
617: clear_roi_act.triggered.connect(self._clear_roi)
```

**Your Pattern:**
```python
622: self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
623: self.save_roi_template_act.triggered.connect(self._save_roi_template)
624: self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
```

✅ Identical pattern, just different action and handler names.

---

## All Clear ROI References (for context)

**Defined in ui_actions.py (line 128):**
```python
self.clear_roi_act = tools_menu.addAction("Clear ROI")
```

**Wired in gui_ui_setup.py (line 617):**
```python
clear_roi_act.triggered.connect(self._clear_roi)
```

**Implemented in gui_roi_crop.py (line 23):**
```python
def _clear_roi(self) -> None:
    ...
```

→ Your three new actions follow the **exact same pattern**.

---

## Command to Verify

After editing, run in terminal:
```bash
cd /home/cs/Desktop/Phage_annotation_tool
python -m py_compile src/phage_annotator/gui_ui_setup.py
echo "✓ Syntax OK" || echo "✗ Syntax Error"
```

Should print: `✓ Syntax OK`
