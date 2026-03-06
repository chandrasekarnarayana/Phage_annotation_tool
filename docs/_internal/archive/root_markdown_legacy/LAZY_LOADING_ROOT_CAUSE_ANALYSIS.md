# EXECUTIVE SUMMARY: Why Lazy Loading Changes Don't Work

## TL;DR - The Core Issues

| Issue | Cause | Evidence | Severity |
|-------|-------|----------|----------|
| **Row 2+ name changes don't appear on canvas** | Panel title not re-rendered OR _current_layout_spec() not reading from _lazy_builtin_views correctly | Name is stored in _lazy_builtin_views but canvas never shows it | 🔴 HIGH |
| **Mean/Std projection source changes don't work** | _refresh_image() hardcodes primary_image instead of reading image_id from _panel_modality_map | `prim = self.primary_image` then `self._get_projection(prim, "mean")` ignores the spec | 🔴 HIGH |
| **Contrast/zoom/pan don't update for projections** | Same root cause - wrong image used, wrong display settings applied | Uses primary image's settings instead of the source image's settings | 🔴 HIGH |
| **Row changes don't refresh canvas without auto-update** | Handlers only call _refresh_image() if auto-update is enabled | Without auto-update, changes stored but canvas never refreshed | 🟠 MEDIUM |
| **Zoom/pan buttons inactive** | Canvas might not be in interactive mode OR custom modality canvases don't have tools | Matplotlib toolbar not properly initialized for modality_canvas.py | 🟠 MEDIUM |

---

## The Three Conflicting Realities

The code has THREE different concepts of "what image should be displayed" and they don't always agree:

### 1. **User's Intent** (Stored in _lazy_builtin_views)
```python
self._lazy_builtin_views = {
    "mean": {
        "image_id": 2,        # User wants mean of IMAGE 2
        "projection": "mean",
        "name": "Mean of Second Image"
    }
}
```

### 2. **Current Canvas Layout** (Stored in _panel_modality_map)
```python
self._panel_modality_map = {
    "mean": ModalitySpec(
        idx=-101,
        image_id=2,           # This SHOULD be 2 (from _lazy_builtin_views)
        display_name="Mean of Second Image",
        projection_type=ProjectionType.MEAN,
        ...
    )
}
```

### 3. **What Actually Gets Rendered** (Hardcoded in renderer.py)
```python
def _refresh_image(self):
    prim = self.primary_image  # Always Image 1!
    mean_data, _ = self._get_projection(prim, "mean")  # Always computes from Image 1
    # Ignores that _panel_modality_map["mean"].image_id is 2!
```

**The Problem**: #1 says show Image 2, #2 thinks Image 2, but #3 shows Image 1. ❌

---

## What SHOULD Happen vs What ACTUALLY Happens

### SCENARIO: User changes Mean projection source from Image 1 → Image 2

**WHAT SHOULD HAPPEN** (Correct Flow):
```
1. User: clicks "Mean" row's SOURCE dropdown, selects Image 2
   ↓
2. Signal: currentIndexChanged(2) on source combo
   ↓
3. Handler: _on_lazy_builtin_source_changed("mean", image_id=2)
   ├─ _lazy_builtin_views["mean"]["image_id"] = 2  ← Stored ✓
   ├─ Check: is auto-update enabled?
   └─ YES: call _apply_lazy_pending_updates()
   
4. _apply_lazy_pending_updates():
   ├─ _refresh_lazy_modality_table()  ← Rebuild table UI
   ├─ _refresh_image()                ← Rebuild canvas
   
5. Inside _refresh_image():
   ├─ _current_layout_spec()
   │  └─ Read from _lazy_builtin_views["mean"]["image_id"]: 2
   │     Update _panel_modality_map["mean"].image_id = 2  ← Sync ✓
   │
   ├─ Render Mean projection:
   │  ├─ Look up: image = self.images[2]  ← Use Image 2 ✓
   │  ├─ mean_data = self._get_projection(image, "mean")
   │  └─ Apply Image 2's display settings (contrast, colormap)
   │
   └─ canvas.draw()  ← Show Image 2's mean projection ✓

6. RESULT: Canvas shows Image 2's mean projection ✓ ✓ ✓
```

