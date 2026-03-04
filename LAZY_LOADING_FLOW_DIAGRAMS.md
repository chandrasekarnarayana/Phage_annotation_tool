# LAZY LOADING FLOW DIAGRAMS

## DIAGRAM 1: How Row Changes Flow to Canvas Refresh

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAZY MODALITY TABLE                          │
│  Row 0: "Frame" [name] [source dropdown] [projection dropdown]  │
│  Row 1: "Support" [name] [source dropdown] [projection dropdown]│
│  Row 2: "Mean" [name] [source dropdown] [projection dropdown]   │
│  Row 3: "Std" [name] [source dropdown] [projection dropdown]    │
│  Row 4+: "Modality 3" ...                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (User changes column)
                    
        ┌─────────────────────────────────────────────┐
        │        SIGNAL CONNECTED TO COLUMN:          │
        ├─────────────────────────────────────────────┤
        │ Col 2 (Name):      _on_lazy_modality_item_  │
        │                    changed()                │
        │                                             │
        │ Col 3 (Source):    _on_lazy_modality_      │
        │                    source_changed()        │
        │                                             │
        │ Col 4 (Projection):_on_lazy_modality_      │
        │                    projection_changed()    │
        └─────────────────────────────────────────────┘
                              ↓
        ┌──────────────────────────────────────────┐
        │  UPDATE INTERNAL STATE DICTIONARIES       │
        ├──────────────────────────────────────────┤
        │ self._lazy_builtin_views["mean"] = {     │
        │     "name": "New Name",                  │
        │     "image_id": 2,                       │
        │     "projection": "mean"                 │
        │ }                                        │
        │                                          │
        │ OR: manager.rename_modality(idx, name)  │
        │ OR: modality.image_id = new_id          │
        │ OR: modality.projection_type = new_proj │
        └──────────────────────────────────────────┘
                              ↓
        ┌──────────────────────────────────────────┐
        │  CHECK: AUTO-UPDATE ENABLED?             │
        └──────────────────────────────────────────┘
                    ↙                            ↘
              YES ✓                           NO ✗
                ↓                               ↓
         ┌──────────────┐            ┌──────────────────┐
         │ Call:        │            │ Enable           │
         │ _apply_lazy_ │            │ "Update Canvas"  │
         │ pending_     │            │ button (blue)    │
         │ updates()    │            │                  │
         └──────────────┘            │ User must click  │
                ↓                     │ button to apply  │
         ┌──────────────┐            └──────────────────┘
         │ Calls:       │                     ↓
         │ _refresh_    │            ┌──────────────────┐
         │ image()      │            │ On button click: │
         └──────────────┘            │ _apply_lazy_pending
                ↓                    │ _updates()       │
         CANVAS UPDATES ✓            └──────────────────┘
                                             ↓
                                     CANVAS UPDATES ✓
```

---

## DIAGRAM 2: The Problem with Mean/Std Projection Source Changes

```
┌───────────────────────────────────────────────────────────────────────┐
│                     USER CHANGES PROJECTION SOURCE                    │
│                                                                       │
│  User clicks "Mean" projection's SOURCE dropdown: Image 1 → Image 2  │
└───────────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────┐
│  _on_lazy_builtin_source_changed("mean", image_id=2)            │
│                                                                  │
│  This updates:                                                   │
│  self._lazy_builtin_views["mean"]["image_id"] = 2              │
│                                                                  │
│  (or if auto-update: triggers _apply_lazy_pending_updates())   │
└──────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────┐
│  _refresh_image() is called (eventually)                         │
│                                                                  │
│  Inside: _current_layout_spec() is called to rebuild             │
│  the _panel_modality_map with new settings:                      │
│                                                                  │
│  mean_spec = _panel_modality_map["mean"]                         │
│  mean_spec.image_id = 2  ← UPDATED ✓                            │
└──────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────┐
│  NOW: _refresh_image() renders the mean projection               │
│                                                                  │
│  ⚠️  PROBLEM: The code does THIS:                               │
│  ─────────────────────────────────────────────────────           │
│                                                                  │
│  prim = self.primary_image  # Image 1 always!                   │
│  mean_data, mean_ready = self._get_projection(prim, "mean")    │
│                           ↑                                      │
│                      Uses Image 1, NOT Image 2!                │
│                                                                  │
│  ✓  SHOULD BE:                                                  │
│  ──────────────                                                 │
│                                                                  │
│  mean_spec = self._panel_modality_map["mean"]                   │
│  mean_image = self.images[mean_spec.image_id]  # Image 2 ✓    │
│  mean_data = self._get_projection(mean_image, "mean")          │
└──────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────┐
│  RESULT:                                                         │
│                                                                  │
│  Canvas shows WRONG projection!                                 │
│  • Displays Image 1's projection instead of Image 2's           │
│  • Contrast doesn't update (uses Image 1's settings)           │
│  • Zoom/pan don't work right (Image 1's zoom values)           │
│                                                                  │
│  Why? Because the code hardcoded self.primary_image             │
│  instead of reading from _panel_modality_map                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## DIAGRAM 3: The State/Dictionary Confusion

