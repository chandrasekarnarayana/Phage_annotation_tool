# Modality-Aware B&C System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                 Modality-Aware Display Control System               │
│                                                                     │
│  Provides persistent, modality-level brightness/contrast settings  │
│  that synchronize with per-image, per-panel display state          │
└─────────────────────────────────────────────────────────────────────┘
```

## Layer Architecture

### Layer 1: UI Controls (Qt Widgets)
```
┌─────────────────────────────┐
│   SliderPanelDouble         │  ← NEW: Dual-handle range slider
│   (bc_range_slider)         │
│                             │
│   Min/Max Spinboxes         │
│   - bc_min_spin             │
│   - bc_max_spin             │
│                             │
│   Brightness Slider         │
│   - bc_brightness_slider    │
│                             │
│   Contrast Slider           │
│   - bc_contrast_slider      │
│                             │
│   Preset Buttons            │  ← NEW: Auto, Linear, Log, Sqrt
│   - auto_btn                │
│   - linear_btn              │
│   - log_btn                 │
│   - sqrt_btn                │
└──────────────┬──────────────┘
               │ Qt Signals
               │ (rangeChanged, valueChanged, clicked)
               ↓
```

### Layer 2: DisplayMapping (Session-Level State)
```
┌────────────────────────────────────────────────────┐
│          DisplayMapping (Per-Image, Per-Panel)     │
│                                                    │
│  Structure:                                        │
│  ├─ vmin: int (minimum display value)              │
│  ├─ vmax: int (maximum display value)              │
│  ├─ lut: str | None (color lookup table)           │
│  ├─ gamma: float (gamma correction)                │
│  ├─ brightness: float (brightness adjustment)      │
│  └─ contrast: float (contrast adjustment)          │
│                                                    │
│  Lookup: mapping = display_mapping(image_id, panel)│
│                                                    │
│  Storage: SessionController._display_mappings      │
│           Dict[(image_id, panel) → DisplayMapping] │
└──────────────┬───────────────────────────────────┘
               │ _sync_modality_display_settings()
               │ (Called from every display update method)
               ↓
```

### Layer 3: ModalityDisplaySettings (Modality-Level Persistent State)
```
┌──────────────────────────────────────────────────┐
│    ModalityDisplaySettings (Per-Modality)        │
│                                                  │
│  Structure:                                      │
│  ├─ vmin: int (persistent minimum)               │
│  ├─ vmax: int (persistent maximum)               │
│  ├─ lut: str | None (persistent color map)       │
│  ├─ gamma: float (persistent gamma)              │
│  ├─ projection_axis: str (3D projection axis)    │
│  └─ [other display properties]                   │
│                                                  │
│  Ownership: Part of ModalitySpec                 │
│             For modality in modality_list:       │
│               modality.display_settings.[prop]   │
│                                                  │
│  Purpose: Ensure consistent display across      │
│           all panels/images of same modality     │
└─────────────────────────────────────────────────┘
```

## Component Interactions

### 1. User Changes Dual-Slider Range

```
User drags slider handle from 50 to 40
    ↓
Qt Signal: bc_range_slider.rangeChanged(40, max_val)
    ↓
Event Handler: _on_bc_range_changed(40, max_val)
    ↓
Display Update: _bc_apply_minmax(40, max_val)
    │
    ├─ mapping.vmin = 40
    ├─ mapping.vmax = max_val
    │
    └─→ _sync_modality_display_settings("frame", mapping)
        │
        ├─ Get ModalitySpec for "frame" panel
        ├─ modality_spec.display_settings.vmin = 40
        └─ modality_spec.display_settings.vmax = max_val
            ↓
            _apply_display_mapping()
            ↓
            Renderer applies new mapping
            ↓
            Display updated on screen
```

### 2. Renderer Restores Settings from Modality

```
New panel created or display mapping requested
    ↓
_get_display_mapping(image, panel="support")
    ├─ Check _panel_modality_map for panel
    ├─ Find ModalitySpec for "support"
    │
    ├─ IF modality_spec.display_settings.vmax > vmin:
    │   ├─ mapping.vmin = modality_spec.display_settings.vmin
    │   ├─ mapping.vmax = modality_spec.display_settings.vmax
    │   ├─ mapping.lut = modality_spec.display_settings.lut
    │   └─ mapping.gamma = modality_spec.display_settings.gamma
    │
    └─ ELSE:
        └─ Use auto-range (fallback)
            ↓
            Renderer applies automatically restored settings
