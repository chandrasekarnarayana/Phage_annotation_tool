# DETAILED EXPLANATION: Lazy Loading Row Changes, Projections, and Canvas Refresh Issues

## OVERVIEW: How Changes Flow from Lazy Loading Table → Canvas

The lazy loading system has multiple "layers" that must all sync correctly:
1. **User modifies table row** (name, source image, projection type)
2. **Row change detected** (signal connected to handler)
3. **State updated** (internal dictionaries modified)
4. **Canvas layout rebuilt** (new panel_modality_map created)
5. **Canvas rendered** (images fetched and displayed)

Each step can break, which is likely what's happening with row 2 and projections.

---

## PART 1: HOW ROW CHANGES ARE DETECTED AND TRIGGER CANVAS REFRESH

### 1.1 ROW CHANGE DETECTION MECHANISM

**File**: `src/phage_annotator/ui_qt/utils/ui_extra.py:1560-1750`

When the lazy modality table is created/refreshed, this happens:

```python
def _refresh_lazy_modality_table(self) -> None:
    """Populate lazy-loading modality/view table."""
    table = getattr(self, "lazy_modality_table", None)
    
    # For EACH ROW (modality, mean, std, etc):
    name_item = QtWidgets.QTableWidgetItem(str(modality.display_name))
    name_item.setData(QtCore.Qt.ItemDataRole.UserRole, int(modality.idx))  # Store modality ID
    table.setItem(row, 2, name_item)  # Column 2 = NAME
    
    source_combo = QtWidgets.QComboBox(table)
    source_combo.currentIndexChanged.connect(
        lambda _i, combo=source_combo: self._on_lazy_modality_source_changed(...)
    )
    table.setCellWidget(row, 3, source_combo)  # Column 3 = SOURCE (dropdown)
    
    view_combo = QtWidgets.QComboBox(table)
    view_combo.currentIndexChanged.connect(
        lambda _i, combo=view_combo: self._on_lazy_modality_projection_changed(...)
    )
    table.setCellWidget(row, 4, view_combo)  # Column 4 = PROJECTION (dropdown)
```

**KEY CONNECTIONS** (Where signals are connected):

| Column | Widget | Signal Handler | What Changes |
|--------|--------|----------------|--------------|
| 2 | QTableWidgetItem (Name) | `_on_lazy_modality_item_changed()` | Display name, sync group |
| 3 | QComboBox (Source) | `_on_lazy_modality_source_changed()` | `image_id` (which image to display) |
| 4 | QComboBox (Projection) | `_on_lazy_modality_projection_changed()` | `projection_type` (raw/mean/std/etc) |

---

### 1.2 WHAT HAPPENS WHEN USER CHANGES A ROW

#### **SCENARIO A: User changes NAME (Column 2)**

**Handler**: `_on_lazy_modality_item_changed()` (line 2086)

```python
def _on_lazy_modality_item_changed(self, item) -> None:
    """Handle lazy-table inline rename and propagate to canvas titles."""
    
    col = int(item.column())
    if col == 2:  # NAME COLUMN
        new_name = str(item.text()).strip()
        manager.rename_modality(modality_idx, new_name)  # Update modality name
        
        btn = getattr(self, "lazy_apply_btn", None)
        if btn is not None:
            btn.setEnabled(True)  # Mark "Update Canvas" button as pending
        
        # AUTO-APPLY? (if auto-update checkbox is checked)
        if self.lazy_auto_update_chk.isChecked():
            self._apply_lazy_pending_updates()  # ← CANVAS REFRESHES IMMEDIATELY
        else:
            self._refresh_annotation_view_controls()
            self._refresh_image()  # ← CANVAS REFRESHES ANYWAY
```

**Flow**: NAME CHANGE → `_refresh_image()` is called → Canvas updates ✓

---

#### **SCENARIO B: User changes SOURCE (Column 3 - the dropdown)**

**Handler**: `_on_lazy_modality_source_changed()` (line 2176)

