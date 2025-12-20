# P4 Roadmap: Testing, Robustness & Polish

**Status**: In Progress (7/7 P3 items complete ✅)  
**Start Date**: December 20, 2025  
**Priority**: P4 (Robustness) + P5 (Advanced Features)

---

## Overview

P3 is complete with all high-priority features implemented. P4 focuses on:
- **Testing coverage** for UI components and critical workflows
- **Telemetry & diagnostics** for cache and performance monitoring
- **Code quality** improvements (consistent naming conventions)
- **Advanced features** (performance panel, multi-image workflows)

---

## P4.1: Unit Tests for UI Wiring (1 day)

**Priority**: HIGH  
**Rationale**: Ensure UI actions, menu items, and shortcuts are correctly wired to prevent regressions

### Requirements

1. **Command Palette Action Inventory**
   - Test that all QActions are registered in command palette
   - Verify searchable text matches user expectations
   - Check keyboard shortcuts are properly assigned

2. **View Menu Toggle Wiring**
   - Test dock visibility toggles update menu checkboxes
   - Verify dock close/open events sync with menu state
   - Test "Show All" / "Hide All" dock actions

3. **Shortcut Registration Consistency**
   - Verify all documented shortcuts (F1 dialog) exist
   - Test shortcuts work from all contexts
   - Check for duplicate/conflicting shortcuts

### Implementation

**File**: `tests/test_ui_wiring.py`

```python
def test_command_palette_inventory(app):
    """All major actions should be in command palette."""
    actions = app.command_palette_actions
    assert "Load Image" in actions
    assert "Export View" in actions
    # ... check 20+ critical actions

def test_dock_toggle_wiring(app):
    """Dock visibility should sync with View menu."""
    app.toggle_logs_act.trigger()
    assert app.dock_logs.isVisible() == app.toggle_logs_act.isChecked()

def test_shortcut_consistency(app):
    """All shortcuts in F1 dialog should work."""
    shortcuts = app.keyboard_shortcuts_dialog.get_shortcuts()
    for key, action in shortcuts:
        assert app.findChild(QAction, action).shortcut() == key
```

### Acceptance Criteria

- ✅ 100% of QActions in command palette
- ✅ All View menu toggles bidirectionally wired
- ✅ All F1 dialog shortcuts validated
- ✅ Test coverage: 15+ assertions

### Estimated Effort: **1 day**

---

## P4.2: Export Preflight Test Coverage (4 hours)

**Priority**: MEDIUM  
**Rationale**: Export validation logic is complex and user-facing; needs test coverage

### Requirements

1. **Preflight Validation Logic**
   - Test support panel requires loaded support image
   - Test ROI bounds checks when region="ROI bounds"
   - Test invalid T ranges are rejected
   - Test DPI/format combinations

2. **Confirmation Dialogs**
   - Test overwrite confirmation when file exists
   - Test confirmation can be suppressed via settings
   - Test "Don't ask again" checkbox behavior

3. **File Naming with Metadata**
   - Test metadata tokens in filenames (when enabled)
   - Test multi-frame exports generate _t0001, _t0002, etc.
   - Test layer export generates _base.png, _annotations.png, etc.

### Implementation

**File**: `tests/test_export.py`

```python
def test_export_preflight_support_panel(app):
    """Export with support panel should fail if no support loaded."""
    with pytest.raises(ValidationError):
        app._export_view(panel="support", ...)

def test_export_layer_filenames(app, tmp_path):
    """Layer export should generate separate files."""
    app._export_view(base_path=tmp_path / "test.png", export_as_layers=True)
    assert (tmp_path / "test_base.png").exists()
    assert (tmp_path / "test_annotations.png").exists()
    assert (tmp_path / "test_roi.png").exists()

def test_export_metadata_filename(app, tmp_path):
    """Filename should include metadata tokens when enabled."""
    app._settings.setValue("encodeAnnotationMetaFilename", True)
    path = app._default_export_paths()[0]
    assert "_crop" in path.name or "_roi" in path.name
```

### Acceptance Criteria

- ✅ All preflight checks tested (8+ scenarios)
- ✅ Layer export filenames validated
- ✅ Metadata encoding tested
- ✅ Test coverage: 20+ assertions

### Estimated Effort: **4 hours**

---

## P4.3: Cache Eviction Telemetry (4 hours)

**Priority**: MEDIUM  
**Rationale**: Help users understand cache behavior and prevent performance issues

### Requirements

1. **90% Budget Warnings**
   - Log warning when cache reaches 90% of max budget
   - Include current usage MB and max MB in warning
   - Show which images are consuming most memory

2. **Hit/Miss Ratio Reporting**
   - Track cache hits vs misses per image
   - Log summary every 100 cache operations
   - Report in debug logs (not user-facing by default)

3. **Optional Toast Notification**
   - Show toast when cache is 95%+ full: "Cache nearly full (970/1024 MB)"
   - Include "Clear Cache" quick action button
   - Dismiss after 5 seconds or on click

