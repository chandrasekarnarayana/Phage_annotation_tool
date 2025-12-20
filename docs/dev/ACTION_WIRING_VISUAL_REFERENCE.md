# Action Wiring Visual Reference Card

## The Complete Flow (3 Files, 3 Steps)

```
┌─────────────────────────────────────────────────────────────────┐
│                    THREE-FILE PATTERN                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STEP 1: DEFINE                                                 │
│  ════════════════════════════════════════════════════════════  │
│  File: src/phage_annotator/ui_actions.py                       │
│  Lines: 128-132                                                 │
│                                                                 │
│  tools_menu = menubar.addMenu("&Tools")                         │
│  self.clear_roi_act = tools_menu.addAction("Clear ROI")         │
│  self.copy_roi_to_all_act = tools_menu.addAction(...)          │
│  self.save_roi_template_act = tools_menu.addAction(...)        │
│  self.apply_roi_template_act = tools_menu.addAction(...)       │
│                                                                 │
│  ✅ DONE                                                         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STEP 2: WIRE (← YOU ARE HERE)                                  │
│  ════════════════════════════════════════════════════════════  │
│  File: src/phage_annotator/gui_ui_setup.py                     │
│  Lines: 617 → INSERT AFTER LINE 619                            │
│                                                                 │
│  clear_roi_act.triggered.connect(self._clear_roi)    # Exists  │
│  ← ADD THESE THREE LINES:                                      │
│  self.copy_roi_to_all_act.triggered.connect(...)               │
│  self.save_roi_template_act.triggered.connect(...)             │
│  self.apply_roi_template_act.triggered.connect(...)            │
│                                                                 │
│  ⏳ MISSING                                                      │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STEP 3: IMPLEMENT                                              │
│  ════════════════════════════════════════════════════════════  │
│  File: src/phage_annotator/gui_roi_crop.py                     │
│  Lines: 23-534                                                  │
│                                                                 │
│  def _clear_roi(self) -> None: ...           # Line 23          │
│  def _copy_roi_to_all_images(self) -> None:  # Line 419         │
│  def _save_roi_template(self) -> None:       # Line 461         │
│  def _apply_roi_template(...) -> None:       # Line 494         │
│                                                                 │
│  ✅ DONE                                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Signal Types Cheat Sheet

```
╔═════════════════════════════════════════════════════════════════╗
║                     SIGNAL TYPE REFERENCE                       ║
╠═════════════════════════════════════════════════════════════════╣
║                                                                 ║
║  ACTION SIGNALS (Menu items, toolbar actions)                  ║
║  ───────────────────────────────────────────                   ║
║  action.triggered.connect(handler)                             ║
║  └─ Handler signature: def handler(self) -> None:              ║
║                                                                 ║
║  BUTTON SIGNALS (Buttons, icon buttons)                        ║
║  ───────────────────────────────────────────                   ║
║  button.clicked.connect(handler)                               ║
║  └─ Handler signature: def handler(self) -> None:              ║
║                                                                 ║
║  CHECKBOX/TOGGLE SIGNALS                                       ║
║  ───────────────────────────────────────────                   ║
║  checkbox.toggled.connect(handler)                             ║
║  └─ Handler signature: def handler(self, checked: bool) -> None║
║                                                                 ║
║  SPINBOX/SLIDER SIGNALS                                        ║
║  ───────────────────────────────────────────                   ║
║  spinbox.valueChanged.connect(handler)                         ║
║  └─ Handler signature: def handler(self, value: int) -> None:  ║
║                                                                 ║
║  COMBO BOX SIGNALS                                             ║
║  ───────────────────────────────────────────                   ║
║  combo.currentTextChanged.connect(handler)                     ║
║  └─ Handler signature: def handler(self, text: str) -> None:   ║
║                                                                 ║
╚═════════════════════════════════════════════════════════════════╝
```

---

## File Locations at a Glance

```
PHAGE_ANNOTATION_TOOL/
├── src/phage_annotator/
│   ├── ui_actions.py
│   │   ├─ Line 128: self.clear_roi_act = ...
│   │   ├─ Line 130: self.copy_roi_to_all_act = ...
│   │   ├─ Line 131: self.save_roi_template_act = ...
│   │   ├─ Line 132: self.apply_roi_template_act = ...
│   │   └─ Line 175-190: Optional - add to actions dict
│   │
│   ├── gui_ui_setup.py
│   │   ├─ Line 61-85: Unpack actions from dict
│   │   ├─ Line 617: clear_roi_act.triggered.connect(...) ✓
│   │   ├─ Line 620: [INSERT YOUR 3 LINES HERE] ← YOU ARE HERE
│   │   ├─ Line 673+: Density panel buttons (for reference)
│   │   └─ NOTE: All .triggered.connect() calls in lines 598-700
│   │
│   ├── gui_roi_crop.py
│   │   ├─ Line 23: def _clear_roi(self) -> None:
│   │   ├─ Line 419: def _copy_roi_to_all_images(self) -> None:
│   │   ├─ Line 461: def _save_roi_template(self) -> None:
│   │   └─ Line 494: def _apply_roi_template(self, ...) -> None:
│   │
│   ├── gui_events.py
│   │   └─ Line 97-112: Widget button pattern reference
│   │
│   ├── gui_controls_display.py
│   │   └─ Line 234-264: Dialog-based action pattern
│   │
│   └── gui_controls_results.py
│       └─ Line 39-67: Simple handler pattern
│
└── docs/dev/
    ├── ACTION_WIRING_PATTERN.md (comprehensive reference)
    ├── ACTION_WIRING_QUICK_REFERENCE.md (table format)
    └── ACTION_WIRING_SEARCH_RESULTS.md (this directory contents)