```python
def _on_lazy_modality_source_changed(self, modality_idx: int, image_id: int) -> None:
    """Update which image this modality displays."""
    
    manager = ensure_modality_system(self.controller.session_state)
    modality = manager.get_modality(int(modality_idx))
    modality.image_id = int(image_id)  # ← CHANGE THE SOURCE IMAGE
    
    btn = getattr(self, "lazy_apply_btn", None)
    if btn is not None:
        btn.setEnabled(True)  # Mark "Update Canvas" button as pending
    
    # AUTO-APPLY?
    if self.lazy_auto_update_chk.isChecked():
        self._apply_lazy_pending_updates()  # ← CANVAS REFRESHES
    # IF NOT AUTO-UPDATE: ⚠️ NOTHING HAPPENS! User must click "Update Canvas"
```

**Flow**: SOURCE CHANGE → If Auto-Update: `_apply_lazy_pending_updates()` → `_refresh_image()` ✓
**IF NO AUTO-UPDATE**: Change only stored, canvas NOT refreshed ⚠️

---

#### **SCENARIO C: User changes PROJECTION TYPE (Column 4 - mean/std/max/etc)**

**Handler**: `_on_lazy_modality_projection_changed()` (line 2189)

```python
def _on_lazy_modality_projection_changed(self, modality_idx: int, projection_key: str) -> None:
    """Update projection type for modality (raw vs mean vs std, etc)."""
    
    manager = ensure_modality_system(self.controller.session_state)
    modality = manager.get_modality(int(modality_idx))
    modality.projection_type = ProjectionType(projection_key)  # ← CHANGE PROJECTION
    
    btn = getattr(self, "lazy_apply_btn", None)
    if btn is not None:
        btn.setEnabled(True)  # Mark "Update Canvas" button as pending
    
    # AUTO-APPLY?
    if self.lazy_auto_update_chk.isChecked():
        self._apply_lazy_pending_updates()  # ← CANVAS REFRESHES
    # IF NOT AUTO-UPDATE: ⚠️ NOTHING HAPPENS! User must click "Update Canvas"
```

**Flow**: PROJECTION CHANGE → If Auto-Update: `_apply_lazy_pending_updates()` → `_refresh_image()` ✓
**IF NO AUTO-UPDATE**: Change only stored, canvas NOT refreshed ⚠️

---

### 1.3 THE "UPDATE CANVAS" BUTTON

When changes are made WITHOUT auto-update enabled, the "Update Canvas" button becomes enabled (blue):

```python
def _apply_lazy_pending_updates(self) -> None:
    """Apply ALL pending changes at once."""
    self._refresh_lazy_modality_table()  # Rebuild table display
    self._refresh_image()                 # Rebuild canvas
    
    btn = getattr(self, "lazy_apply_btn", None)
    if btn is not None:
        btn.setEnabled(False)  # Button grays out after apply
```

**KEY POINT**: If the user has NOT clicked "Update Canvas" and auto-update is OFF, the canvas will NOT change.

---

## PART 2: WHY ROW 1 WORKS BUT ROW 2 DOESN'T CHANGE NAME

### 2.1 ROW NUMBERING AND INDEX CONFUSION

The lazy table has this structure:

| Row | Type | Panel Key | Modality Index | What it represents |
|-----|------|-----------|---------------|--------------------|
| 0 | Frame | "frame" | 0 | Primary modality (1st image) |
| 1 | Support | "support" | 1 | Secondary modality (2nd image) |
| 2 | Mean Projection | "mean" | -101 (builtin) | Mean of 1st image |
| 3 | Std Projection | "std" | -103 (builtin) | Std of 1st image |
| 4+ | Modality 3+ | "modality_2", etc | 2+ | Additional user modalities |

---

### 2.2 THE NAME CHANGE BUG THEORY

When you edit the NAME in Row 2 (the Mean Projection):

```python
def _on_lazy_modality_item_changed(self, item) -> None:
    col = int(item.column())
    
    # ⚠️ BUG LOCATION: Check what type of row this is
    role_text = str(role_data)
    
    if role_text.startswith("builtin:"):
        # This is a BUILTIN row (mean/std)
        panel_key = role_text.split(":", 1)[1]
        
        # Only rename if it's mean or std
        builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
        cfg = dict(builtin.get(panel_key, {}) or {})
        cfg["name"] = str(item.text()).strip() or cfg.get("name", panel_key.title())
        builtin[panel_key] = cfg
        self._lazy_builtin_views = builtin
        
        # ✓ This path calls _refresh_image() OR _apply_lazy_pending_updates()
        if self.lazy_auto_update_chk.isChecked():
            self._apply_lazy_pending_updates()
        else:
            self._refresh_annotation_view_controls()
            self._refresh_image()
        return  # ← RETURNS HERE for builtin rows
    
    # Only reached if NOT a builtin row
    modality_idx = int(role_data)
    # ... handle regular modality rename
```