### Implementation

**Affected Files**:
- `projection_cache.py` - add telemetry tracking
- `pyramid.py` - log cache stats on eviction
- `gui_rendering.py` - optional toast notifications

```python
# projection_cache.py
class ProjectionCache:
    def __init__(self, budget_mb: int):
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def get(self, key):
        if key in self._cache:
            self._hits += 1
            self._log_stats()
            return self._cache[key]
        self._misses += 1
        return None
    
    def _log_stats(self):
        if (self._hits + self._misses) % 100 == 0:
            hit_rate = self._hits / (self._hits + self._misses)
            LOGGER.debug(f"Cache: {hit_rate:.1%} hit rate, {self._evictions} evictions")
    
    def _check_budget(self):
        usage_pct = self._current_mb / self._budget_mb
        if usage_pct >= 0.90 and not self._warned_90:
            LOGGER.warning(f"Cache 90% full: {self._current_mb}/{self._budget_mb} MB")
            self._warned_90 = True
        if usage_pct >= 0.95:
            self._emit_toast_warning()
```

### Acceptance Criteria

- ✅ Warning logged at 90% budget
- ✅ Hit/miss ratios in debug logs
- ✅ Toast notification at 95% (optional, settings-controlled)
- ✅ Toast includes "Clear Cache" button

### Estimated Effort: **4 hours**

---

## P4.4: Consistent Widget objectName (1 day)

**Priority**: LOW  
**Rationale**: Improves debuggability, command palette indexing, and automated testing

### Requirements

1. **Naming Convention**
   - Format: `{module}_{type}_{function}`
   - Example: `gui_export_action_export_view`
   - Example: `gui_ui_setup_dock_logs`
   - Example: `threshold_panel_spinbox_smooth_sigma`

2. **Apply to All Widgets**
   - All QActions (100+ actions)
   - All QDockWidgets (12 docks)
   - All major input widgets (spinboxes, combos, checkboxes)
   - All panels and custom widgets

3. **Update Command Palette Indexing**
   - Use objectName as fallback for action text
   - Improve search matching (fuzzy search on objectName)
   - Show objectName in command palette results (debug mode)

### Implementation

**Affected Files**: All `gui_*.py`, `*_panel.py`, `ui_*.py` modules

```python
# Example: gui_ui_setup.py
def _setup_actions(self):
    self.load_image_act = QtWidgets.QAction("Load Image", self)
    self.load_image_act.setObjectName("gui_ui_setup_action_load_image")
    self.load_image_act.setShortcut("Ctrl+O")
    
    self.export_view_act = QtWidgets.QAction("Export View", self)
    self.export_view_act.setObjectName("gui_export_action_export_view")
    
def _setup_docks(self):
    self.dock_logs = QtWidgets.QDockWidget("Logs", self)
    self.dock_logs.setObjectName("gui_ui_setup_dock_logs")
    
    self.dock_threshold = QtWidgets.QDockWidget("Threshold", self)
    self.dock_threshold.setObjectName("threshold_panel_dock_threshold")
```

### Acceptance Criteria

- ✅ All QActions have objectName set (100+ widgets)
- ✅ All QDockWidgets have objectName set (12 docks)
- ✅ Convention documented in code comments
- ✅ Command palette uses objectName for better search

### Estimated Effort: **1 day**

---

## P5.1: Consolidated Performance Panel (2 days)

**Priority**: MEDIUM  
**Rationale**: Power users need visibility into cache, jobs, and prefetch state

### Requirements

1. **Cache Usage Display**
   - Current MB / Max MB with progress bar
   - Color-coded: green (<80%), yellow (80-95%), red (>95%)
   - List top 5 images by memory usage
   - "Clear Cache" button

2. **Active Jobs Display**
   - Table: Job Name, Progress %, Elapsed Time, Status
   - Color-coded status: Running (blue), Queued (gray), Error (red)
   - "Cancel" button per job
   - "Cancel All" button

3. **Prefetch Queue Display**
   - Queue depth: N frames waiting
   - Current prefetch: Image name, T range
   - Inflight blocks: N/M
   - "Pause Prefetch" toggle

4. **Buffer Status**
   - Ring buffer: Filled / Capacity
   - Playback underruns count
   - "Reset Underruns" button

### Implementation

**File**: `src/phage_annotator/performance_panel.py`

```python
class PerformancePanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        
        # Cache section
        cache_group = QtWidgets.QGroupBox("Cache")
        self.cache_progress = QtWidgets.QProgressBar()
        self.cache_label = QtWidgets.QLabel("0 / 1024 MB")
        self.cache_clear_btn = QtWidgets.QPushButton("Clear Cache")
        
        # Jobs section
        jobs_group = QtWidgets.QGroupBox("Active Jobs")
        self.jobs_table = QtWidgets.QTableWidget()
        self.jobs_cancel_all_btn = QtWidgets.QPushButton("Cancel All")
        
        # Prefetch section
        prefetch_group = QtWidgets.QGroupBox("Prefetch Queue")
        self.prefetch_label = QtWidgets.QLabel("Queue: 0 frames")
        self.prefetch_pause_chk = QtWidgets.QCheckBox("Pause Prefetch")
        
        # Buffer section
        buffer_group = QtWidgets.QGroupBox("Playback Buffer")
        self.buffer_label = QtWidgets.QLabel("64 / 128 frames")
        self.underruns_label = QtWidgets.QLabel("Underruns: 0")
```

