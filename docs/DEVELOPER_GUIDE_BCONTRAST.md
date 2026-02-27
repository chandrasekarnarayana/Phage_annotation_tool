# Developer Guide: Modality-Aware Brightness/Contrast System

## Architecture Overview

The B&C system implements a **three-layer synchronization architecture**:

```
┌─────────────────────────────────────┐
│  Layer 1: UI Controls              │
│  (SliderPanelDouble, spinboxes)    │
└──────────────┬──────────────────────┘
               │ Qt Signals
               ↓
┌─────────────────────────────────────┐
│  Layer 2: DisplayMapping            │
│  (Per-image, per-panel state)       │
│  - min_val, max_val                 │
│  - gamma, mode, lut, invert         │
└──────────────┬──────────────────────┘
               │ _sync_modality_display_settings()
               ↓
┌─────────────────────────────────────┐
│  Layer 3: ModalityDisplaySettings   │
│  (Per-modality persistent state)    │
│  - vmin, vmax, lut, gamma, etc      │
└─────────────────────────────────────┘
```

## Key Components

### 1. SliderPanelDouble Widget
**File**: `src/phage_annotator/ui_qt/widgets/slider_panel_double.py`

A custom Qt widget providing dual-handle slider functionality:

```python
class SliderPanelDouble(QtWidgets.QWidget):
    rangeChanged = QtCore.pyqtSignal(int, int)  # min, max
    
    def setRange(self, min_val, max_val) -> None:
        """Set slider range bounds."""
        
    def setValues(self, min_val, max_val) -> None:
        """Update slider handle positions."""
        
    def setStep(self, step) -> None:
        """Set quantization step for values."""
```

**Key Methods**:
- `_handle_hit()`: Check mouse hit detection
- `mousePressEvent()`: Select active handle
- `mouseMoveEvent()`: Drag handle
- `keyPressEvent()`: Keyboard fine-tuning
- `paintEvent()`: Render slider and histogram

**Features**:
- Visual feedback (handle cursors, groove highlighting)
- Signal emission on value changes
- Step-based quantization
- Min/max clamping

### 2. DisplayMapping
**File**: `src/phage_annotator/data/display_mapping.py`

Data structure holding per-image, per-panel display state:

```python
@dataclass
class DisplayMapping:
    """Brightness/contrast mapping state."""
    min_val: float
    max_val: float
    gamma: float = 1.0
    mode: str = "linear"
    lut: int = 0
    invert: bool = False
    sync_vmin: bool = False
    sync_vmax: bool = False
    sync_contrast: bool = False
```

**Responsibilities**:
- Store min/max display window
- Track gamma correction
- Manage LUT selection
- Track sync state flags
- Per-panel and per-image overrides

### 3. ModalityDisplaySettings
**File**: `src/phage_annotator/session/modality.py`

```python
class ModalitySpec:
    """Specification for a modality."""
    name: str
    image_id: int
    projection_type: str
    display_settings: ModalityDisplaySettings
    
class ModalityDisplaySettings:
    """Persistent display settings for a modality."""
    vmin: int
    vmax: int
    lut: Optional[str]
    gamma: float
    projection_axis: str
```

**Responsibilities**:
- Store per-modality display preferences
- Persist across sessions
- Enable consistent display across multiple panels

### 4. DisplayControlsMixin (Display Controller)
**File**: `src/phage_annotator/ui_qt/controls/display.py`

Main handler for B&C control logic:

```python
class DisplayControlsMixin:
    """Mixin for display controls and B&C logic."""
    
    def _sync_modality_display_settings(
        self, panel: str, mapping: DisplayMapping
    ) -> None:
        """Sync DisplayMapping → ModalityDisplaySettings."""
        # Called after EVERY display modification
        
    def _on_bc_range_changed(self, min_val: int, max_val: int) -> None:
        """Handler for dual-slider changes."""
        
    def _bc_apply_minmax(self, min_val: int, max_val: int) -> None:
        """Apply min/max to DisplayMapping and sync."""
        
    def _update_bc_controls(self) -> None:
        """Update all UI controls from DisplayMapping."""
```

**Key Responsibilities**:
- Implement _sync_modality_display_settings() calls throughout
- Prevent signal feedback loops with blockSignals()
- Update all control widgets programmatically
- Propagate changes to renderer

### 5. Renderer Enhancement
**File**: `src/phage_annotator/ui_qt/renderers/renderer.py`