```
┌─────────────────────────────────────────────────────────────────┐
│  User changes "Mean" projection's source: Image 1 → Image 2     │
└─────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────┐
│  TWO DICTIONARIES MUST STAY IN SYNC:                             │
│                                                                  │
│  1. self._lazy_builtin_views  (user's pending changes)          │
│     ├─ "mean": {                                                │
│     │  ├─ "name": "Mean Projection"                             │
│     │  ├─ "image_id": 2  ← USER CHANGED THIS                  │
│     │  └─ "projection": "mean"                                  │
│     │                                                            │
│     ├─ "std": {                                                 │
│     │  ├─ "name": "Std Projection"                              │
│     │  ├─ "image_id": 1                                         │
│     │  └─ "projection": "std"                                   │
│                                                                  │
│  2. self._panel_modality_map  (what's rendered on canvas)      │
│     ├─ "mean": ModalitySpec(                                    │
│     │  ├─ idx: -101                                             │
│     │  ├─ image_id: 2  ← SHOULD BE UPDATED                    │
│     │  ├─ display_name: "Mean Projection"                       │
│     │  └─ projection_type: ProjectionType.MEAN                  │
│     │                                                            │
│     ├─ "std": ModalitySpec(                                     │
│     │  ├─ idx: -103                                             │
│     │  ├─ image_id: 1                                           │
│     │  ├─ display_name: "Std Projection"                        │
│     │  └─ projection_type: ProjectionType.STD                   │
└──────────────────────────────────────────────────────────────────┘
                                  ↓
                    ┌──────────────────────────────┐
                    │  SYNC POINT:                 │
                    │  _current_layout_spec()      │
                    │                              │
                    │  This reads from _lazy_      │
                    │  builtin_views and updates   │
                    │  _panel_modality_map         │
                    │                              │
                    │  IF this works, the map      │
                    │  should have image_id: 2    │
                    └──────────────────────────────┘
                                  ↓
                    ┌──────────────────────────────┐
                    │  PROBLEM:                    │
                    │                              │
                    │  _panel_modality_map might   │
                    │  have the right image_id,   │
                    │  BUT _refresh_image()        │
                    │  doesn't USE the map!        │
                    │                              │
                    │  It hardcodes:               │
                    │  prim = self.primary_image  │
                    │  (ignores the map)           │
                    └──────────────────────────────┘
```

---

## DIAGRAM 4: Why Row 1 Works But Row 2 Doesn't

```
┌──────────────────────────────────────┐
│  ROW TYPES AND HOW THEY'RE HANDLED    │
├──────────────────────────────────────┤
│                                      │
│  Row 0: "Frame"                      │
│  └─ Modality idx: 0 (primary)       │
│     └─ Handler path: MODALITY        │
│        └─ Updates: manager.rename()  │
│           Calls: _refresh_image()    │
│           WORKS ✓                    │
│                                      │
│  Row 1: "Support"                    │
│  └─ Modality idx: 1 (secondary)      │
│     └─ Handler path: MODALITY        │
│        └─ Updates: manager.rename()  │
│           Calls: _refresh_image()    │
│           WORKS ✓                    │
│                                      │
│  Row 2: "Mean"                       │
│  └─ Builtin key: "builtin:mean"      │
│     └─ Handler path: BUILTIN         │
│        └─ Updates: _lazy_builtin_    │
│             views["mean"]["name"]    │
│           Calls: _refresh_image()    │
│           SHOULD WORK but...         │
│           Panel title NOT updated    │
│           WHY? ⚠️                     │
│                                      │
│  Row 3: "Std"                        │
│  └─ Builtin key: "builtin:std"       │
│     └─ Handler path: BUILTIN         │
│        └─ Updates: _lazy_builtin_    │
│             views["std"]["name"]     │
│           Calls: _refresh_image()    │
│           SHOULD WORK but...         │
│           Panel title NOT updated    │
│           WHY? ⚠️                     │
└──────────────────────────────────────┘

POSSIBLE BUGS:
1. _current_layout_spec() reads _lazy_builtin_views
   BUT doesn't apply the custom name?
   
2. Canvas title is rendered elsewhere
   (not in _refresh_image()) and NOT
   updated when custom names change?
   
3. The title update happens in the
   modality_canvas.py or renderer.py
   but uses hardcoded default names
   instead of reading from spec?
```

