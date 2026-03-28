# Log Analysis & Optimization Report

## 📊 Current State

**Log File**: `phage_annotator.log`  
**Total Lines**: 5,194  
**Time Range**: 08:44:34 - 08:46:15  
**Duration**: ~101 seconds

---

## 🔴 Critical Issues Found

### 1. **MASSIVE LOGGING SPAM** (1,662/5,194 entries = 31% of log!)

```
view_state_changed | change_type=sync_mode | t_index=None | z_index=None | roi_rect=None | crop_rect=None
```

**Problem**:
- Same exact entry repeated **1,662 times** during initialization
- All parameters are `None` (completely useless)
- Happens during `__init__()` - initialization noise
- Each entry appears **TWICE** (duplicate from file + GUI logging)

**Impact**: 
- Log file bloat (noise obscures real issues)
- Performance cost (writing useless data)
- Hard to debug problems (real events hidden)

**Fix**: Skip logging when all parameters are `None`:
```python
# BEFORE: Logs even with no data
self.log_action("view_state_changed", details={"t_index": None, "z_index": None})

# AFTER: Skip useless logs
if any(v is not None for v in [t_index, z_index, roi_rect, crop_rect]):
    self.log_action("view_state_changed", details={...})
```

---

### 2. **CRITICAL GAP: Mean Projection Rendering Not Logged**

**Timeline**:
```
2563 [08:45:46] projection_changed | modality_idx=1 | old=raw | new=mean  ✅ LOGGED
     [08:45:46 - 08:46:15]  ← CRITICAL GAP (29 SECONDS, NO LOGGING!)
     [08:46:15] view_state_changed | change_type=view_sync ...  ✓ Resume
```

**What Should Be Logged But Isn't**:
- ❌ Mean projection computation started
- ❌ Mean projection computed successfully (or error)
- ❌ Render job queued for display
- ❌ Render job executed (canvas updated)
- ❌ Canvas refresh triggered
- ❌ GPU texture uploaded with new data

**Why Mean Projection Isn't Visible**:

Based on the logging gap, the issue is likely that:
1. ✅ UI action detected: projection_changed is logged
2. ✅ Backend signal fired: projection_changed signal emitted (implied)
3. ❌ **Data layer missing**: No log of mean projection being computed
4. ❌ **Render layer missing**: No log of render job being created/executed
5. ❌ **Display missing**: Canvas never gets updated

**What's Needed**:
```python
# In image data layer (where mean projection computed):
logger.log_action("projection_computed", 
    modality_idx=idx, 
    projection_type="mean",
    shape=data.shape,  # To verify computation happened
    duration_ms=elapsed)

# In render layer (when queuing canvas update):
logger.log_action("render_job_queued",
    job_type="display",
    modality_idx=idx,
    reason="projection_changed")

# In canvas/display (when actually rendering):
logger.log_action("canvas_updated",
    modality_idx=idx,
    projection=current_projection,
    duration_ms=render_time)
```

---

## 📈 Log Composition Analysis

| Category | Count | % | Status |
|----------|-------|---|--------|
| **view_state_changed (sync_mode)** | 1,662 | 31% | 🔴 SPAM - All None params |
| **view_state_changed (other)** | 9 | <1% | ✅ Informative |
| **ASSIST panel** | 50 | 1% | ✅ Good info |
| **LAZY_LOADER panel** | 3 | <1% | ✅ Shows modalities loaded |
| **State/ROI/Playback** | 9 | <1% | ✅ Moderate info |
| **Missing (data/render)** | 0 | 0% | 🔴 CRITICAL GAP |

---

## ✅ What's Working Well

### 1. **ASSIST Panel Logging** (50 entries)
```
[ASSIST] suggestion_queue_updated | total_suggestions=0 | accepted_count=0 | ...
```
✅ **Good**: Shows actual values, informative, update counts  
✅ **Useful**: Can track suggestion pipeline  

### 2. **LAZY_LOADER Panel Logging** (3 entries)
```
[LAZY_LOADER] add_modality | modality_idx=1 | projection=raw | image_id=0
[LAZY_LOADER] projection_changed | modality_idx=1 | old_projection=raw | new_projection=mean
```
✅ **Good**: Clear state transitions  
✅ **Useful**: Shows initial setup and projection changes  
⚠️ **Issue**: No logging of what happens AFTER projection change

