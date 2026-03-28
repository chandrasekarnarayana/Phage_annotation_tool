# Where to Add Missing Logging for Mean Projection Debugging

## 🎯 The Problem Flow

```
[LAZY_LOADER] projection_changed ✅ LOGGED (line 2172 in ui_extra.py)
    ↓
[DATA] Update modality.projection_type to MEAN (line 2165)
    ↓ ❌ NOT LOGGED - Need to add here
[DATA] Compute mean projection from stack
    ↓ ❌ NOT LOGGED - Need to add here  
[RENDER] Queue canvas refresh (line 2167)
    ↓ 
[RENDER] Flush refresh request (line 2168)
    ↓ ❌ NOT LOGGED - Need to add here
[CANVAS] Actually render to screen
    ↓ ??? Unknown result - Can't see if it worked!
```

---

## 🔧 Exact Code Locations to Modify

### **Location 1: Eliminate View State Spam**

**File**: [src/phage_annotator/session/signal_hub.py](src/phage_annotator/session/signal_hub.py#L160)  
**Line**: ~160  
**Current Code**:
```python
logger = _get_action_logger()
if logger and change_type:
    logger.log_action(
        "view_state_changed",
        details={
            "change_type": change_type,
            "t_index": t_index,
            "z_index": z_index,
            "roi_rect": str(roi_rect) if roi_rect else None,
            "crop_rect": str(crop_rect) if crop_rect else None,
        }
    )
```

**Problem**: Logs even when all index/rect parameters are None (initialization spam)  
**Fix**: Add conditional check:
```python
logger = _get_action_logger()
if logger and change_type:
    # SKIP logging if nothing actually changed (avoid spam during init)
    has_changes = any(x is not None for x in [t_index, z_index, roi_rect, crop_rect])
    if has_changes:
        logger.log_action(
            "view_state_changed",
            details={
                "change_type": change_type,
                "t_index": t_index,
                "z_index": z_index,
                "roi_rect": str(roi_rect) if roi_rect else None,
                "crop_rect": str(crop_rect) if crop_rect else None,
            }
        )
```

**Expected Result**: Reduces log from 5,194 → ~3,500 lines (-31%)

---

### **Location 2: Log Projection Computation** ✅ CRITICAL FOR DEBUGGING

**File**: [src/phage_annotator/ui_qt/utils/ui_extra.py](src/phage_annotator/ui_qt/utils/ui_extra.py#L2165)  
**Line**: ~2165  
**Current Code**:
```python
old_projection = str(getattr(modality.projection_type, "value", "raw"))
try:
    modality.projection_type = ProjectionType(str(projection_key).strip().lower())
except Exception:
    modality.projection_type = ProjectionType.RAW
```

**Need to Add**: Log the result of projection computation  
**Suggested Fix**:
```python
old_projection = str(getattr(modality.projection_type, "value", "raw"))
try:
    modality.projection_type = ProjectionType(str(projection_key).strip().lower())
    logger = get_action_logger()
    logger.log_action(
        "projection_computation_started",
        panel="lazy_loader",
        details={
            "modality_idx": modality_idx,
            "old_projection": old_projection,
            "new_projection": projection_key
        }
    )
except Exception as e:
    modality.projection_type = ProjectionType.RAW
    logger = get_action_logger()
    logger.log_action(
        "projection_computation_failed",
        panel="lazy_loader",
        details={
            "modality_idx": modality_idx,
            "requested_projection": projection_key,
            "error": str(e)
        }
    )
    raise
```

**Why This Matters**: If projection computation is failing, this will show it!

---

### **Location 3: Log Canvas Refresh Request & Execution** ✅ CRITICAL FOR DEBUGGING

**File**: [src/phage_annotator/ui_qt/utils/ui_extra.py](src/phage_annotator/ui_qt/utils/ui_extra.py#L2166-2168)  
**Lines**: ~2166-2168  
**Current Code**:
```python
self._queue_lazy_panel_auto_contrast(self._panel_key_for_modality_idx(int(modality_idx)))
self._request_lazy_canvas_refresh("lazy-projection-change", refresh_table=False)
self._flush_lazy_canvas_refresh()
```

**Need to Add**: Log these refresh operations  
**Suggested Fix**:
```python
self._queue_lazy_panel_auto_contrast(self._panel_key_for_modality_idx(int(modality_idx)))

# Log canvas refresh request
logger = get_action_logger()
logger.log_action(
    "canvas_refresh_requested",
    panel="lazy_loader",
    details={
        "modality_idx": modality_idx,
        "reason": "projection_changed",
        "auto_contrast": True
    }
)

self._request_lazy_canvas_refresh("lazy-projection-change", refresh_table=False)

try:
    self._flush_lazy_canvas_refresh()
    logger.log_action(
        "canvas_refresh_flushed",
        panel="lazy_loader",
        details={
            "modality_idx": modality_idx,
            "status": "success"
        }
    )
except Exception as e:
    logger.log_action(
        "canvas_refresh_flushed",
        panel="lazy_loader",
        details={
            "modality_idx": modality_idx,
            "status": "failed",
            "error": str(e)
        }
    )
    raise
```

**Why This Matters**: Shows if the canvas refresh pipeline is working!

---

## 📋 Summary of Changes Required

| Location | File | Line | Change | Impact |
|----------|------|------|--------|--------|
| **1** | signal_hub.py | ~160 | Add condition: skip if all None | -1,662 spam lines |
| **2** | ui_extra.py | ~2165 | Log projection_computation_started/failed | Detect computation errors |
| **3** | ui_extra.py | ~2166-2168 | Log canvas_refresh_requested/flushed | Detect render pipeline breaks |

---

## 🧪 How to Debug After Changes

**After adding these three logging points**:

```bash
# Move/kill old log
mv phage_annotator_actions.jsonl phage_annotator_actions.jsonl.old

# Run application again and change projection to mean
# (GUI should show it, or we'll see why it doesn't)

# Then examine:
jq 'select(.panel == "lazy_loader")' phage_annotator_actions.jsonl
```

**You should see**:
```
{
  "timestamp": 1711612742.1234,
  "action": "projection_changed",
  "panel": "lazy_loader",
  "details": {"modality_idx": 1, "old_projection": "raw", "new_projection": "mean"},
  ...
}
{
  "action": "projection_computation_started",  ← NEW!
  ...
}
{
  "action": "canvas_refresh_requested",  ← NEW!
  ...
}
{
  "action": "canvas_refresh_flushed",  ← NEW!
  ...
}
```

**If any step is missing or shows error → You found the bug!**

---

## ✅ Files to Modify (Summary)

1. **[signal_hub.py](src/phage_annotator/session/signal_hub.py)**
   - Line ~160: Add condition `if has_changes:`

2. **[ui_extra.py](src/phage_annotator/ui_qt/utils/ui_extra.py)**
   - Line ~2165: Add projection computation logging
   - Line ~2166-2168: Add canvas refresh logging

All other files are already logging appropriately.

---

## 🎯 Quick Test After Changes

1. **Clear old log**:
   ```bash
   rm -f phage_annotator_actions.jsonl phage_annotator.log
   ```

2. **Start GUI and load images**

3. **Change projection to mean**

4. **Check logs**:
   ```bash
   # Count lines (should be ~1500-2000, not 5000+)
   wc -l phage_annotator_actions.jsonl
   
   # See projection change flow
   jq 'select(.panel == "lazy_loader" or (.action | contains("projection")) or (.action | contains("canvas")))' phage_annotator_actions.jsonl | jq .action
   ```

5. **Expected output**:
   ```
   "projection_changed"
   "projection_computation_started"  ← If added
   "canvas_refresh_requested"        ← If added
   "canvas_refresh_flushed"          ← If added
   ```

If you see all four → mean projection should be visible!  
If any is missing → you found the break point!
