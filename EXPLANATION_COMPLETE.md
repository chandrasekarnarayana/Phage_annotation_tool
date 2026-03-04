# 📋 COMPREHENSIVE EXPLANATION: Complete (NO CODE CHANGES YET)

## What Was Explained

I've analyzed the entire lazy loading system and created **4 detailed documents** explaining:

1. **LAZY_LOADING_DETAILED_EXPLANATION.md**
   - How row changes are detected (signals connected to handlers)
   - Why Row 1 works but Row 2 doesn't (name change bug)
   - Why projections don't change images (hardcoded `prim` instead of reading from spec)
   - Why contrast/zoom/pan don't update (uses wrong image's settings)
   - Complete code path analysis

2. **LAZY_LOADING_FLOW_DIAGRAMS.md**
   - Visual flow diagrams of the entire change chain
   - State synchronization between the 3 dictionaries
   - Current (buggy) vs. Correct rendering flow
   - Call stack diagram
   - Row type handling and where they differ

3. **LAZY_LOADING_ROOT_CAUSE_ANALYSIS.md**
   - Executive summary of all issues
   - Three conflicting realities (what user wants vs what code does)
   - Detailed scenario: user changes projection source, what should happen vs. what actually happens
   - Cascading failures from root bugs
   - Why the design is actually good, but implementation has bugs

4. **LAZY_LOADING_QUICK_REFERENCE.md**
   - Quick lookup tables
   - Signal → Handler → Update → Refresh chain
   - State dictionary structures
   - Bug locations cheat sheet
   - Debugging checklist

---

## TL;DR Summary

### The Architecture (Good Design)
```
Tier 1: User edits table → stores in _lazy_builtin_views
   ↓ (handler called)
Tier 2: _lazy_builtin_views read into _panel_modality_map (via _current_layout_spec)
   ↓ (sync point)
Tier 3: _panel_modality_map used in _refresh_image() to render
   ↓ (should use spec)
Canvas displays correct result
```

### The Reality (Current Bugs)
```
Tier 1: User edits table → stores in _lazy_builtin_views ✓
   ↓
Tier 2: _panel_modality_map updated ✓ (usually)
   ↓
Tier 3: _refresh_image() IGNORES Tier 2! ✗
        ├─ Hardcodes: prim = self.primary_image
        ├─ Always renders from primary image
        ├─ Ignores: _panel_modality_map[key].image_id
        └─ Result: Canvas shows WRONG image
   ↓
Canvas displays WRONG result ✗
```

---

## Root Causes Identified

### Issue #1: Mean/Std Projection Source Doesn't Change (🔴 CRITICAL)
**File**: `src/phage_annotator/ui_qt/rendering/renderer.py`
**Lines**: 198, 237, 239
**Cause**: Hardcoded `prim = self.primary_image` used instead of looking up `_panel_modality_map["mean"].image_id`

```python
# Current (WRONG):
prim = self.primary_image
mean_data, _ = self._get_projection(prim, "mean")  # Always uses primary image

# Should be:
mean_spec = self._panel_modality_map.get("mean")
mean_image = self.images[mean_spec.image_id] if mean_spec else prim
mean_data, _ = self._get_projection(mean_image, "mean")  # Uses correct image
```

**Impact**: Even if user sets mean projection source to Image 2, canvas still shows Image 1's mean

---

### Issue #2: Row 2 Name Change Doesn't Appear on Canvas (🟠 HIGH)
**File**: Likely `src/phage_annotator/ui_qt/rendering/roi_crop.py` (80-230) or renderer.py
**Cause**: Either:
  - _lazy_builtin_views name not read into _panel_modality_map.display_name, OR
  - Canvas title hardcoded instead of reading from spec

```python
# Name is stored here:
self._lazy_builtin_views["mean"]["name"] = "Custom Mean Name"

# Should be applied here (in _current_layout_spec):
spec.display_name = str(cfg["name"]).strip()

# And used here (in renderer):
render_title(spec.display_name)  # Should show custom name
```

**Impact**: User changes "Mean" to "Mean of Image 2" but canvas still shows "Mean Projection"

---

### Issue #3: Contrast/Zoom/Pan Don't Update for Projections (🟠 HIGH)
**File**: `src/phage_annotator/ui_qt/rendering/renderer.py` (Lines 320-350)
**Cause**: Same as Issue #1 - uses primary image's display settings instead of source image's

```python
# Current (WRONG):
mean_mapping = self._get_display_mapping(prim.id, "mean", mean_data)
# Gets contrast for primary image, not source image

# Should be:
mean_image = self.images[_panel_modality_map["mean"].image_id]
mean_mapping = self._get_display_mapping(mean_image.id, "mean", mean_data)
```

**Impact**: Projection's contrast/colormap doesn't match the image being displayed

---

### Issue #4: No Canvas Refresh Without Auto-Update (🟡 MEDIUM)
**File**: `src/phage_annotator/ui_qt/utils/ui_extra.py` (Lines 2176-2243)
**Cause**: Handlers only call `_refresh_image()` if auto-update checkbox is enabled

```python
if self.lazy_auto_update_chk.isChecked():
    self._apply_lazy_pending_updates()  # Refreshes canvas
# ELSE: Nothing happens!
```

**Impact**: User changes projection source, but if auto-update is OFF, canvas doesn't update until "Update Canvas" button is clicked

**Note**: This might be intentional design. Users must click the blue "Update Canvas" button.

---

### Issue #5: Zoom/Pan Buttons Inactive (🟡 MEDIUM)
**File**: Possibly `src/phage_annotator/ui_qt/widgets/modality_canvas.py` or `main_window.py`
**Cause**: Matplotlib interactive tools might not be enabled, or not wired to custom modality axes