**Hypothesis**: 
- Row 1 (Support) is a regular modality (idx=1) - NAME path is: `builtin:support` → triggers refresh
- Row 2 (Mean) is builtin (idx=-101) - NAME path is: `builtin:mean` → should trigger refresh

**BUT** there might be a bug where:
1. The `_lazy_builtin_views` dict doesn't have "mean" key initially
2. OR the change is made but canvas refresh is not called
3. OR the panel_modality_map is not rebuilt to use the new name

---

### 2.3 WHERE THE NAME CHANGE ISN'T FLOWING TO CANVAS

The name gets stored here:
```python
self._lazy_builtin_views["mean"] = {"name": "New Name", "image_id": ..., "projection": ...}
```

But the canvas uses this:
```python
spec = self._panel_modality_map.get("mean")
if spec is None:
    continue
spec.display_name = str(cfg["name"]).strip()  # ← This reads from _lazy_builtin_views
```

**Problem**: The display name is only applied in `_current_layout_spec()` which builds `_panel_modality_map`. This is called from `_refresh_image()`. So IF `_refresh_image()` is called, the name should update.

**Actual bug is likely**:
- Row 2 name change handler is called ✓
- State is updated in `_lazy_builtin_views` ✓
- `_refresh_image()` is called ✓
- BUT: `_current_layout_spec()` isn't reading the updated `_lazy_builtin_views` correctly
- OR: The panel title isn't re-rendered after refresh

---

## PART 3: WHY MEAN AND STD PROJECTIONS DON'T CHANGE IMAGE

### 3.1 THE PROJECTION SYSTEM ARCHITECTURE

**File**: `src/phage_annotator/ui_qt/utils/state.py:602`

```python
def _get_projection(
    self,
    img: "LazyImage",
    kind: str,
    axis_override: Optional[str] = None,
    modality_idx: Optional[int] = None,
) -> Tuple[Optional[np.ndarray], bool]:
    """Return cached projection or LOD fallback while full-res loads."""
    
    kind_l = kind.lower()  # "mean", "std", "min", "max"
    axis = axis_override or self._projection_axis_for_image(img)
    
    # Build CACHE KEY
    key = self._projection_key(img, kind_l, axis, modality_idx=modality_idx)
    
    # Check if ALREADY CACHED
    cached = self.proj_cache.get(key)
    if cached is not None:
        return cached, True  # ✓ Return cached projection
    
    # If NOT cached, try LOD pyramid fallback
    pyramid_cached = self.proj_cache.get_pyramid(pyramid_key)
    if pyramid_cached is not None:
        self._request_projection_job(img, {kind_l}, ...)
        return pyramid_cached, False  # Return LOD version
    
    # If nothing cached, request full-res job
    self._request_projection_job(img, {kind_l}, ...)
    return None, False  # Return None, will show "Computing..." on canvas
```

**KEY INSIGHT**: The projection is cached by `_projection_key()` which includes:
- Image ID
- Projection kind (mean/std/etc)
- Projection axis (t/z/tz)
- Modality index (optional)

If you change the SOURCE IMAGE for the "mean" projection from Image 1 → Image 2, the cache key will be different:
- OLD KEY: `(image_id=1, kind="mean", axis="tz", modality=-101)`
- NEW KEY: `(image_id=2, kind="mean", axis="tz", modality=-101)`

These are **different keys**, so the cache won't be hit, and a NEW projection will be computed. ✓

---

### 3.2 WHERE PROJECTION SOURCE CHANGES HAPPEN

**File**: `src/phage_annotator/ui_qt/utils/ui_extra.py:2231` (for BUILTIN projections)