```python
def _get_display_mapping(self, image, panel: str) -> DisplayMapping:
    """Get or create display mapping with modality restoration."""
    mapping = self._ensure_display_mapping(image, panel)
    
    # Restore from _panel_modality_map if available
    if hasattr(self, '_panel_modality_map'):
        modality_spec = self._panel_modality_map.get(panel)
        if modality_spec and modality_spec.display_settings.vmax > vmin:
            mapping.min_val = modality_spec.display_settings.vmin
            mapping.max_val = modality_spec.display_settings.vmax
            # ... restore gamma, lut ...
    
    return mapping
```

**Key Responsibilities**:
- Auto-restore modality settings on first access
- Graceful fallback to auto-range
- Enable seamless panel switching

## Data Flow

### User Adjusts Slider

```python
# 1. User drags slider handle
# 2. Qt emits rangeChanged signal
bc_range_slider.rangeChanged.emit(min_val, max_val)

# 3. Event handler invoked (ALWAYS connected)
@Slot(int, int)
def _on_bc_range_changed(self, min_val: int, max_val: int) -> None:
    self._bc_apply_minmax(min_val, max_val)

# 4. Apply to display mapping
def _bc_apply_minmax(self, min_val: int, max_val: int) -> None:
    mapping = self.display_mapping("frame")
    mapping.min_val = min_val
    mapping.max_val = max_val
    
    # ✓ CRITICAL: Sync to modality settings
    self._sync_modality_display_settings("frame", mapping)
    
    self._apply_display_mapping()

# 5. Sync implementation
def _sync_modality_display_settings(self, panel: str, mapping: DisplayMapping) -> None:
    if not hasattr(self, '_panel_modality_map'):
        return
    
    modality_spec = self._panel_modality_map.get(panel)
    if modality_spec is None:
        return
    
    # Update modality settings from display mapping
    modality_spec.display_settings.vmin = mapping.min_val
    modality_spec.display_settings.vmax = mapping.max_val
    modality_spec.display_settings.lut = ... # sync lut, gamma, etc.

# 6. Render applied
def _apply_display_mapping(self) -> None:
    # View updated on screen with new B&C
```

## Integration Checklist

When adding **new display control methods** that modify B&C:

✓ **Step 1**: Create/modify method  
```python
def _my_new_control():
    mapping = self.display_mapping(panel)
    # ... modify mapping ...
    
    # ✓ REQUIRED: Sync to modality
    self._sync_modality_display_settings(panel, mapping)
    self._apply_display_mapping()
```

✓ **Step 2**: Block signals during programmatic updates  
```python
widget.blockSignals(True)
widget.setValue(new_value)  # No signal emitted
widget.blockSignals(False)
```

✓ **Step 3**: Test with modalities
```python
# Switch modalities
primary_combo.setCurrentIndex(1)
# Verify settings restored
assert mapping.min_val == modality.display_settings.vmin
```

✓ **Step 4**: Add to _update_bc_controls()  
```python
def _update_bc_controls(self) -> None:
    mapping = self.display_mapping("frame")
    
    # Block signals
    self.bc_min_spin.blockSignals(True)
    self.bc_range_slider.blockSignals(True)
    
    # Update values
    self.bc_min_spin.setValue(mapping.min_val)
    self.bc_range_slider.setValues(mapping.min_val, mapping.max_val)
    
    # Unblock signals
    self.bc_min_spin.blockSignals(False)
    self.bc_range_slider.blockSignals(False)
```

## Testing Strategy

### Unit Tests
```python
# Test DisplayMapping consistency
def test_display_mapping_vmin_vmax():
    mapping = DisplayMapping(50, 200)
    assert mapping.min_val <= mapping.max_val

# Test slider widget
@pytest.mark.skip(reason="Requires Qt")
def test_slider_range_updates():
    slider = SliderPanelDouble()
    slider.setValues(25, 75)
    assert slider._min_value == 25
```

### Integration Tests
```python
# Test sync chain: UI → Mapping → Modality
def test_sync_modality_updates_all_properties():
    mapping = DisplayMapping(50, 200)
    modality = Mock()
    
    # Simulate sync
    modality.display_settings.vmin = mapping.min_val
    
    # Verify
    assert modality.display_settings.vmin == 50
```

### Regression Tests
Located in: `tests/unit/ui_qt/test_bcontrast_regression.py`