**WHAT ACTUALLY HAPPENS** (Current Broken Flow):
```
1. User: clicks "Mean" row's SOURCE dropdown, selects Image 2
   ↓
2. Signal: currentIndexChanged(2) on source combo
   ↓
3. Handler: _on_lazy_builtin_source_changed("mean", image_id=2)
   ├─ _lazy_builtin_views["mean"]["image_id"] = 2  ← Stored ✓
   ├─ Check: is auto-update enabled?
   ├─ NO: return (button enabled, wait for user to click "Update Canvas")
   ├─ OR YES: call _apply_lazy_pending_updates()
   
4. _apply_lazy_pending_updates():
   ├─ _refresh_lazy_modality_table()  ← Rebuild table UI
   ├─ _refresh_image()                ← Rebuild canvas
   
5. Inside _refresh_image():
   ├─ _current_layout_spec()
   │  └─ SHOULD read from _lazy_builtin_views["mean"]["image_id"]: 2
   │     But _panel_modality_map["mean"].image_id updated??? (assume yes)
   │
   ├─ Render Mean projection:
   │  ├─ prim = self.primary_image  ← HARDCODED TO IMAGE 1 ✗
   │  ├─ mean_data = self._get_projection(prim, "mean")  ← Image 1 ✗
   │  │   Even though _panel_modality_map says image_id=2!
   │  └─ Apply Image 1's display settings (not Image 2's) ✗
   │
   └─ canvas.draw()  ← Show Image 1's mean projection ✗ (WRONG!)

6. RESULT: Canvas shows Image 1's mean projection (WRONG) ✗ ✗ ✗
```

---

## The Code Path Analysis

### File: `src/phage_annotator/ui_qt/utils/ui_extra.py` (Lines 2216-2243)

**Handler that catches source changes**:
```python
def _on_lazy_builtin_source_changed(self, panel_key: str, image_id: int) -> None:
    builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
    cfg = dict(builtin.get(str(panel_key), {}) or {})
    cfg["image_id"] = int(image_id)              # ← STORES the new image_id
    builtin[str(panel_key)] = cfg
    self._lazy_builtin_views = builtin
    
    if bool(getattr(self, "lazy_auto_update_chk", None) and 
            self.lazy_auto_update_chk.isChecked()):
        self._apply_lazy_pending_updates()       # ← IF AUTO-UPDATE, refresh now
    # ELSE: Canvas doesn't update!
```

### File: `src/phage_annotator/ui_qt/rendering/roi_crop.py` (Lines 80-230)

**Where the state should be read back out**:
```python
def _current_layout_spec(self) -> dict:
    # ... setup code ...
    
    for key, cfg, default_projection in (
        ("mean", mean_cfg, ProjectionType.MEAN),
        ("std", std_cfg, ProjectionType.STD),
    ):
        spec = self._panel_modality_map.get(key)
        if spec is None:
            continue
        
        image_id = int(cfg.get("image_id", spec.image_id))  # ← Reads from cfg
        spec.image_id = image_id                            # ← UPDATES spec
        
        # GOOD: This should work correctly
        # _panel_modality_map["mean"].image_id should now be 2
```

### File: `src/phage_annotator/ui_qt/rendering/renderer.py` (Lines 198-250)

**Where the bug happens**:
```python
def _refresh_image(self) -> None:
    prim = self.primary_image    # ← HARDCODED to primary
    supp = self.support_image    # ← HARDCODED to support
    
    # ... slice data from primary ...
    slice_data = self._slice_data(prim)
    
    # ⚠️ HERE'S THE BUG:
    mean_data, mean_ready = self._get_projection(prim, "mean")
    #                                             ^^^^
    #                    ALWAYS uses primary image!
    #                    Even if _panel_modality_map["mean"].image_id = 2
    
    std_data, std_ready = self._get_projection(prim, "std")
    #                                           ^^^^
    #                    ALWAYS uses primary image!
    
    # BUT for custom modalities, it DOES read from the map:
    if getattr(self, "_panel_modality_map", None):
        for key, modality in self._panel_modality_map.items():
            img = self.images[modality.image_id]  # ← Uses map here ✓
            data, _ready = self._get_projection(img, ...)
```

**The Inconsistency**: Mean/std use `prim`, but custom modalities use `_panel_modality_map`!

---

## Why This Causes Cascading Failures

### Failure 1: Wrong projection image
```python
mean_data = self._get_projection(prim, "mean")  # Always Image 1
# Should be: mean_image = self.images[_panel_modality_map["mean"].image_id]
#            mean_data = self._get_projection(mean_image, "mean")
```

### Failure 2: Wrong contrast settings
```python
mean_mapping = self._get_display_mapping(prim.id, "mean", mean_data)
# Gets contrast for Image 1, not Image 2
# Should look up correct image's display_settings from _panel_modality_map
```

### Failure 3: Wrong colormap applied
```python
panel_cmaps = {
    "mean": cmap_for(_spec(mean_mapping.lut), mean_mapping.invert),
    # Uses Image 1's colormap index
}
# Should use Image 2's colormap from display_settings
```