```python
def _on_lazy_builtin_source_changed(self, panel_key: str, image_id: int) -> None:
    """Update source image for built-in mean/std panel rows."""
    
    builtin = dict(getattr(self, "_lazy_builtin_views", {}) or {})
    cfg = dict(builtin.get(str(panel_key), {}) or {})
    cfg["image_id"] = int(image_id)  # ← CHANGE SOURCE IMAGE ID
    builtin[str(panel_key)] = cfg
    self._lazy_builtin_views = builtin
    
    btn = getattr(self, "lazy_apply_btn", None)
    if btn is not None:
        btn.setEnabled(True)  # Mark "Update Canvas" button as pending
    
    # AUTO-APPLY?
    if bool(getattr(self, "lazy_auto_update_chk", None) and self.lazy_auto_update_chk.isChecked()):
        self._apply_lazy_pending_updates()  # ← CANVAS REFRESHES
```

**PROBLEM 1**: If auto-update is OFF, the change is stored but canvas doesn't refresh.

**PROBLEM 2**: When canvas DOES refresh, the new source image ID must be read and used:

```python
# In _current_layout_spec() (roi_crop.py:80+)
for key, cfg, default_projection in (
    ("mean", mean_cfg, ProjectionType.MEAN),
    ("std", std_cfg, ProjectionType.STD),
):
    spec = self._panel_modality_map.get(key)
    if spec is None:
        continue
    
    # ← THIS reads the NEW image_id from _lazy_builtin_views
    image_id = int(cfg.get("image_id", spec.image_id))
    spec.image_id = image_id  # Update the spec to use new image
```

**THEN** in `_refresh_image()` (renderer.py):

```python
mean_data, mean_ready = self._get_projection(prim, "mean")  # ← prim is PRIMARY image
```

**⚠️ HERE'S THE BUG**: The code uses `prim` (PRIMARY IMAGE) always, not the image_id from the spec!

---

### 3.3 THE ACTUAL PROJECTION RENDERING BUG

**File**: `src/phage_annotator/ui_qt/rendering/renderer.py:198`

```python
def _refresh_image(self) -> None:
    """Refresh the image display using current state."""
    
    prim = self.primary_image  # Always uses current primary image
    
    mean_data, mean_ready = self._get_projection(prim, "mean")  # ← HARDCODED TO prim
    std_data, std_ready = self._get_projection(prim, "std")     # ← HARDCODED TO prim
    
    # But should be:
    # mean_spec = self._panel_modality_map.get("mean")
    # mean_image = self.images[mean_spec.image_id]  if mean_spec else prim
    # mean_data, mean_ready = self._get_projection(mean_image, "mean")
```

**ROOT CAUSE FOUND**: The canvas ALWAYS uses the primary image for mean/std projections, regardless of what image_id is set in `_lazy_builtin_views["mean"]` or `_panel_modality_map["mean"]`.

---

### 3.4 CONTRAST AND DISPLAY SETTINGS NOT UPDATING

When you change the source image for a projection:

```python
# In _current_layout_spec()
source_modality = None
if manager is not None:
    for modality in manager.get_all_modalities():
        if int(getattr(modality, "image_id", -1)) == image_id:
            source_modality = modality
            break

# Copy display settings from source modality
spec.display_settings = _clone_settings(
    source_modality.display_settings if source_modality else spec.display_settings
)
```

**This should update** the contrast/colormap/etc settings for the projection. But if the canvas is using the wrong image (always primary), the wrong display settings are applied.

---

## PART 4: WHY ZOOM AND PAN BUTTONS DON'T WORK

### 4.1 ZOOM/PAN IN THE MATPLOTLIB TOOLBAR

The zoom/pan buttons are part of Matplotlib's standard toolbar, which is embedded in the canvas. These are **NOT custom buttons** - they're native Matplotlib interactive tools.

**Expected behavior**:
1. User clicks "Zoom" button in Matplotlib toolbar
2. User drags a rectangle on canvas
3. Canvas zooms to that rectangle

**Likely issue**: The zoom/pan tools might NOT be enabled on the canvas, or the canvas might not be in interactive mode.

**File**: Check if canvas is created with interactive=True:

```python
# In main_window.py or UI setup
self.canvas = FigureCanvasQTAgg(self.figure)
# ⚠️ If canvas.set_cursor_data(None) is called, interactive mode might be disabled
```

OR the tools might not be hooked up to the correct axes.

### 4.2 THE REAL PROBLEM: LAZY MODALITY MAP NOT UPDATED FOR CUSTOM MODALITIES

When you have custom modalities (beyond frame/support/mean/std), the zoom settings need to apply to each one separately.