```

---

## The Missing Code (Your Task)

### Current State (Line 617-620 in gui_ui_setup.py):

```python
617: clear_roi_act.triggered.connect(self._clear_roi)
618: if clear_hist_cache_act is not None:
619:     clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)
620: 
621: self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
```

### What You Need to Add (Insert between lines 619 and 621):

```python
617: clear_roi_act.triggered.connect(self._clear_roi)
618: if clear_hist_cache_act is not None:
619:     clear_hist_cache_act.triggered.connect(self._clear_histogram_cache)
620: 
← INSERT HERE →
621: self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
622: self.save_roi_template_act.triggered.connect(self._save_roi_template)
623: self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
624: 
625: self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
```

Or keep blank line:

```python
620: 
621: # Multi-image ROI management
622: self.copy_roi_to_all_act.triggered.connect(self._copy_roi_to_all_images)
623: self.save_roi_template_act.triggered.connect(self._save_roi_template)
624: self.apply_roi_template_act.triggered.connect(self._apply_roi_template)
625: 
626: self.toggle_profile_act.triggered.connect(self._toggle_profile_panel)
```

---

## All Patterns in Your Codebase

### ✅ Simple Action Wiring
```python
action.triggered.connect(self._handler)
```
Examples: Lines 598-617 in gui_ui_setup.py

### ✅ Safe Optional Action Wiring
```python
action = actions.get("key")
if action is not None:
    action.triggered.connect(self._handler)
```
Example: Line 618-619 in gui_ui_setup.py

### ✅ Direct Self-Attribute Wiring
```python
self.action.triggered.connect(self._handler)
```
Example: Line 621+ in gui_ui_setup.py

### ✅ Toggled Signal (Boolean Handler)
```python
self.checkbox.toggled.connect(self._handler)
# def _handler(self, checked: bool) -> None: ...
```
Example: Line 616 in gui_ui_setup.py

### ✅ Button Click Signal
```python
widget.button.clicked.connect(self._handler)
```
Example: Line 97-112 in gui_events.py, Line 673+ in gui_ui_setup.py

### ✅ Conditional Attribute Wiring
```python
if hasattr(self, "optional_action"):
    self.optional_action.triggered.connect(self._handler)