### Acceptance Criteria

- ✅ Real-time cache usage display
- ✅ Active jobs table with cancel actions
- ✅ Prefetch queue monitoring
- ✅ Buffer status with underrun counter
- ✅ All quick actions functional

### Estimated Effort: **2 days**

---

## P5.2: Multi-Image ROI Management (2 days)

**Priority**: LOW  
**Rationale**: Batch processing workflows need ROI templates

### Requirements

1. **Copy ROI to All Images**
   - Menu action: "ROI → Copy to All Images"
   - Applies current ROI (shape + rect) to all images in session
   - Confirmation dialog: "Apply ROI to N images?"
   - Undo support (batch operation)

2. **Copy ROI to Tagged Images**
   - Menu action: "ROI → Copy to Tagged Images..."
   - Dialog: Select tags (checkboxes)
   - Apply ROI only to images with selected tags
   - Useful for multi-condition experiments

3. **ROI Templates**
   - Save current ROI as template: "ROI → Save as Template..."
   - Dialog: Enter template name
   - Load template: "ROI → Load Template..." (dropdown)
   - Templates stored in session state
   - Persist in project files

4. **Bulk Measurement Presets**
   - Define measurement preset: ROI + threshold + particle settings
   - Apply preset to image list
   - Export results to CSV
   - Useful for high-throughput analysis

### Implementation

**Affected Files**:
- `session_controller.py` - batch ROI operations
- `gui_roi_crop.py` - ROI menu actions
- `session_state.py` - ROI template storage

```python
# session_controller.py
def copy_roi_to_all_images(self, roi_shape: str, roi_rect: tuple) -> int:
    """Apply ROI to all images in session."""
    count = 0
    for img in self.session_state.images:
        self._set_roi_for_image(img.id, roi_shape, roi_rect)
        count += 1
    return count

def save_roi_template(self, name: str, roi_shape: str, roi_rect: tuple):
    """Save ROI as reusable template."""
    if not hasattr(self.session_state, 'roi_templates'):
        self.session_state.roi_templates = {}
    self.session_state.roi_templates[name] = {
        'shape': roi_shape,
        'rect': roi_rect,
    }

def load_roi_template(self, name: str) -> tuple:
    """Load ROI template by name."""
    template = self.session_state.roi_templates.get(name)
    if template:
        return template['shape'], tuple(template['rect'])
    return None, None
```

### Acceptance Criteria

- ✅ Copy ROI to all images (with confirmation)
- ✅ Copy ROI to tagged subset
- ✅ Save/load ROI templates
- ✅ Templates persist in project files
- ✅ Undo support for batch operations

### Estimated Effort: **2 days**

---

## Priority Summary

### Phase 1: Testing & Quality (2 days)
- **P4.1**: UI wiring tests (1 day) ⚠️ **HIGH**
- **P4.2**: Export tests (4 hours)

### Phase 2: Diagnostics (8 hours)
- **P4.3**: Cache telemetry (4 hours)
- **P4.4**: Widget naming (1 day - LOW priority, can defer)

### Phase 3: Advanced Features (4 days)
- **P5.1**: Performance panel (2 days)
- **P5.2**: Multi-image ROI (2 days)

**Total Estimated Effort**: ~6-7 days

---

## Success Metrics

- **Test Coverage**: 90%+ for critical UI paths
- **Cache Hit Rate**: 85%+ during typical workflows
- **Widget Naming**: 100% of QActions have objectName
- **User Feedback**: "Performance panel helps diagnose slowness"
- **Batch Workflows**: ROI templates save 5+ minutes per experiment

---

## Risk Mitigation

1. **Testing Complexity**
   - Risk: Qt UI testing can be flaky
   - Mitigation: Use `pytest-qt` fixtures, mock heavy operations

2. **Cache Telemetry Overhead**
   - Risk: Logging might slow down cache operations
   - Mitigation: Only log every 100 operations, use debug level

3. **Widget Naming Tedium**
   - Risk: Manually naming 100+ widgets is error-prone
   - Mitigation: Script to auto-generate names, review in batches

4. **Performance Panel Refresh Rate**
   - Risk: Updating UI too frequently causes lag
   - Mitigation: Throttle updates to 2 Hz, use QTimer

---

## Next Steps After P4

- **P5+**: Consider additional improvements based on user feedback
- **Documentation**: Update user manual with new features
- **Release**: Tag v2.0.0 with complete P0-P4 implementation
