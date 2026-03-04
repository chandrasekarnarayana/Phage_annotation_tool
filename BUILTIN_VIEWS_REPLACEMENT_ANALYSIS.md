# Builtin Views Replacement Analysis

## Overview
This document identifies all regions where the hardcoded "frame", "support", "mean", and "std" views are referenced, so they can be completely replaced with a unified modality system.

## Architecture Summary

### Current System (Problematic)
```
┌─────────────────────────────────────────────────────┐
│ TIER 1: Storage                                     │
├─────────────────────────────────────────────────────┤
│ • _lazy_builtin_views (dict)                        │
│   Keys: "frame", "support", "mean", "std"           │
│   Values: {name, image_id, projection}              │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│ TIER 2: Layout Spec                                 │
├─────────────────────────────────────────────────────┤
│ • _panel_modality_map (dict)                        │
│   Keys: "frame", "support", "mean", "std"           │
│   Values: ModalitySpec objects                      │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│ TIER 3: Rendering (INCONSISTENT!)                   │
├─────────────────────────────────────────────────────┤
│ • frame/support/mean/std: Hardcoded to prim/supp    │
│ • Custom modalities: Read from _panel_modality_map  │
│   ⚠️ MIXED APPROACH CAUSES BUGS                     │
└─────────────────────────────────────────────────────┘
```

### Target System (Unified)
```
All modalities treated uniformly through _panel_modality_map
No special cases for "frame"/"mean"/"std"/"support"
```

---

## Files and Regions to Replace

### 1. **Main Window Initialization**
**File**: `src/phage_annotator/ui_qt/main_window.py`

**Lines 186, 198**:
```python
self._lazy_builtin_views = {}
self._panel_modality_map: Dict[str, object] = {}
```

**Action**: 
- Remove `_lazy_builtin_views` completely
- Keep only `_panel_modality_map` as single source of truth
- Initialize with default modalities in a unified way

---

### 2. **Layout Specification Builder**
**File**: `src/phage_annotator/ui_qt/rendering/roi_crop.py`

#### **Lines 80-230**: `_current_layout_spec()` method

**Current approach** (HARDCODED):
```python
# Lines 84-165: Explicit hardcoded sections
self._panel_modality_map["frame"] = ModalitySpec(...)
self._panel_modality_map["mean"] = ModalitySpec(...)
self._panel_modality_map["support"] = ModalitySpec(...)
self._panel_modality_map["std"] = ModalitySpec(...)
```

**Replacement strategy**:
```python
# Unified approach - build ALL modalities the same way
def _current_layout_spec(self):
    self._panel_modality_map = {}
    
    # Get all active modalities from session/state
    active_modalities = self._get_active_modalities()
    
    for modality in active_modalities:
        key = modality.key  # e.g., "frame", "mean", "custom_1"
        self._panel_modality_map[key] = ModalitySpec(
            image_id=modality.image_id,
            display_name=modality.display_name,
            projection_type=modality.projection_type,
            display_settings=modality.display_settings,
        )
```

**References to replace**:
- Line 84: `self._panel_modality_map = {}`
- Line 125: `self._panel_modality_map["frame"] = ...`
- Line 134: `self._panel_modality_map["mean"] = ...`
- Line 156: `self._panel_modality_map["support"] = ...`
- Line 165: `self._panel_modality_map["std"] = ...`
- Lines 174-226: Special handling for builtin vs custom modalities

---

### 3. **Renderer - Primary Image Resolution**
**File**: `src/phage_annotator/ui_qt/rendering/renderer.py`

#### **Lines 190-260**: Image lookup and projection (ROOT CAUSE OF BUGS)

**Current approach** (HARDCODED):
```python
# Lines 193-196: Hardcoded image lookup
frame_img = _panel_image("frame", prim)
support_img = _panel_image("support", supp)
mean_img = _panel_image("mean", prim)      # ⚠️ ALWAYS uses prim!
std_img = _panel_image("std", prim)        # ⚠️ ALWAYS uses prim!

# Lines 204-206: Hardcoded projection types
frame_projection = _panel_projection_key("frame", "raw")
support_projection = _panel_projection_key("support", "raw")
mean_projection = _panel_projection_key("mean", "mean")
std_projection = _panel_projection_key("std", "std")
```

