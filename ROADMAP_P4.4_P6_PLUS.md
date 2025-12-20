# Implementation Roadmap: P4.4 Continuation & P6+ Planning

## Current Status (Phase P3-P5 Complete)
- ✅ **Total Tests Passing**: 108/110 (98.2%)
- ✅ **P3**: 7/7 items complete
- ✅ **P4**: 3/4 items complete (P4.4 partial)
- ✅ **P5**: 2/2 items complete
- 📋 **Next**: Complete P4.4, then move to P6

---

## P4.4: Widget ObjectName Completion Roadmap

### Current Status
- ✅ **gui_export.py**: 16 widgets completed (export dialog)
- ⏳ **Remaining**: ~10-15 files with ~200+ widgets

### Files to Process (Priority Order)

#### HIGH PRIORITY (Core UI - Used in Tests)

| File | Widget Count | Widget Types | Status | Effort |
|------|--------------|--------------|--------|--------|
| `gui_controls.py` | ~25 | ComboBox, SpinBox, CheckBox, Button | ⏳ TODO | 30min |
| `gui_controls_display.py` | ~20 | ComboBox, CheckBox, SpinBox | ⏳ TODO | 25min |
| `gui_controls_roi.py` | ~18 | ComboBox, CheckBox, Button | ⏳ TODO | 20min |
| `gui_roi_crop.py` | ~15 | CheckBox, Button, LineEdit | ⏳ TODO | 20min |
| `gui_actions.py` | ~12 | Button, CheckBox | ⏳ TODO | 15min |

#### MEDIUM PRIORITY (Analysis & Tools)

| File | Widget Count | Widget Types | Status | Effort |
|------|--------------|--------------|--------|--------|
| `gui_controls_smlm.py` | ~16 | ComboBox, SpinBox, CheckBox | ⏳ TODO | 20min |
| `gui_controls_density.py` | ~14 | SpinBox, CheckBox, Button | ⏳ TODO | 18min |
| `gui_controls_threshold.py` | ~12 | SpinBox, CheckBox, Button | ⏳ TODO | 15min |
| `gui_controls_preferences.py` | ~20 | CheckBox, SpinBox, LineEdit | ⏳ TODO | 25min |
| `gui_controls_recorder.py` | ~8 | Button, CheckBox | ⏳ TODO | 10min |

#### LOWER PRIORITY (Secondary Features)

| File | Widget Count | Widget Types | Status | Effort |
|------|--------------|--------------|--------|--------|
| `gui_ui_setup.py` | ~10 | Button, CheckBox | ⏳ TODO | 12min |
| `gui_playback.py` | ~8 | Slider, Button, SpinBox | ⏳ TODO | 12min |
| `gui_controls_results.py` | ~6 | Button, CheckBox | ⏳ TODO | 8min |
| `gui_debug.py` | ~5 | Button, Label | ⏳ TODO | 5min |

### Naming Convention

```python
# Pattern: {module}_{widget_type}_{purpose}

# Module: Short name from filename
gui_controls.py → controls
gui_export.py → export_dialog
gui_roi_crop.py → roi_crop
gui_controls_display.py → controls_display

# Widget Types: combo, spinbox, checkbox, button, label, lineedit, slider
QComboBox → combo
QSpinBox → spinbox
QCheckBox → checkbox
QPushButton → button
QLabel → label
QLineEdit → lineedit
QSlider → slider

# Purpose: Descriptive of function
opacity_combo → describes it controls opacity
threshold_spinbox → describes it controls threshold
```

### Batch Processing Script

```bash
#!/bin/bash
# Process P4.4 files systematically

cd src/phage_annotator

# Helper: add objectName to all QComboBox, QSpinBox, etc. in file
# Requires manual review but pattern is consistent

files=(
  "gui_controls.py"
  "gui_controls_display.py"
  "gui_controls_roi.py"
  "gui_roi_crop.py"
  "gui_actions.py"
  "gui_controls_smlm.py"
  "gui_controls_density.py"
  "gui_controls_threshold.py"
  "gui_controls_preferences.py"
)

for file in "${files[@]}"; do
  echo "Processing $file..."
  # Manual review needed for each file
done
```

### Example: gui_controls.py Template

```python
# BEFORE (no objectName)
class ControlsPanel:
    def _setup_ui(self):
        self.opacity_combo = QComboBox()
        self.threshold_spinbox = QSpinBox()
        self.apply_button = QPushButton("Apply")

# AFTER (with objectName)
class ControlsPanel:
    def _setup_ui(self):
        self.opacity_combo = QComboBox()
        self.opacity_combo.setObjectName("controls_combo_opacity")
        
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setObjectName("controls_spinbox_threshold")
        
        self.apply_button = QPushButton("Apply")
        self.apply_button.setObjectName("controls_button_apply")
```