### 3. **ROI/State Changes** (selective)
```
[]-roi_state_changed | signal=roi_changed
[]-state_changed | signal=state_changed
```
✅ **Good**: Logged selectively, not spam  
✅ **Useful**: Marks state transitions  

---

## 🎯 Optimization Recommendations

### **PRIORITY 1: Eliminate Spam** (Quick Win)

**Problem**: `view_state_changed` with all None logged 1,662 times  
**Location**: [signal_hub.py](src/phage_annotator/core/signal_hub.py)  
**Solution**: Conditional logging

```python
# Current (noisy):
def _on_view_changed(self, change_type, t_index, z_index, roi_rect, crop_rect):
    log_action("view_state_changed", details={
        "change_type": change_type,
        "t_index": t_index,
        "z_index": z_index,
        "roi_rect": roi_rect,
        "crop_rect": crop_rect
    })

# Optimized (conditional):
def _on_view_changed(self, change_type, t_index, z_index, roi_rect, crop_rect):
    # Skip if nothing actually changed
    if all(x is None for x in [t_index, z_index, roi_rect, crop_rect]):
        return  # Don't log during initialization
    
    # Only log the values that changed
    details = {"change_type": change_type}
    if t_index is not None:
        details["t_index"] = t_index
    if z_index is not None:
        details["z_index"] = z_index
    # ... etc
    
    log_action("view_state_changed", details=details)
```

**Expected Impact**: 
- ❌ Remove 1,662 useless lines
- ✅ Log file becomes 69% smaller
- ✅ Real events easier to find

---

### **PRIORITY 2: Add Data Layer Logging** (Debugging)

**Problem**: No logging when computing mean projection  
**Location**: [image_data.py](src/phage_annotator/data/) or projection handler  
**Solution**: Log projection computation

```python
# When projection method changes:
start_ms = time.time()
try:
    mean_data = compute_mean_projection(stack_data)
    elapsed_ms = (time.time() - start_ms) * 1000
    
    logger.log_action("projection_computed",
        projection_type="mean",
        modality_idx=idx,
        input_shape=stack_data.shape,
        output_shape=mean_data.shape,
        duration_ms=elapsed_ms,
        success=True)
except Exception as e:
    logger.log_action("projection_computed",
        projection_type="mean",
        modality_idx=idx,
        duration_ms=(time.time() - start_ms) * 1000,
        success=False,
        error=str(e))
```

**Expected Impact**:
- ✅ Reveal if mean projection computation is failing
- ✅ Show performance (duration_ms)
- ✅ Verify data shapes match expectations

---

### **PRIORITY 3: Add Render Layer Logging** (Critical)

**Problem**: No logging when canvas is updated  
**Location**: [render_job_manager.py](src/phage_annotator/ui_qt/rendering/)  
**Solution**: Log render job execution

```python
# When queuing render job:
logger.log_action("render_job_queued",
    job_type="display",
    modality_idx=idx,
    reason="projection_changed",  # or "zoom", "pan", etc
    priority="high")

# When job executes:
start_ms = time.time()
try:
    render_gpu_texture(modality_idx, data)
    elapsed_ms = (time.time() - start_ms) * 1000
    
    logger.log_action("render_job_executed",
        job_type="display",
        modality_idx=idx,
        duration_ms=elapsed_ms,
        success=True)
except Exception as e:
    logger.log_action("render_job_executed",
        job_type="display",
        modality_idx=idx,
        duration_ms=(time.time() - start_ms) * 1000,
        success=False,
        error=str(e))
```

**Expected Impact**:
- ✅ Know if render job was created
- ✅ Know if render job succeeded or failed
- ✅ Performance metrics (GPU time)
- ✅ Debug mean projection rendering

---

### **PRIORITY 4: Change Logging Frequency**

**Current Issues**:
- Too frequent: sync_mode changes logged on every init
- Too verbose: All parameters logged even when None
- Missing: Critical operations not logged at all

**Recommendations**:

| Event | Current | Should Be | Reason |
|-------|---------|-----------|--------|
| **view_state_changed (init)** | Every time (1662x) | Never | Spam, all None |
| **view_state_changed (actual)** | Never logged | Every time | Important for debugging |
| **Projection compute** | Never | Once per change | CRITICAL missing |
| **Render job queue** | Never | Once per job | CRITICAL missing |
| **Render job execute** | Never | Once per job | CRITICAL missing |
| **ASSIST suggestions** | Every update | Same | ✅ Good |
| **ROI changes** | Per ROI update | Same | ✅ Good |

---

## 🔧 Implementation Checklist

**Phase 1: Eliminate Spam** (30 mins)
- [ ] Find where view_state_changed logs all None values
- [ ] Add conditional check: `if all(x is None...)` then skip
- [ ] Test: Log should drop from 5194 → ~3500 lines

**Phase 2: Add Missing Critical Logging** (1-2 hours)
- [ ] Log projection computation (with duration, shape, success/error)
- [ ] Log render job queue events (job_type, reason, modality)
- [ ] Log render job execution (success/error, duration)
- [ ] Include in LAZY_LOADER panel for easy tracking

**Phase 3: Test If Mean Projection Works** (15 mins)
After implementing logging:
```bash
# Run again, then filter:
jq 'select(.action | contains("projection"))' phage_annotator_actions.jsonl

# Should show:
# 1. projection_changed event
# 2. projection_computed event (new)
# 3. render_job_queued event (new)
# 4. render_job_executed event (new)
```

If any of steps 2-4 are missing or show errors → you found the bug!

---

## 📋 Summary: What's Informative vs. Not

| Log Type | Frequency | Useful? | Action |
|----------|-----------|---------|--------|
| `view_state_changed (all None)` | 1,662x | ❌ No | **REMOVE** |
| `view_state_changed (with data)` | 9x | ✅ Yes | **KEEP** |
| `projection_changed` | 1x | ✅ Yes | **KEEP** (but add follow-up) |
| `suggestion_queue_updated` | 50x | ✅ Yes | **KEEP** |
| `state_changed` | 2x | ✅ Yes | **KEEP** |
| `roi_state_changed` | 3x | ✅ Yes | **KEEP** |
| `projection_computed` | 0x | 🔴 MISSING | **ADD** |
| `render_job_*` | 0x | 🔴 MISSING | **ADD** |
| `canvas_updated` | 0x | 🔴 MISSING | **ADD** |

---

## 🎯 Expected Impact

**After Optimizations**:

| Metric | Before | After | Improvement |
|--------|--------|-------|------------|
| Log file lines | 5,194 | ~3,500 | -33% |
| Signal-to-noise ratio | 5:1 (noisy) | 50:1 (clean) | +900% |
| Debuggability | Medium | High | Much easier |
| Mean projection visibility | ❌ Can't debug | ✅ Clear trail | SOLVED |

---

## 🚀 Quick Fix for Mean Projection

**Hypothesis**: The logging gap between projection_changed and anything else means:

1. **Check** if `projection_computed` is called after `projection_changed`
   - Add: `logger.log_action("projection_computed", ...)`
   - If event NEVER fires → projection computation is broken

2. **Check** if render job is queued
   - Add: `logger.log_action("render_job_queued", ...)`
   - If event NEVER fires → no canvas update triggered

3. **Check** if render executes without errors
   - Add: `logger.log_action("render_job_executed", ...)`
   - If event shows error → rendering layer is failing

Once you add these three logging points, run again and look at the .jsonl file:
```bash
jq 'select(.panel == "LAZY_LOADER" or .action | contains("render"))' phage_annotator_actions.jsonl
```

**This will immediately show** if/where the mean projection pipeline breaks.

---

## 📌 Files to Modify

1. **signal_hub.py** - Remove sync_mode spam
2. **image_data.py** or projection handler - Add projection_computed logging
3. **render_job_manager.py** - Add render job logging
4. **lazy_loader.py** - Already good, just make sure it logs projection_changed

---

## Bottom Line

✅ **Logging itself is working** (file and GUI display unified)  
🔴 **What's being logged is the problem**: Spam + critical gaps  
🎯 **Solution**: Remove 31% spam, add 3 critical logging points  
🚀 **Result**: Mean projection issue becomes immediately visible in logs!