**Replacement strategy**:
```python
# Unified approach - lookup ALL from _panel_modality_map
for key, spec in self._panel_modality_map.items():
    img = self.images[spec.image_id]  # Use correct image!
    self._ensure_loaded(spec.image_id)
    projection = spec.projection_type.value
    # ... rest of rendering logic
```

**Critical lines to replace**:
- Line 193-196: Replace with unified loop over `_panel_modality_map`
- Line 197-200: Replace `_ensure_loaded` with loop
- Line 204-206: Replace with reading from spec
- Line 246-253: Replace hardcoded mean/std projection logic

---

#### **Lines 260-360**: Display data and titles

**Current approach** (HARDCODED):
```python
# Lines 267-271: Hardcoded axis lookups
frame_ax = self.renderer.axes.get("frame")
mean_ax = self.renderer.axes.get("mean")
std_ax = self.renderer.axes.get("std")

# Lines 273-311: Hardcoded pyramid lookups
slice_display = self._get_pyramid_display(prim.id, "frame", ...)
mean_display = self._get_pyramid_display(prim.id, mean_kind, ...)  # ⚠️ prim.id!
std_display = self._get_pyramid_display(prim.id, std_kind, ...)    # ⚠️ prim.id!

# Lines 319-340: Hardcoded titles and panel_images dict
titles = {
    "frame": _panel_title("frame", "Modality 1"),
    "mean": _panel_title("mean", "Mean Projection"),
    "support": _panel_title("support", "Modality 2"),
    "std": _panel_title("std", "Std Projection"),
}
panel_images: Dict[str, np.ndarray] = {
    "frame": slice_display,
    "mean": mean_display,
    "support": support_display,
    "std": std_display,
}
```

**Replacement strategy**:
```python
# Build dynamically from _panel_modality_map
titles = {}
panel_images = {}
for key, spec in self._panel_modality_map.items():
    titles[key] = self._get_panel_title(spec, t_idx, z_idx)
    panel_images[key] = self._render_panel(spec, t_idx, z_idx)
```

**Lines to replace**:
- 267-271: Remove hardcoded axis lookups
- 289-311: Remove hardcoded pyramid lookups for mean/std
- 319-328: Replace with dynamic dict comprehension
- 335-340: Replace with dynamic dict comprehension
- 349-385: Unify builtin and custom modality rendering

---

#### **Lines 418-450**: Annotations overlay (hardcoded panel keys)

**Current approach**:
```python
if getattr(self, "_panel_modality_map", None):
    for key, modality in self._panel_modality_map.items():
        if key in {"frame", "mean", "std", "support"}:  # ⚠️ Hardcoded check
            continue
        # ... render custom modalities
```

**Replacement**: Remove the special check, treat all uniformly

---

### 4. **UI Controls and Event Handlers**
**File**: `src/phage_annotator/ui_qt/utils/ui_extra.py`

#### **Lines 297-305**: Panel configuration lookup
```python
panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
# Hardcoded keys: "frame", "support"
cfg = dict(dict(getattr(self, "_lazy_builtin_views", {}) or {}).get(key, {}) or {})
support_cfg = dict(dict(getattr(self, "_lazy_builtin_views", {}) or {}).get("support", {}) or {})
```

**Replacement**: Remove `_lazy_builtin_views` lookups

---

#### **Lines 1531-1548**: `_on_lazy_modality_item_changed()` handler

**Current approach**:
```python
builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
# ... modify builtin dict
self._lazy_builtin_views = builtin
```

**Replacement**: Directly update `_panel_modality_map` or session state

---

#### **Lines 1688**: Panel key check
```python
cfg = dict(self._lazy_builtin_views.get(panel_key, {}) or {})
```

**Replacement**: Use `_panel_modality_map` directly

---

#### **Lines 1936-2084**: Multiple handlers reading `_lazy_builtin_views`