### Testing P4.4 Completion

```python
# Test file after P4.4 completion
def test_all_widgets_have_objectname():
    """Verify all critical widgets have objectName set"""
    
    window = create_main_window()
    
    # Check export dialog
    dialog = window.export_dialog
    assert dialog.findChild(QComboBox, "export_dialog_combo_panel") is not None
    
    # Check controls
    controls_panel = window.controls_panel
    assert controls_panel.findChild(QComboBox, "controls_combo_opacity") is not None
    assert controls_panel.findChild(QSpinBox, "controls_spinbox_threshold") is not None
    
    # Check ROI panel
    roi_panel = window.roi_panel
    assert roi_panel.findChild(QCheckBox, "roi_crop_checkbox_show") is not None
```

### Effort Estimate & Timeline

- **Total Widget Count**: ~200+ widgets
- **Estimated Time**: 3-4 hours (manual review + testing)
- **Timeline**: 
  - Session 1: HIGH PRIORITY files (2-3 hours)
  - Session 2: MEDIUM PRIORITY files (1-2 hours)
  - Session 3: LOWER PRIORITY + Testing (1 hour)

---

## P6+ Planning

### Phase P6: Robustness & Error Handling

#### P6.1: Project Load Error Handling
**Scope**: Handle missing image paths gracefully
**Effort**: 4-6 hours
**Tests**: 8-10 new tests

```python
# Design: When project loads with missing images:
1. Detect missing file (open() raises FileNotFoundError)
2. Show warning dialog with list of missing images
3. Offer options:
   - Locate files (file picker per image)
   - Skip image (load partial project)
   - Abort load (don't load anything)
4. Save mapping for future reference
```

**Files to Modify**:
- `project_io.py` - Add error recovery
- `session_controller_project.py` - Propagate errors to UI
- `gui_actions.py` - Show missing file dialog
- `tests/test_project_io.py` - Add error cases

#### P6.2: Error Reporting Enhancements
**Scope**: Clickable stack traces + severity filtering
**Effort**: 6-8 hours
**Tests**: 12-15 new tests

```python
# Design: Enhance Logs dock with:
1. Severity level filter (ERROR/WARNING/INFO/DEBUG/TRACE)
2. Clickable stack traces (navigate to source line)
3. Copy log entry (for bug reports)
4. Search/filter logs by module/timestamp
5. Auto-scroll new entries
```

**Files to Create/Modify**:
- `gui_logs_dock.py` (new) - Enhanced log display
- `logger.py` - Attach stack trace info
- `gui_events.py` - Integrate with click handlers

#### P6.3: Cache Eviction Telemetry
**Scope**: Monitor cache pressure, warn at threshold
**Effort**: 3-4 hours
**Tests**: 6-8 new tests

```python
# Design: Cache monitoring:
1. Track hit_rate, memory_usage trends
2. Warn when cache approaches 90% budget
3. Show eviction history (what was removed, when, why)
4. Provide manual cache clear + optimization suggestions
5. Log performance metrics to file for analysis
```

**Files to Modify**:
- `projection_cache.py` - Add pressure metrics
- `gui_panel_performance.py` - Show warnings
- `logger.py` - Log cache events

#### P6.4: Widget Naming Completion (P4.4 Extension)
**Scope**: Complete remaining ~200 widgets
**Effort**: 3-4 hours
**Tests**: Regression suite (5 tests)

See P4.4 roadmap above for details.

### Phase P7: Workflow Optimization

#### P7.1: Settings Persistence Completion
**Scope**: Persist remaining transient settings
**Effort**: 3-4 hours
**Tests**: 8-10 new tests

```python
# Remaining settings to persist:
- Colormap selection (current, custom maps)
- Annotation scope (single/multi-image)
- ROI tool mode (free/rectangle/polygon)
- Tool options (brush size, opacity)
- View zoom level, pan position
- Dock layout, window geometry
- Recently used export presets
```

#### P7.2: Multi-format Export Presets
**Scope**: Save/load export dialog state
**Effort**: 4-5 hours
**Tests**: 10-12 new tests

```python
# Design:
1. Presets button in export dialog
2. Save current state → name + description
3. Load preset → restore all settings
4. Built-in presets:
   - "Publication" (PNG, 300DPI, full view, all overlays)
   - "Web" (PNG, 96DPI, crop, minimal overlays)
   - "Archive" (TIFF, 600DPI, full view, all layers)
```