```
Example: Line 642-650 in gui_ui_setup.py

### ✅ Lambda for Parameterized Calls
```python
action.triggered.connect(lambda: self.apply_preset("Annotate"))
```
Example: Line 630-633 in gui_ui_setup.py

### ✅ Value-Passing Signals
```python
spinbox.valueChanged.connect(self._handler)
# def _handler(self, value: int) -> None: ...
```
Example: Line 666+ in gui_ui_setup.py

---

## Verification Checklist

After making your changes, verify:

- [ ] Code compiles without syntax errors
- [ ] Tools menu shows your 3 new items
- [ ] Click each menu item without crashes
- [ ] Each action calls its handler correctly
- [ ] Handler logic executes as expected
- [ ] No log errors appear
- [ ] Display updates correctly when needed

---

## Cross-Reference by Domain

### ROI-Related Actions & Handlers
| Action | File | Line | Handler | File | Line |
|--------|------|------|---------|------|------|
| `clear_roi_act` | `ui_actions.py` | 128 | `_clear_roi()` | `gui_roi_crop.py` | 23 |
| `copy_roi_to_all_act` | `ui_actions.py` | 130 | `_copy_roi_to_all_images()` | `gui_roi_crop.py` | 419 |
| `save_roi_template_act` | `ui_actions.py` | 131 | `_save_roi_template()` | `gui_roi_crop.py` | 461 |
| `apply_roi_template_act` | `ui_actions.py` | 132 | `_apply_roi_template()` | `gui_roi_crop.py` | 494 |

### Display-Related Actions & Handlers
| Action | File | Line | Handler | File | Line |
|--------|------|------|---------|------|------|
| `copy_display_act` | `ui_actions.py` | 122 | `_copy_display_settings()` | `gui_controls_display.py` | 234 |
| `measure_act` | `ui_actions.py` | 124 | `_results_measure_current()` | `gui_controls_results.py` | 39 |

---

## Signal Flow Diagram

```
User clicks menu item
        ↓
QAction sends .triggered signal
        ↓
Qt slots system calls connected handler method
        ↓
Handler executes business logic
        ↓
Handler calls self._refresh_image() or similar update
        ↓
Display updates
```

Example for your actions:

```
User selects "Tools > Copy ROI to all images"
        ↓
self.copy_roi_to_all_act.triggered signal fires
        ↓
Qt calls self._copy_roi_to_all_images()
        ↓
Method iterates images and copies ROI
        ↓
Calls self._refresh_image()
        ↓
Display updates with ROI on all images
```

---

## Key Lines Reference

| What | File | Line | Status |
|------|------|------|--------|
| Define actions | `ui_actions.py` | 128-132 | ✅ Done |
| Wire signals | `gui_ui_setup.py` | 620 | ⏳ **MISSING** |
| Implement handlers | `gui_roi_crop.py` | 23-534 | ✅ Done |
| Verify in docs | `feature_control_matrix.md` | TBD | ⏳ Optional |

---

## Remember

1. **ui_actions.py** = CREATE action objects (menus, buttons)
2. **gui_ui_setup.py** = WIRE signals to methods
3. **gui_roi_crop.py** = IMPLEMENT the actual logic

You've done steps 1 and 3. Just need step 2!

---

## Helpful Commands

### Find where triggered.connect is used
```bash
grep -n "triggered.connect" src/phage_annotator/*.py
```

### Find where clicked.connect is used
```bash
grep -n "clicked.connect" src/phage_annotator/*.py
```

### Find your action definitions
```bash
grep -n "copy_roi_to_all\|save_roi_template\|apply_roi_template" src/phage_annotator/*.py
```

### Find your handler implementations
```bash
grep -n "def _copy_roi_to_all_images\|def _save_roi_template\|def _apply_roi_template" src/phage_annotator/*.py
```