```

### 3. Contrast Preset Application

```
User clicks "Log Preset" button
    ↓
Signal: preset_button.clicked()
    ↓
Handler: _apply_preset("log")
    ├─ Compute log-transformed range
    │   data_range = (data_min, data_max)
    │   log_range = (log10(data_min), log10(data_max))
    │
    ├─ blockSignals() on sliders (prevent feedback)
    ├─ Update bc_slider_min, bc_slider_max
    ├─ blockSignals(False)
    │
    ├─ Emit: rangeChanged(log_range[0], log_range[1])
    │   ↓
    │   _on_bc_range_changed()
    │   └─ _bc_apply_minmax()
    │       └─ _sync_modality_display_settings()
    │
    └─ Display updated with log-transformed contrast
```

## Signal Flow with Feedback Prevention

```
┌─────────────────────────────────────────────────────────────┐
│  WITHOUT blockSignals(): FEEDBACK LOOP RISK                 │
│                                                             │
│  _bc_apply_minmax()                                         │
│    ├─ mapping.vmin = new_value                              │
│    └─ _update_bc_controls()  ← Updates UI                   │
│        ├─ spin_box.setValue()  ← Emits valueChanged         │
│        │   ↓                                                │
│        │   _on_vminmax_change()  ← Handler called           │
│        │   └─ _bc_apply_minmax()  ← Could update again      │
│        │       → FEEDBACK LOOP!                             │
│        └─ [other control updates...]                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  WITH blockSignals(): SAFE PROGRAMMATIC UPDATE              │
│                                                             │
│  _update_bc_controls()                                      │
│    ├─ spin_box.blockSignals(True)                           │
│    ├─ spin_box.setValue()  ← No signal emitted              │
│    ├─ spin_box.blockSignals(False)                          │
│    │                                                        │
│    └─ [safe control update without feedback]               │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram: Complete Journey

```
INPUT LAYER
───────────
   User
     └─ Interacts with UI (slider, spin, button)


EVENT LAYER
───────────
   Qt Signal Emitted
     └─ rangeChanged(min, max)
        valueChanged(value)
        clicked()


HANDLER LAYER
─────────────
   Event Handler Invoked
     ├─ _on_bc_range_changed()
     ├─ _on_vminmax_change()
     ├─ _apply_preset()
     └─ [other handlers]


DISPLAY UPDATE LAYER
────────────────────
   DisplayMapping Updated
     ├─ mapping.vmin = new_value
     ├─ mapping.vmax = new_value
     ├─ mapping.lut = new_lut
     └─ mapping.gamma = new_gamma


SYNCHRONIZATION LAYER
──────────────────────
   _sync_modality_display_settings(panel, mapping)
     └─ ModalitySpec.display_settings Updated
        ├─ display_settings.vmin = mapping.vmin
        ├─ display_settings.vmax = mapping.vmax
        ├─ display_settings.lut = mapping.lut
        └─ display_settings.gamma = mapping.gamma


RENDERING LAYER
───────────────
   _apply_display_mapping()
     ├─ Image data transformed
     ├─ Display mapping applied
     └─ Renderer updates image


PERSISTENCE LAYER
─────────────────
   Next panel/image access: _get_display_mapping()
     └─ Checks _panel_modality_map
        └─ Restores display_settings from ModalitySpec
           └─ Display consistency maintained
```

## State Machine: Display Control States

