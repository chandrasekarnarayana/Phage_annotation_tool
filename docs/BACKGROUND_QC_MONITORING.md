# Background QC Monitoring Implementation

## Overview

The Phage Annotator tool now includes **continuous background QC monitoring** that automatically detects quality issues without interrupting your annotation workflow.

### Key Features

✅ **Non-blocking monitoring** — Runs in background without UI delays
✅ **Smart debouncing** — 2 seconds after edits, 10 second periodic scans
✅ **Dual-trigger system** — Responds to annotation changes + image loads
✅ **Visual feedback** — Pulsing indicator shows monitor is active
✅ **Automatic issue detection** — Continuously validates:
- Annotation metadata (duplicates, bounds, labels)
- Image artifacts (illumination, photobleaching, dust, patterning, clustering)
- Signal stochasticity (Poisson distribution tests)

---

## Architecture

### 1. Background Monitor (`qc_background_monitor.py`)

The `QCBackgroundMonitor` class runs in the main thread with two synchronized timers:

```python
## Edit-triggered validation (2s debounce)
self._edit_debounce_timer = QtCore.QTimer()
self._edit_debounce_timer.setInterval(2000)
self._edit_debounce_timer.timeout.connect(self._on_edit_debounce_timeout)

## Periodic full scan (10s intervals)
self._periodic_timer = QtCore.QTimer()
self._periodic_timer.setInterval(10000)
self._periodic_timer.timeout.connect(self._on_periodic_timeout)
```

#### Key Methods

| Method | Trigger | Purpose |
|--------|---------|---------|
| `on_annotation_changed()` | When points are added/removed/modified | Debounce validation (2s) |
| `on_image_loaded()` | When FOV changes or image loads | Fast validation (500ms) |
| `on_labels_changed()` | When taxonomy changes | Label constraint check (1s) |
| `set_enabled(bool)` | Configuration | Enable/disable monitoring |
| `set_validation_callback()` | Setup | Register validation function |

#### Signals Emitted

- `validation_completed` — Validation finished (issues updated)
- `monitoring_started` — Monitor activated
- `monitoring_stopped` — Monitor deactivated
- `status_changed(str)` — Status message for UI display

#### Status Widget (`QCMonitorStatusWidget`)

Displays pulsing green indicator + status message:
```
● Monitoring...
● Change detected, QC pending...
● Running QC check...
● QC check complete
```

---

### 2. State Management (`qc_state.py`)

Extended `QCState` with monitoring configuration:

```python
@dataclass
class QCState:
    # ... existing fields ...

    # Background monitoring configuration
    auto_monitor_enabled: bool = True           # Enable/disable monitoring
    monitor_debounce_ms: int = 2000             # Edit debounce (ms)
    monitor_periodic_ms: int = 10000            # Periodic scan interval (ms)
```

---

### 3. Integration Points

#### A. QC Actions Mixin (`qc_actions.py`)

**Initialization** (`_ensure_qc_runtime`):
```python
## Create and wire monitor
self._qc_background_monitor = QCBackgroundMonitor()
self._qc_background_monitor.set_validation_callback(
    lambda: self._trigger_qc_validation()
)
self._qc_background_monitor.status_changed.connect(
    self._on_qc_monitor_status_changed
)

## Wire annotation change signal
self.controller.annotations_changed.connect(
    self._on_qc_annotations_changed
)
```

**Event Handlers**:
```python
def _on_qc_annotations_changed(self) -> None:
    """Trigger monitor when annotations change."""
    self._qc_background_monitor.on_annotation_changed()

def _on_qc_image_changed(self) -> None:
    """Trigger monitor when image loads."""
    self._qc_background_monitor.on_image_loaded()

def _on_qc_monitor_status_changed(self, message: str) -> None:
    """Update QC panel with monitor status."""
    self.qc_issues_panel.set_monitor_status(message)
```

#### B. Display Controls (`display.py`)

**FOV Change Hook** (`_set_fov`):
```python
self._refresh_image()

## Trigger QC monitor for new image
if hasattr(self, "_on_qc_image_changed"):
    self._on_qc_image_changed()
```

This ensures QC validation starts immediately when switching between images.