---

## DIAGRAM 5: The Projection Rendering Flow (Current vs Correct)

```
CURRENT (BUGGY):
════════════════════════════════════════════════════════════════

def _refresh_image(self):
    prim = self.primary_image           # Image 1
    supp = self.support_image           # Image 2
    
    # Main panels (always use primary/support hardcoded)
    slice_data = self._slice_data(prim)
    mean_data, _ = self._get_projection(prim, "mean")  # ← Image 1
    std_data, _ = self._get_projection(prim, "std")    # ← Image 1
    support_slice = self._slice_data(supp)
    
    # Custom modality panels
    if self._panel_modality_map:
        for key, modality in self._panel_modality_map.items():
            img = self.images[modality.image_id]        # ✓ Uses spec
            # Correctly uses the modality's image_id
    
    # BUG: Main panels don't use _panel_modality_map!
    # Even if user changed mean source to Image 2,
    # we still compute it from prim (Image 1)


CORRECT (FIXED):
════════════════════════════════════════════════════════════════

def _refresh_image(self):
    prim = self.primary_image           # Default image
    supp = self.support_image           # Default image
    
    # Main panels (READ from _panel_modality_map)
    frame_spec = self._panel_modality_map.get("frame")
    frame_image = self.images[frame_spec.image_id] if frame_spec else prim
    slice_data = self._slice_data(frame_image)
    
    mean_spec = self._panel_modality_map.get("mean")
    mean_image = self.images[mean_spec.image_id] if mean_spec else prim
    mean_data, _ = self._get_projection(mean_image, "mean")  # ✓ Image 2
    
    std_spec = self._panel_modality_map.get("std")
    std_image = self.images[std_spec.image_id] if std_spec else prim
    std_data, _ = self._get_projection(std_image, "std")    # ✓ Image 2
    
    support_spec = self._panel_modality_map.get("support")
    support_image = self.images[support_spec.image_id] if support_spec else supp
    support_slice = self._slice_data(support_image)
    
    # Custom modality panels
    if self._panel_modality_map:
        for key, modality in self._panel_modality_map.items():
            img = self.images[modality.image_id]        # ✓ Consistent
    
    # FIX: All panels now read from _panel_modality_map!
```

---

## DIAGRAM 6: Canvas Refresh Call Stack

```
USER ACTION
    ↓
Handler Function Called:
    ├─ _on_lazy_modality_item_changed()
    ├─ _on_lazy_modality_source_changed()
    └─ _on_lazy_modality_projection_changed()
    
    ↓
    
Update Internal State:
    ├─ self._lazy_builtin_views["mean"] = {...}
    ├─ modality.image_id = new_id
    ├─ modality.projection_type = new_type
    └─ modality.display_name = new_name
    
    ↓
    
IF auto-update enabled:
    └─ _apply_lazy_pending_updates()
       ├─ _refresh_lazy_modality_table()    ← Rebuild table UI
       └─ _refresh_image()
    
ELSE:
    └─ Enable "Update Canvas" button
       Wait for user click
       └─ _apply_lazy_pending_updates()
          ├─ _refresh_lazy_modality_table()
          └─ _refresh_image()
    
    ↓
    
Inside _refresh_image():
    ├─ _current_layout_spec()              ← BUILD _panel_modality_map
    │  ├─ Read modality manager
    │  ├─ Read _lazy_builtin_views         ← Should have new values
    │  ├─ Build _panel_modality_map        ← Should have new image_ids
    │  └─ Return {"order": [...], "panel_visibility": {...}}
    │
    ├─ _rebuild_figure_layout(layout_spec) ← Update matplotlib figure
    │
    ├─ For each panel (frame, support, mean, std):
    │  ├─ Get data                         ← BUG: Uses hardcoded prim
    │  ├─ Compute normalization
    │  ├─ Apply colormap
    │  └─ Update matplotlib artist
    │
    ├─ renderer.update_images(ctx)         ← Render to canvas
    ├─ renderer.update_overlays(ctx)
    │
    └─ canvas.draw_idle()                  ← Actually display

    ↓
    
CANVAS UPDATES ✓ (but with wrong images for mean/std)
```

---

**These diagrams show exactly where the bugs are and why things don't work as expected.**