### Failure 4: Zoom/pan don't work
```python
# Zoom values are stored per-modality in display_settings
# But if we're using wrong image, we use wrong zoom value
zoom_value = self._panel_modality_map["mean"].display_settings.zoom
# But we render using prim's zoom value (implicitly)
```

---

## One More Bug: Row 2 Name Change

When you change the name of the Mean projection:

**Path 1: Name is stored** ✓
```python
builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
cfg = dict(builtin.get("mean", {}) or {})
cfg["name"] = "New Name"
builtin["mean"] = cfg
self._lazy_builtin_views = builtin  # ← STORED
```

**Path 2: Should be read and applied to spec** ?
```python
# In _current_layout_spec():
spec = self._panel_modality_map.get("mean")
if spec is None:
    continue
if str(cfg.get("name", "")).strip():
    spec.display_name = str(cfg["name"]).strip()  # ← Applied to spec?
```

**Path 3: Should be rendered on canvas** ?
```python
# In renderer.py, the panel title is rendered
# But is it reading from spec.display_name?
# Or is it hardcoded to "Mean Projection"?
# ⚠️ UNCLEAR - need to check
```

**Suspicion**: Either the name is NOT being read from _lazy_builtin_views into the spec,
or the canvas title is hardcoded and never reads from the spec.

---

## Summary of Root Causes

| Issue | Root Cause | Location | Why It Breaks |
|-------|-----------|----------|---------------|
| Projection source not changing | Hardcoded `prim` used instead of looking up image_id | `renderer.py:198-250` | Always renders from primary image |
| Contrast not updating | Uses primary image's mapping instead of source image's | `renderer.py:320-340` | Wrong image's display settings applied |
| Row 2 name not showing | Either _lazy_builtin_views not read into spec, or canvas title hardcoded | `roi_crop.py:80-230` or `renderer.py:title rendering` | Name change never reaches canvas |
| Zoom/pan inactive | Matplotlib tools might not be enabled, or custom canvases don't have tools | `main_window.py` or `modality_canvas.py` | Tools not wired up |
| No refresh without auto-update | Handler doesn't call _refresh_image() when auto-update disabled | `ui_extra.py:2176+` | Changes stored but canvas never updated |

---

## Files That Need Changes

1. **`renderer.py` (HIGH PRIORITY)**
   - Lines 198-250: Replace hardcoded `prim` with lookup from `_panel_modality_map`
   - Lines 320-340: Use correct image's display settings

2. **`roi_crop.py` (MEDIUM PRIORITY)**
   - Lines 80-230: Verify `_lazy_builtin_views` is read into `_panel_modality_map` correctly
   - Check if name updates are preserved

3. **`ui_extra.py` (MEDIUM PRIORITY)**
   - Lines 2176-2243: Consider always calling `_refresh_image()` even without auto-update
   - OR make it clear user must click "Update Canvas"

4. **`modality_canvas.py` (LOW PRIORITY - if zoom/pan needed)**
   - Enable interactive mode
   - Ensure matplotlib toolbar is properly initialized

---

## Next Steps (When Ready to Fix)

1. **First**: Fix the hardcoded `prim` issue in renderer.py
   - Replace with `self.images[_panel_modality_map[key].image_id]`
   - This will fix projection images, contrast, colormaps, and zoom/pan

2. **Second**: Verify _lazy_builtin_views → _panel_modality_map sync
   - Check _current_layout_spec() reads all values correctly
   - Test row 2 name change

3. **Third**: Add refresh call for non-auto-update changes
   - Maybe always call _refresh_image() for projection changes
   - Or make "Update Canvas" button required for all changes (currently is)

4. **Fourth**: Test zoom/pan if still broken
   - Enable interactive mode on canvas
   - Wire up matplotlib toolbar to custom modality axes

---

## Key Learning: The Design Is Actually Good

The architecture with `_lazy_builtin_views` and `_panel_modality_map` is sound:
- Stores user's pending changes in one dict
- Merges into spec dict on demand
- Renders from spec dict

**The Bug**: The render code doesn't consistently use the spec dict.
It should be:

```python
# GOOD: Consistent pattern
for key in ["frame", "support", "mean", "std"]:
    spec = self._panel_modality_map.get(key)
    if spec is None:
        continue
    image = self.images[spec.image_id]
    data = self._get_projection(image, spec.projection_type.value)
    apply_settings_from(spec.display_settings)
    render(data, settings, title=spec.display_name)
```

Currently it mixes: hardcoded `prim`, `spec`, and `builtin`. 🔀

---

**This explanation should help you understand exactly what's wrong and where to fix it.**
**No code changes yet - just pure diagnosis!**