```
                    ┌───────────────────┐
                    │  Initial State    │
                    │  (Auto-range)     │
                    └─────────┬─────────┘
                              │
                              ↓
        ┌─────────────────────────────────────────┐
        │         User Adjusts Controls           │
        │      (Slider, Spin, Preset Button)      │
        └────────────────┬────────────────────────┘
                         │
                         ↓
        ┌─────────────────────────────────────────┐
        │     DisplayMapping Updated              │
        │   (vmin, vmax, lut, gamma, brightness)  │
        └────────────────┬────────────────────────┘
                         │
                         ↓
        ┌─────────────────────────────────────────┐
        │  Modality Sync Called                   │
        │  (ModalitySpec.display_settings updated)│
        └────────────────┬────────────────────────┘
                         │
                         ↓
        ┌─────────────────────────────────────────┐
        │  Display Rendered                       │
        │  (Updated image shown on screen)        │
        └────────────────┬────────────────────────┘
                         │
                    ┌────┴─────┐
                    │           │
                    ↓           ↓
            ┌──────────────┐  ┌────────────────┐
            │ Panel Stays  │  │ Panel Changes  │
            │ Same Modality│  │ (Switch View)  │
            └──────┬───────┘  └────────┬───────┘
                   │                   │
                   │                   ↓
                   │         ┌──────────────────────┐
                   │         │ _get_display_mapping │
                   │         │ Called for new panel │
                   │         └──────────┬───────────┘
                   │                    │
                   │                    ↓
                   │         ┌──────────────────────────┐
                   │         │ Modality Settings Found  │
                   │         │ (From _panel_modality_map)
                   │         └──────────┬───────────────┘
                   │                    │
                   │                    ↓
                   │         ┌──────────────────────────┐
                   │         │ Display Settings Restored│
                   │         │ (vmin, vmax, lut, gamma)│
                   │         └──────────┬───────────────┘
                   │                    │
                   └────────┬───────────┘
                            │
                            ↓
            ┌──────────────────────────────────┐
            │  New Panel Shows Same Display    │
            │  Settings as Previous Modality   │
            │  Panel (Consistency Achieved)    │
            └──────────────────────────────────┘
```

## File Dependencies Graph

```
User Interface Layer
│
├─ ui_docks.py
│  └─ Creates SliderPanelDouble
│     └─ slider_panel_double.py (NEW)
│
├─ events.py (actions)
│  └─ Binds bc_range_slider signals
│
├─ contrast_dialog.py
│  └─ Implements preset transformations
│
Event/Display Control Layer
│
├─ display.py (controls)
│  ├─ Implements _sync_modality_display_settings()
│  ├─ Implements _on_bc_range_changed()
│  ├─ Updates all display methods with sync calls
│  └─ Depends on: ModalitySpec structure
│
Rendering Layer
│
└─ renderer.py
   ├─ Enhanced _get_display_mapping()
   └─ Restores modality display_settings
```

## Backward Compatibility

```
Legacy Code (Old Slider References)
        │
        ├─ hasattr(self, 'bc_min_slider') checks
        ├─ hasattr(self, 'bc_max_slider') checks
        └─ hasattr(self, 'bc_range_slider') checks
                    │
                    ↓
                [Graceful Degradation]
                    │
        ┌───────────┴───────────┐
        │                       │
   If Present            If Not Present
   (New Code)            (Old Code)
        │                       │
        ↓                       ↓
   Use Both              Fall Back to
   Old + New             Legacy Sliders
   Simultaneously
```

## Testing Coverage

```
✅ Test: slider_panel_double.py
   ├─ test_slider_range_updates
   └─ test_slider_clamps_values

✅ Test: contrast_dialog.py
   ├─ test_contrast_dialog_basic
   ├─ test_preset_buttons
   └─ test_signal_emission

✅ Test: All UI tests (75/75 passing)
   ├─ Display controls
   ├─ Event handling
   ├─ Widget initialization
   └─ Signal/slot wiring

⏱️ Pending: Performance/load tests
   ├─ High-frequency slider updates
   ├─ Multi-modality synchronization
   └─ Memory usage with large datasets
```

## Summary

The modality-aware brightness/contrast system provides:

1. **User-Friendly Controls**
   - Dual-slider for intuitive range selection
   - Preset buttons for common transformations
   - Spin boxes for precise numeric input

2. **Persistent Display Settings**
   - Per-modality display preferences
   - Automatic restoration across panels
   - Consistent display for same modality

3. **Robust Synchronization**
   - Three-layer sync architecture
   - Signal feedback prevention
   - Modality-aware renderer initialization

4. **Quality Assurance**
   - All existing tests passing
   - New widget tests comprehensive
   - No regressions introduced
   - Backward compatible