```python
def test_panel_switch_restores_modality_settings():
    """Verify display settings restored when switching panels."""
    # Create modality with settings
    modality_a = Mock()
    modality_a.display_settings = Mock(vmin=100, vmax=200)
    
    # Switch panel
    modality = panel_modality_map.get("frame")
    
    # Verify restored
    assert modality.display_settings.vmin == 100
```

## Common Pitfalls

### ❌ Mistake: Forgetting _sync_modality_display_settings()

```python
# WRONG: Modality settings won't update
def _on_contrast_change():
    mapping = self.display_mapping("frame")
    mapping.gamma = user_value
    self._apply_display_mapping()  # Missing sync!
```

**Fix**: Always add sync call
```python
# RIGHT: Modality stays in sync
def _on_contrast_change():
    mapping = self.display_mapping("frame")
    mapping.gamma = user_value
    self._sync_modality_display_settings("frame", mapping)  # ✓
    self._apply_display_mapping()
```

### ❌ Mistake: Signal Feedback Loops

```python
# WRONG: Infinite loop
def _on_spin_changed(value):
    slider.setValue(value)  # Triggers slider changed
    # → slider handler calls _on_spin_changed()
    # → infinite loop!
```

**Fix**: Use blockSignals()
```python
# RIGHT: No feedback
def _on_spin_changed(value):
    slider.blockSignals(True)
    slider.setValue(value)  # No signal from slider
    slider.blockSignals(False)
```

### ❌ Mistake: Wrong Attribute Names

```python
# WRONG: DisplayMapping uses min_val, not vmin
mapping.vmin = 50  # AttributeError!

# RIGHT:
mapping.min_val = 50  # ✓
```

### ❌ Mistake: Incomplete Panel Updates

```python
# WRONG: Only updates slider, not spins
def _update_bc_controls():
    slider.setValue(new_value)  # Missing spin boxes!

# RIGHT: Update all controls
def _update_bc_controls():
    spin_min.blockSignals(True)
    spin_min.setValue(mapping.min_val)
    spin_min.blockSignals(False)
    
    slider.blockSignals(True)
    slider.setValues(mapping.min_val, mapping.max_val)
    slider.blockSignals(False)
```

## Performance Considerations

### LUT Pre-computation
- Pre-compute LUT when min/max changes (~1ms)
- Reuse LUT for all pixel lookups (~200ms for 2K×2K×100)
- Cache LUTs per modality to avoid recomputation

### Signal Blocking
- blockSignals() prevents redundant updates
- Typical update: set 3-4 controls with blocking
- Cost: minimal (Qt-level optimization)

### Memory Usage
- One DisplayMapping per (image, panel) pair
- One ModalityDisplaySettings per modality
- Typical overhead: <100KB per 10 modalities

## Extending the System

### Adding a New Display Control

1. **Add UI element** in `ui_docks.py`:
```python
self.my_control = QtWidgets.QSlider()
self.my_control.valueChanged.connect(self._on_my_control)
```

2. **Add handler** in `display.py`:
```python
def _on_my_control(self, value):
    mapping = self.display_mapping("frame")
    mapping.my_property = value
    self._sync_modality_display_settings("frame", mapping)  # ✓
    self._apply_display_mapping()
```

3. **Add to _update_bc_controls()**:
```python
def _update_bc_controls(self):
    # ... existing code ...
    self.my_control.blockSignals(True)
    self.my_control.setValue(mapping.my_property)
    self.my_control.blockSignals(False)
```

4. **Test**:
```python
def test_my_control_syncs_to_modality():
    controller._on_my_control(new_value)
    assert modality.display_settings.my_property == new_value
```

### Adding a New Preset

1. **Add computation** in `contrast_dialog.py`:
```python
def _compute_preset_range(self, preset, low, high):
    if preset == "my_preset":
        return (special_low, special_high)
```

2. **Add button** in dialog UI:
```python
preset_btn = QtWidgets.QPushButton("My Preset")
preset_btn.clicked.connect(lambda: self._apply_preset("my_preset"))
```

3. **Test**:
```python
def test_my_preset_applies_correctly():
    dialog._apply_preset("my_preset")
    assert slider.value() == expected_value
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 2026 | Initial release with SliderPanelDouble, modality sync |
| TBD | TBD | RGB per-channel controls (planned) |
| TBD | TBD | Custom preset management (planned) |

---

**Questions?** Check the code comments or contact the dev team!