#### P7.3: Batch Measurement Presets
**Scope**: Save/load ROI measurement sets
**Effort**: 5-6 hours
**Tests**: 12-15 new tests

```python
# Design:
1. Define measurement preset (area, perimeter, intensity, circularity)
2. Save as named preset (e.g., "Cell Analysis", "Nucleus")
3. Apply preset → auto-compute all metrics
4. Export measurements → CSV/JSON with preset name
```

### Phase P8: Testing & CI

#### P8.1: Command Palette Tests
**Scope**: Comprehensive action registry coverage
**Effort**: 3-4 hours
**Tests**: 15-20 new tests

```python
# Test every:
- QAction registered in menu
- QAction trigger calls correct handler
- Command palette can find action by name
- Keyboard shortcuts work
- Context menus wired correctly
```

#### P8.2: Performance Baseline Tests
**Scope**: Export performance regression tracking
**Effort**: 4-5 hours
**Tests**: 8-10 benchmarks

```python
# Benchmark scenarios:
- Export small image (512x512)
- Export large image (4096x4096)
- Export with all layers
- Export with many annotations
- Export to PNG vs TIFF
- Target: <2 sec for typical case
```

#### P8.3: CI/CD Enhancements
**Scope**: Code quality automation
**Effort**: 2-3 hours
**Tests**: Integration tests

```bash
# CI Pipeline additions:
- pylint (code style)
- flake8 (PEP8 compliance)
- black (formatting)
- mypy (type hints)
- docstring coverage (sphinx)
- Security scan (bandit)
```

---

## Dependency Graph

```
P4.4 Complete ─────┐
                   ├─→ P6.1 (Error Handling)
P6.1 Complete ─────┤
                   ├─→ P6.2 (Error Reporting)
P6.2 Complete ─────┤
                   ├─→ P6.3 (Cache Telemetry)
P6.3 Complete ─────┤
                   ├─→ P7 (Workflow)
P4.4 + P6 ────────→ P8 (Testing)
```

---

## Success Criteria

### P4.4 Completion
- [ ] All ~200+ critical widgets have objectName
- [ ] objectName naming convention documented
- [ ] 5+ widget-finding tests pass
- [ ] Zero regressions in existing tests
- [ ] Code review approved

### P6 Phase
- [ ] Error handling for 90%+ of edge cases
- [ ] Logs dock has filtering + stack traces
- [ ] Cache pressure warnings working
- [ ] User experience improved (confirmed via testing)

### P7 Phase
- [ ] All transient settings persisted
- [ ] 3+ export presets available
- [ ] Measurement presets save/load working
- [ ] Workflow time reduced by 20%+ (subjective)

### P8 Phase
- [ ] 95%+ code coverage for critical paths
- [ ] All CI checks passing
- [ ] Performance regression <5% on typical export
- [ ] Zero security issues from bandit scan

---

## Resource Estimates

| Phase | Files | Tests | Effort | Timeline |
|-------|-------|-------|--------|----------|
| P4.4 | 10-15 | 5 | 3-4h | Session 1-3 |
| P6 | 6-8 | 26-33 | 13-18h | Week 1-2 |
| P7 | 5-7 | 30-37 | 12-15h | Week 2-3 |
| P8 | 3-5 | 50-60 | 8-10h | Week 3-4 |
| **TOTAL** | **24-35** | **111-135** | **36-47h** | **1 month** |

---

## Key Milestones

1. ✅ **P3-P5 Complete**: 108 tests passing (DONE)
2. ⏳ **P4.4 Complete**: All widgets named (+5 tests)
3. ⏳ **P6 Phase**: Robustness & error handling (+26-33 tests)
4. ⏳ **P7 Phase**: Workflow optimization (+30-37 tests)
5. ⏳ **P8 Phase**: Testing & CI (+50-60 tests)

**Final State**: 220-250 tests, comprehensive coverage, production-ready

---

## Next Session Action Items

1. **Immediate**: Complete P4.4 for HIGH PRIORITY files (gui_controls.py, gui_controls_display.py, gui_controls_roi.py)
2. **Then**: Start P6.1 (project load error handling)
3. **Document**: Update feature_control_matrix.md with P6+ detailed roadmap

---

*Target Completion*: 4 weeks at 9-12 hours/week  
*Current Velocity*: 108 tests in 3 sessions = ~36 tests/session  
*Est. Final Tests*: 220-250 (up from 73 original)  