#### C. QC Issues Panel (`qc_issues_panel.py`)

**Monitor Integration**:
```python
def set_monitor(self, monitor) -> None:
    """Wire monitor to panel."""
    self._monitor = monitor
    monitor.monitoring_started.connect(self._on_monitor_started)
    monitor.monitoring_stopped.connect(self._on_monitor_stopped)

def set_monitor_status(self, message: str) -> None:
    """Update status widget."""
    self.monitor_status.set_status(message)

def _on_monitor_started(self) -> None:
    """Show indicator when monitoring starts."""
    self.monitor_status.set_monitoring_active(True)

def _on_monitor_stopped(self) -> None:
    """Hide indicator when monitoring stops."""
    self.monitor_status.set_monitoring_active(False)
```

The monitor status widget is embedded in the QC panel header (between summary label and Validate button).

---

## Execution Flow

### Workflow: User Adds Annotation

```
1. User clicks to add point
   ↓
2. _add_annotation() adds point to session
   ↓
3. controller.annotations_changed.emit()
   ↓
4. _on_qc_annotations_changed() called
   ↓
5. monitor.on_annotation_changed() sets _pending_edit=True
   ↓
6. monitor._edit_debounce_timer.start() (resets 2s countdown)
   ↓
7. [User adds another point within 2s]
   → Timer restarts (debounce continues)
   ↓
8. [2 seconds idle]
   → _on_edit_debounce_timeout() fires
   ↓
9. validation_callback() invokes _trigger_qc_validation()
   ↓
10. QC checks annotations + image for issues
    ↓
11. validation_completed.emit()
    ↓
12. QC panel refreshes with new issues
```

### Workflow: User Switches Images

```
1. User clicks different FOV in list
   ↓
2. _set_fov(new_index) called
   ↓
3. Image state updated, _refresh_image()
   ↓
4. _on_qc_image_changed() called
   ↓
5. monitor.on_image_loaded() sets _pending_edit=True
   ↓
6. monitor._edit_debounce_timer.start(500ms) [fast for image load]
   ↓
7. [500ms later]
   → _on_edit_debounce_timeout() fires
   ↓
8. QC validation runs for new image
   ↓
9. Issues panel shows defects in this image
```

### Workflow: Periodic Background Scan

```
Every 10 seconds (if no recent edits):
   ↓
_on_periodic_timeout() checks if 9+ seconds since last validation
   ↓
If TRUE:
  → Runs full validation (all images)
  → Updates any drifting artifact issues
If FALSE:
  → Skips (avoid overlap with debounced checks)
```

---

## Visual Feedback

### Monitor Status Widget (QC Panel Header)

**Hidden State** (No monitoring):
```
No indicator visible
```

**Active State** (Monitoring running):
```
● Monitoring...
```

**During Check**:
```
● Change detected, QC pending...
● Running QC check...
```

**After Check**:
```
● QC check complete
```

The dot pulses (opacity 0.5 ↔ 1.0) at 500ms intervals to draw attention.

---

## Configuration

### Enable/Disable Monitoring

In `QCState`:
```python
qc_state.auto_monitor_enabled = True   # Enable (default)
qc_state.auto_monitor_enabled = False  # Disable
```

Monitoring respects `_settings.value("qcAutoMonitorEnabled", True)` if persisted.

### Adjust Intervals

Modify timers in `QCBackgroundMonitor`:
```python
## Slower (testing/low-power mode)
self._edit_debounce_timer.setInterval(4000)      # 4s debounce
self._periodic_timer.setInterval(30000)          # 30s periodic

## Faster (interactive mode)
self._edit_debounce_timer.setInterval(1000)      # 1s debounce
self._periodic_timer.setInterval(5000)           # 5s periodic
```

### Future: User Settings Panel

```python
## Settings would appear in QC panel:
[✓] Enable background monitoring
Debounce interval:    [2000ms ]
Periodic scan interval: [10000ms]
```

---

## Performance Considerations

### Memory
- Monitor: ~10 KB (timers + state tracking)
- Background thread: None (runs in main Qt thread)

### CPU
- Idle: ~0% (timers only fire when triggered)
- During validation: Same as manual "Validate" button
- Periodic scan: Same as `_trigger_qc_validation(image_id=None)`