**Impact**: User can't zoom/pan on the canvas interactive tools

**Note**: Zoom slider works. This might be about the Matplotlib toolbar zoom/pan buttons.

---

## The Three-Dictionary Problem

The code manages the same information in THREE places that can get out of sync:

```python
# Dictionary 1: User's pending changes (what they edited)
self._lazy_builtin_views = {
    "mean": {
        "image_id": 2,      # User wants mean from Image 2
        "name": "Custom Mean",
        "projection": "mean"
    }
}

# Dictionary 2: Current canvas layout (what should be rendered)
self._panel_modality_map = {
    "mean": ModalitySpec(
        image_id=2,         # Should match Dict 1
        display_name="Custom Mean",
        projection_type=ProjectionType.MEAN,
        ...
    )
}

# Dictionary 3: What gets rendered (actual code in _refresh_image)
# Currently hardcodes:
prim = self.primary_image  # Ignores Dicts 1 & 2!
mean_data = self._get_projection(prim, "mean")  # Uses Image 1, not 2
```

**The Fix**: Make Dictionary 3 consistent - always read from Dictionary 2 in renderer.py

---

## Signal Flow Example

### When User Changes Mean Projection Source from Image 1 → Image 2:

1. **User Action**: Clicks combo box in Row 2, Column 3 (source column), selects Image 2
   
2. **Signal**: `currentIndexChanged(2)` signal emitted from QComboBox
   
3. **Handler Called**: `_on_lazy_builtin_source_changed("mean", image_id=2)` (line 2216)
   - Updates: `_lazy_builtin_views["mean"]["image_id"] = 2` ✓
   - Checks: Is auto-update enabled?
     - **YES**: Calls `_apply_lazy_pending_updates()` which calls `_refresh_image()` ✓
     - **NO**: Enables blue "Update Canvas" button, waits for user click
   
4. **Sync Point**: `_current_layout_spec()` is called (roi_crop.py:80)
   - Reads: `_lazy_builtin_views["mean"]["image_id"]` = 2
   - Updates: `_panel_modality_map["mean"].image_id = 2` ✓ (should work)
   
5. **Rendering**: `_refresh_image()` should render:
   - Get image: `image = self.images[_panel_modality_map["mean"].image_id]` = Image 2
   - Compute projection: `mean_data = self._get_projection(image, "mean")` from Image 2 ✓
   - **CURRENTLY**: Uses `prim` (Image 1) instead ✗
   
6. **Result**: 
   - **Expected**: Canvas shows Image 2's mean projection ✓
   - **Actual**: Canvas shows Image 1's mean projection ✗

---

## Why Row 1 (Support) Works But Row 2+ Doesn't

The handling is DIFFERENT for regular modalities vs. builtin views:

```python
# For Row 1 (Support):
class: Regular modality (idx=1)
handler: _on_lazy_modality_item_changed() → calls manager.rename_modality()
works: YES, because manager modalities have their own display_name attribute

# For Row 2 (Mean):
class: Builtin view (idx=-101)
handler: _on_lazy_modality_item_changed() → stores in _lazy_builtin_views dict
question: Does _current_layout_spec() read it back and update spec.display_name?
works: UNCLEAR - probably not, or canvas title is hardcoded
```

Row 2 name change might work on the table (you see it update) but the CANVAS title doesn't change.

---

## Design vs. Implementation

The **design is actually very clean**:
- Store pending changes in Dict 1
- Sync into Dict 2 at one point (_current_layout_spec)
- Use Dict 2 to render in Dict 3

**The bugs** are all about Dict 3 (rendering) not using Dict 2 (the spec) correctly:
- Hardcodes primary image instead of looking up in spec
- Ignores display settings from spec
- Ignores display name from spec
- Doesn't handle builtin projections consistently

**The fix**: Make renderer.py consistent - always use _panel_modality_map["key"] spec

---

## What The Modality Canvas Manager Does

There's also `src/phage_annotator/ui_qt/widgets/modality_canvas.py` which manages rendering multiple modalities in a grid layout. This is SEPARATE from the mean/std projections bug.

Custom modalities (Modality 3+) actually seem to work correctly because they use the spec consistently. So the bug is specific to how the "base" panels (frame, support, mean, std) are handled.

---

## Files to Read (In Order of Importance)

1. **LAZY_LOADING_ROOT_CAUSE_ANALYSIS.md** - Start here for overview
2. **LAZY_LOADING_DETAILED_EXPLANATION.md** - Deep dive into each system
3. **LAZY_LOADING_QUICK_REFERENCE.md** - Quick lookup during fixing
4. **LAZY_LOADING_FLOW_DIAGRAMS.md** - Visual reference

---

## Key Code Locations

| Task | File | Line | What To Look For |
|------|------|------|------------------|
| See how handlers work | ui_extra.py | 2086-2243 | Signal handlers call _refresh_image() |
| See where sync happens | roi_crop.py | 80-230 | _current_layout_spec() updates _panel_modality_map |
| See the bug | renderer.py | 198-350 | Hardcoded `prim` and `supp` instead of reading from spec |
| See state storage | main_window.py | 198 | Where _panel_modality_map is initialized |

---

## Summary

**Without seeing any code changes, you now understand:**

1. ✅ How lazy loading row changes are detected (signals → handlers)
2. ✅ Why Row 1 works but Row 2 doesn't (different handling paths)
3. ✅ Why projections don't change images (hardcoded primary image)
4. ✅ Why contrast/zoom/pan don't update (wrong image's settings)
5. ✅ Why zoom/pan buttons might be inactive (unclear, needs checking)
6. ✅ Root cause of each bug and which files to fix

**Ready to move to the FIX phase whenever you are!**

---

**All documentation files have been created in the workspace root for your reference.**
