# LAZY LOADING DEBUGGING QUICK REFERENCE

## The 3-Tier System

```
TIER 1: User Intent          TIER 2: Layout Spec          TIER 3: Rendering
────────────────────────────────────────────────────────────────────────────
_lazy_builtin_views     →    _panel_modality_map     →    _refresh_image()
_lazy_modality_groups        (ModalitySpec objects)       (Render to canvas)

[User edits table]           [Sync point via             [Hardcoded bugs
 ↓                           _current_layout_spec()]      here! ⚠️]
Store in dict #1      →      Merge into dict #2      →    Should use dict #2
```

---

## Signal → Handler → State Update → Canvas Refresh Chain

```
┌─ TIER 1 CHANGES ─┐
│ User edits row  │  Col 2 → _on_lazy_modality_item_changed()
│ in table        │  Col 3 → _on_lazy_modality_source_changed()
└─────────────────┘  Col 4 → _on_lazy_modality_projection_changed()
        ↓
┌─ STATE UPDATE ──┐
│ Handler stores  │  Updates one of:
│ new value       │  • _lazy_builtin_views (builtin rows)
│                 │  • modality.property via manager (modality rows)
└─────────────────┘
        ↓
┌─ CHECK: AUTO? ──┐
│ Is auto-update  │  YES → calls _apply_lazy_pending_updates()
│ enabled?        │  NO  → enables "Update Canvas" button
└─────────────────┘
        ↓
┌─ SYNC TIER 1→2 ┐
│ _apply_lazy_   │  Calls:
│ pending_       │  1. _refresh_lazy_modality_table() [rebuild UI]
│ updates()      │  2. _refresh_image() [rebuild canvas]
└─────────────────┘
        ↓
┌─ SYNC TIER 2→3 ┐
│ _current_      │  Reads from Tier 1:
│ layout_spec()  │  • _lazy_builtin_views
│ [SYNC POINT]   │  • manager modality settings
│                │  Writes to Tier 2:
└─────────────────┘  • _panel_modality_map specs
        ↓
┌─ RENDER (TIER3)┐
│ _refresh_      │  ⚠️ BUG: Doesn't use Tier 2!
│ image()        │  Hardcodes prim = self.primary_image
│ [BUG HERE!]    │  Should use: _panel_modality_map[key].image_id
└─────────────────┘
        ↓
   CANVAS SHOWS
   (Usually WRONG image!)
```

---

## Handler Locations (What Gets Called)

| Change | Handler Function | File | Line | Issue |
|--------|------------------|------|------|-------|
| Name (Col 2) | `_on_lazy_modality_item_changed()` | ui_extra.py | 2086 | Name change might not show on canvas |
| Source (Col 3) | `_on_lazy_modality_source_changed()` | ui_extra.py | 2176 | Wrong image rendered (hardcoded prim) |
| Projection (Col 4) | `_on_lazy_modality_projection_changed()` | ui_extra.py | 2189 | Same as source - wrong image |
| Projection builtin | `_on_lazy_builtin_projection_changed()` | ui_extra.py | 2231 | Same as source - wrong image |
| Source builtin | `_on_lazy_builtin_source_changed()` | ui_extra.py | 2216 | Same as source - wrong image |

---

## State Dictionary Keys

### `_lazy_builtin_views` (What user wants for mean/std)
```python
{
    "mean": {
        "name": "Mean Projection",      # Display name (custom)
        "image_id": 1,                  # Which image to compute from
        "projection": "mean"            # Type (mean/std/min/max)
    },
    "std": {
        "name": "Std Projection",
        "image_id": 1,
        "projection": "std"
    }
}
```

### `_panel_modality_map` (Current canvas layout)
```python
{
    "frame": ModalitySpec(
        idx=0,
        image_id=1,
        display_name="Frame",
        projection_type=ProjectionType.RAW,
        display_settings=DisplaySettings(...)
    ),
    "mean": ModalitySpec(
        idx=-101,
        image_id=1,                    # Should match _lazy_builtin_views["mean"]["image_id"]
        display_name="Mean Projection", # Should match _lazy_builtin_views["mean"]["name"]
        projection_type=ProjectionType.MEAN,
        display_settings=DisplaySettings(...)
    ),
    ...
}
```

---

## Sync Point: _current_layout_spec() (roi_crop.py:80)