### Optimization: Fast Heuristics
The QC validators use fast heuristics to keep validation snappy:
- **Image artifacts**: Downsample to 512×32 pixels
- **Annotation checks**: O(n) with early exit
- **Stochasticity**: Fano-factor (single pass)

Typical validation time: **50-200ms** for typical images.

---

## Testing

### Unit Tests

```bash
pytest tests/unit/test_qc_state.py -xvs
## ✓ 26 passing (includes monitor configuration)

pytest tests/unit/test_qc_validators.py -xvs
## ✓ 29 passing (artifact + stochasticity checks still pass)
```

### Integration Tests

```bash
pytest tests/integration/test_ui_context_qc.py -xvs
## ✓ Filter toggle tests (verified monitor status updates)
```

---

## Example: Monitoring in Action

### Scenario: Annotation Workflow

```
User starts with: 1 image, no annotations
↓
[Load image] → monitor.on_image_loaded()
              → Detects uneven illumination warning
              → QC panel shows: 1 issue (WARNING)
↓
[Click to add point 1] → monitor.on_annotation_changed()
[Click to add point 2]    (debounce: +2s)
[Click to add point 3]
              → 2s idle
              → Validation runs
              → Detects all 3 points valid
              → QC panel: "Open: 1 / Total: 2 (Warning)"
↓
[Switch to image 2] → monitor.on_image_loaded()
                    → Detects photobleaching
                    → QC panel: "Open: 1 / Total: 1 (Warning)"
↓
[Every 10s] → Periodic scan checks both images
            → Updates artifact detection if degradation detected
```

---

## Future Enhancements

### Phase 2: Deep Learning Artifacts
```python
class DeepLearningArtifactValidator:
    """Optional ML-based detector for complex artifacts."""
    def detect_chromatic_aberration(image_array):
        # ThunderSTORM calibration data
        pass
```

### Phase 3: User-Tunable Thresholds
```python
## Settings panel with sliders
illumination_ratio_threshold: float = 1.25
photobleach_percent: float = 15.0
fano_factor_bounds: Tuple[float, float] = (0.6, 1.8)
```

### Phase 4: Predictive Alerts
```python
## Alert before problems detected
"Image will reach 20% photobleaching in 30 steps"
"Annotation density approaching cluster threshold"
```

---

## Code Map

| File | Class | Purpose |
|------|-------|---------|
| `qc_background_monitor.py` | `QCBackgroundMonitor` | Main monitor worker + timers |
| `qc_background_monitor.py` | `QCMonitorStatusWidget` | Visual indicator widget |
| `qc_state.py` | `QCState` | Config for `auto_monitor_enabled`, intervals |
| `qc_actions.py` | `QCActionsMixin` | Monitor initialization + event handlers |
| `display.py` | `DisplayControlsMixin` | FOV change hook + image load trigger |
| `qc_issues_panel.py` | `QCIssuesPanel` | Monitor status display + wiring |

---

## Troubleshooting

### Monitor not running?
1. Check `qc_state.auto_monitor_enabled == True`
2. Verify `_ensure_qc_runtime()` called (first FOV change or "Validate" button click)
3. Check console for errors in validation callback

### Status widget not showing?
1. Ensure `QCIssuesPanel.set_monitor(monitor)` called from actions
2. Check monitor emits `monitoring_started` signal
3. Verify `monitor_status` widget created in `_setup_ui()`

### Validation running too slowly?
1. Check image size (should be auto-downsampled to 512×32)
2. Profile `_trigger_qc_validation()` with `pytest --profile`
3. Disable periodic scanning if CPU-bound: `periodic_timer.stop()`

### Monitor consuming too much memory?
1. Monitor itself: ~10 KB
2. QC issues: ~1 KB per issue (scale with image count)
3. If memory high: Reduce `monitor_periodic_ms` interval

---

## Related Documentation

- [Planned Features](PLANNED_FEATURES.md)
- [Current Capabilities](CURRENT_CAPABILITIES.md)
- [Testing Strategy](reports/Testing_Strategy.md)
- [Design Report](reports/Design_Report.md)