**All instances**:
- Line 1936: `_add_lazy_modality_view()`
- Line 1957: `_remove_lazy_view_row()`
- Line 2017: `_on_lazy_view_name_edit()`
- Line 2080: `_on_lazy_view_dropdown_change()`
- Line 2218: `_refresh_lazy_modality_table_combo()`
- Line 2235: `_refresh_lazy_modality_table()`

**Replacement**: Update to use unified modality management system

---

### 5. **Event Connections**
**File**: `src/phage_annotator/ui_qt/actions/events.py`

**Lines 30-31**:
```python
self.lazy_add_mean_btn.pressed.connect(lambda: self._add_lazy_modality_view("mean"))
self.lazy_add_std_btn.pressed.connect(lambda: self._add_lazy_modality_view("std"))
```

**Replacement**: Generic "Add Projection" button that doesn't hardcode mean/std

---

### 6. **Display Settings Helpers**
**File**: `src/phage_annotator/ui_qt/rendering/renderer.py`

**Lines 765, 1014**: Panel map lookups
```python
panel_map = dict(getattr(self, "_panel_modality_map", {}) or {})
```

**Action**: Ensure all lookups use panel keys generically, not hardcoded

---

### 7. **View State Management**
**File**: `src/phage_annotator/ui_qt/utils/state.py`

**Lines 241, 249**:
```python
return self.controller.view_state.show_ann_frame
return self.controller.view_state.show_ann_mean
```

**Replacement**: Generic annotation visibility per modality key

---

### 8. **Session State**
**File**: `src/phage_annotator/core/session_state.py`

**Line 63**:
```python
annotate_target: str = "mean"
```

**Replacement**: Generic modality key, not hardcoded to "mean"

---

### 9. **Documentation Files** (Update after code changes)
- `LAZY_LOADING_DETAILED_EXPLANATION.md`
- `LAZY_LOADING_FLOW_DIAGRAMS.md`
- `LAZY_LOADING_ROOT_CAUSE_ANALYSIS.md`
- `LAZY_LOADING_QUICK_REFERENCE.md`
- `EXPLANATION_COMPLETE.md`

---

## Replacement Strategy Summary

### Phase 1: Unify Data Storage
1. Remove `_lazy_builtin_views` completely
2. Store all modality configurations in `_panel_modality_map` or session state
3. Use generic modality keys instead of hardcoded "frame"/"mean"/"std"/"support"

### Phase 2: Unify Layout Building
1. Rewrite `_current_layout_spec()` to build all modalities uniformly
2. Remove special cases for builtin vs custom modalities
3. Single code path for all panel types

### Phase 3: Unify Rendering
1. In `renderer.py`, replace hardcoded `prim`/`supp` lookups with `_panel_modality_map[key].image_id`
2. Remove separate logic for frame/mean/std vs custom modalities
3. Use single loop: `for key, spec in self._panel_modality_map.items()`

### Phase 4: Update UI Controls
1. Remove `_lazy_builtin_views` references from `ui_extra.py`
2. Update event handlers to work with generic modality keys
3. Remove hardcoded button labels for "mean" and "std"

### Phase 5: Testing
1. Verify Row 2+ name changes appear on canvas
2. Verify mean/std can read from any source image
3. Verify zoom/pan/contrast work for all modalities
4. Verify no regression for frame and support panels

---

## Benefits of Unified System

✅ **Consistency**: All modalities rendered the same way
✅ **Flexibility**: Users can create arbitrary projections from any source
✅ **Bug-free**: No special cases to maintain
✅ **Extensibility**: Easy to add new modality types
✅ **Maintainability**: Single code path instead of three

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking existing sessions | Add migration logic to convert old _lazy_builtin_views to new format |
| UI layout changes | Preserve panel keys "frame", "mean", "std", "support" for backward compatibility |
| Performance regression | Use same caching/lazy loading mechanisms |
| Test coverage gaps | Expand integration tests for all modality types |

---

## Next Steps

1. Create unified `ModalityManager` class in session
2. Update `_current_layout_spec()` to use manager
3. Replace hardcoded lookups in `renderer.py`
4. Remove `_lazy_builtin_views` from codebase
5. Update documentation
6. Add migration tests