```python
def _current_layout_spec(self) -> dict:
    # This function:
    # 1. Reads from _lazy_builtin_views
    # 2. Updates _panel_modality_map with new values
    # 3. Returns layout spec used for figure layout
    
    # This is where Tier 1 → Tier 2 happens
    
    # IF WORKING CORRECTLY:
    # - Changes in _lazy_builtin_views flow into _panel_modality_map
    # - Tier 2 always reflects Tier 1
    
    # IF BROKEN:
    # - _lazy_builtin_views changes don't reach Tier 2
    # - OR Tier 2 updates aren't used in renderer
```

---

## Bug Locations Cheat Sheet

### 🔴 CRITICAL: Projection Image Bug
**File**: `src/phage_annotator/ui_qt/rendering/renderer.py`
**Lines**: 198, 237, 239
**Code**:
```python
prim = self.primary_image
mean_data, mean_ready = self._get_projection(prim, "mean")  # ← WRONG
#                                             ^^^^
#                                    Should use:
#                                    self.images[self._panel_modality_map["mean"].image_id]
```

### 🟠 HIGH: Display Settings Bug
**File**: `src/phage_annotator/ui_qt/rendering/renderer.py`
**Lines**: 320-340
**Code**:
```python
mean_mapping = self._get_display_mapping(prim.id, "mean", mean_data)
#                                        ^^^^^^^
#                            Uses prim's display settings
#                            Should use correct image's settings
```

### 🟠 MEDIUM: Name Rendering Bug (Unclear Location)
**Possible Files**:
- `src/phage_annotator/ui_qt/rendering/roi_crop.py` (line 80)
- `src/phage_annotator/ui_qt/rendering/renderer.py` (title rendering)
**Issue**: Name changes stored in _lazy_builtin_views but never shown on canvas

### 🟡 LOW: Missing Refresh Without Auto-Update
**File**: `src/phage_annotator/ui_qt/utils/ui_extra.py`
**Lines**: 2176-2243
**Issue**: If auto-update disabled, canvas doesn't refresh until "Update Canvas" clicked

---

## Debugging Checklist

When testing a fix:

- [ ] Change Mean projection source from Image 1 → Image 2
  - [ ] With Auto-Update ON: Should show Image 2's mean immediately
  - [ ] With Auto-Update OFF: Click "Update Canvas", should show Image 2's mean
  - [ ] Contrast should match Image 2's settings
  
- [ ] Change Mean projection NAME
  - [ ] Canvas title should update immediately
  - [ ] _lazy_modality_table shows new name
  
- [ ] Change Std projection source from Image 1 → Image 3
  - [ ] Same as Mean tests
  
- [ ] Test with custom Modality 3+
  - [ ] Should already work (uses _panel_modality_map correctly)
  - [ ] Use as reference for correct behavior
  
- [ ] Zoom slider test
  - [ ] Set zoom value in toolbar
  - [ ] Should apply to current panel's image
  - [ ] If projection source is different, should use correct zoom value

---

## Quick Facts

| Fact | Details |
|------|---------|
| **Row 0** | "Frame" (primary modality, idx=0) |
| **Row 1** | "Support" (secondary modality, idx=1) |
| **Row 2** | "Mean" (builtin, idx=-101, projection always reads from _lazy_builtin_views) |
| **Row 3** | "Std" (builtin, idx=-103, projection always reads from _lazy_builtin_views) |
| **Row 4+** | Custom modalities added by user (idx=2, 3, 4, ...) |
| **Auto-Update Button** | In lazy panel header, checkbox labeled "Auto-Update" |
| **Update Canvas Button** | Blue button next to Auto-Update, enabled when changes pending |
| **Cache Key** | Projection cache includes: image_id, kind, axis, modality_idx |
| **State Sync** | Happens in _current_layout_spec(), NOT in handlers |

---

## One-Liner Bug Fix Ideas (Before Deep Dive)

```python
# In renderer.py line 198, instead of:
prim = self.primary_image
mean_data, _ = self._get_projection(prim, "mean")

# Try:
mean_spec = self._panel_modality_map.get("mean") or ModalitySpec(..., image_id=prim.id)
mean_img = self.images[mean_spec.image_id] if 0 <= mean_spec.image_id < len(self.images) else prim
mean_data, _ = self._get_projection(mean_img, "mean")
```

---

**Use these references while debugging and fixing!**