**File**: `src/phage_annotator/ui_qt/controls/display.py:1300+`

```python
def _on_zoom_changed(self, value: float) -> None:
    """Handle zoom slider change for all sync-grouped panels."""
    
    # Sync zoom to all modalities in the same group
    groups = dict(getattr(self, "_lazy_modality_groups", {}) or {})
    active_group = getattr(self, "_sync_target_group", "1")
    
    # Apply zoom to all modalities in active_group
    for modality_idx, group_key in groups.items():
        if str(group_key) == str(active_group):
            modality = manager.get_modality(modality_idx)
            if modality:
                modality.display_settings.zoom = value
```

**ISSUE**: If custom modalities aren't in `_panel_modality_map` yet, or if the zoom value isn't being read correctly, the zoom won't apply.

---

## SUMMARY: WHY THINGS DON'T WORK

| Issue | Root Cause | File/Location |
|-------|-----------|---------------|
| **Row 2 name doesn't change** | Panel title not re-rendered or `_current_layout_spec()` not reading updated `_lazy_builtin_views` | `ui_extra.py:2086` or `roi_crop.py:80` |
| **Mean/Std source image doesn't change** | Canvas always uses primary image, ignoring `_lazy_builtin_views["mean"]["image_id"]` | `renderer.py:198` (hardcoded `prim` instead of looking up correct image) |
| **Contrast/zoom/pan don't change for projections** | Same root cause - wrong image is used, so wrong display settings applied | `renderer.py:198-250` (all use `prim` instead of spec.image_id) |
| **Projection doesn't update on source change** | If auto-update is OFF, `_refresh_image()` isn't called | `ui_extra.py:2231` (needs to call refresh even without auto-update) |
| **Zoom/pan buttons inactive** | Canvas might not be in interactive mode, or tools not connected to custom modality axes | `main_window.py` or `widgets/modality_canvas.py` |

---

## THE FIX ROADMAP (HIGH LEVEL - DON'T IMPLEMENT YET)

1. **For projection source changes**: 
   - In `renderer.py:198+`, when rendering mean/std, look up the actual image from `_panel_modality_map` instead of always using `prim`
   - Use `image = self.images[self._panel_modality_map["mean"].image_id]` if available

2. **For row 2 name not updating**:
   - Verify `_current_layout_spec()` is reading from `_lazy_builtin_views` correctly
   - Check if canvas title refresh is being called

3. **For contrast/zoom/pan**:
   - Same as #1 - use correct image for each panel

4. **For auto-update missing**:
   - Some handlers should trigger `_refresh_image()` even without auto-update (at least for user-initiated changes)

5. **For zoom/pan inactive**:
   - Check if matplotlib toolbar is properly initialized
   - Check if custom modality canvases have interactive tools enabled

---

## KEY TAKEAWAYS FOR UNDERSTANDING THE CODE

**Three different "image" references** are confusing:

1. `self.primary_image` - Always the "current" 1st modality being viewed
2. `self.support_image` - Always the "current" 2nd modality being viewed
3. `modality.image_id` - What IMAGE this modality should DISPLAY (might be Image 1, 2, 3, etc)
4. `spec.image_id` in `_panel_modality_map` - Same as above, but in a spec object

The canvas uses `self.primary_image` directly in many places, but it should use the correct image based on which modality is being rendered.

**Two different config stores** are also confusing:

1. `_lazy_builtin_views` dict - Stores user's pending changes to mean/std (source, projection, name)
2. `_panel_modality_map` dict - What's currently on the canvas (a ModalitySpec object per panel)

Changes in `_lazy_builtin_views` only affect canvas if `_current_layout_spec()` reads them and updates `_panel_modality_map`.

---

## FILES TO CHECK FOR FIXES

- `src/phage_annotator/ui_qt/rendering/renderer.py` (line 198-250) - Projection rendering
- `src/phage_annotator/ui_qt/rendering/roi_crop.py` (line 80-230) - Layout spec builder
- `src/phage_annotator/ui_qt/utils/ui_extra.py` (line 1560-2300) - Lazy table handlers
- `src/phage_annotator/ui_qt/controls/display.py` (line 1300+) - Zoom/contrast sync

---

**Now you understand the system. Ready to debug and fix?**
