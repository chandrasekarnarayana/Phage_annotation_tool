# Comprehensive Action Logging System

## Overview
A lightweight, non-blocking action logging system that records every user interaction and background process in the GUI. Logs are written asynchronously to avoid UI blocking.

## Log Location
- **Format**: JSON Lines (one JSON object per line)
- **File**: `phage_annotator_actions.jsonl` in the working directory
- **Console**: Also available in the application log via standard logger

## What Gets Logged

### UI Panel Actions
All interactions in these panels are automatically recorded:

#### Lazy Loader Panel
- `add_modality` - Adding new modality views
- `add_builtin_projection` - Adding mean/std projections
- `projection_changed` - Changing projection type (modality or builtin)
- `bind_annotation_file` - Binding annotation files
- `load_annotation_binding` - Loading annotations from bound files
- `annotation_context_mode_changed` - Changing annotation ownership mode

#### Annotate Panel
- `add_annotation` - Adding new points
- `delete_annotation` - Removing annotations
- `edit_annotation` - Modifying annotation properties
- `batch_operation` - Bulk annotation changes

#### Contrast Panel
- `contrast_changed` - Min/max value changes
- `auto_contrast` - Auto-contrast activation
- `lut_change` - Color/LUT modifications

#### Assist Panel
- `assist_action` - Any assistant-based action
- `assist_suggestion_accepted` - Accepting suggestions
- `assist_suggestion_rejected` - Rejecting suggestions

#### QC Panel
- `qc_flag_set` - Setting QC flags/issues
- `qc_comment_added` - Adding QC comments
- `qc_review` - QC review actions

#### Annotation Table Panel
- `table_row_selection` - Row selection
- `table_batch_edit` - Batch edits in table
- `table_sort_or_filter` - Table sorting/filtering

#### Prepare Panel
- `calibration_changed` - Calibration updates
- `metadata_edited` - Metadata changes
- `channel_configured` - Channel configuration changes

### Background Processes
- `background_job` - Any long-running background task
  - Includes job name, status (started/completed/cancelled/error)
  - Duration in milliseconds
  - Error messages if failed

## Log Record Format
```json
{
  "timestamp": 1711616400.123456,
  "action": "projection_changed",
  "panel": "lazy_loader",
  "details": {
    "modality_idx": 2,
    "old_projection": "raw",
    "new_projection": "mean"
  },
  "duration_ms": 45.2,
  "error": null
}
```

### Record Fields
- `timestamp`: Unix timestamp (float)
- `action`: Action type string
- `panel`: Which panel the action occurred in
- `details`: Action-specific parameters (dict)
- `duration_ms`: How long the action took (nullable)
- `error`: Error message if action failed (nullable)

## Reading Logs

### Quick Python Script
```python
import json
from pathlib import Path

log_file = Path("phage_annotator_actions.jsonl")
for line in log_file.read_text().splitlines():
    if line.strip():
        record = json.loads(line)
        print(f"{record['timestamp']:.0f} | {record['action']:25} | {record['panel']:15} | {record['duration_ms']}")
```

### Command Line (tail)
```bash
tail -f phage_annotator_actions.jsonl | jq '.'
```

### Find Actions of Interest
```bash
## All projection changes
grep 'projection_changed' phage_annotator_actions.jsonl | jq '.details'

## Slow actions (took > 1 second)
cat phage_annotator_actions.jsonl | jq 'select(.duration_ms > 1000)'

## All errors
cat phage_annotator_actions.jsonl | jq 'select(.error != null)'
```

## Reproducing Issues
To reproduce an issue:

1. **Find the timestamp** of when issue occurred in logs
2. **Extract relevant actions** around that time
3. **Identify exact parameters** from the `details` field
4. **Replay the actions** to reproduce

Example: "User says projection doesn't change from mean to std"
```bash
grep 'projection_changed' phage_annotator_actions.jsonl | tail -5
```
This shows exactly what projection changes happened and with what parameters.

## Performance Insights

### Identify Slow Operations
```bash
cat phage_annotator_actions.jsonl | jq 'select(.duration_ms > 500) | [.action, .duration_ms]'
```

### Track Background Job Queue
```bash
grep 'background_job' phage_annotator_actions.jsonl | jq '.details.status' | sort | uniq -c
```

## Error Diagnosis

### All Errors in Log
```bash
cat phage_annotator_actions.jsonl | jq '.[] | select(.error != null) | {action, panel, error}'
```

### Errors in Specific Panel
```bash
cat phage_annotator_actions.jsonl | jq '. | select(.panel == "lazy_loader" and .error != null)'
```

## Adding Logging to New Actions

### Quick Log (One-Line)
```python
from phage_annotator.ui_qt.services.action_logger import get_action_logger

logger = get_action_logger()
logger.log_click("add_button", panel="my_panel")
logger.log_value_change("slider", old_value=0.5, new_value=0.7, panel="contrast")
```

### Automatic Timing and Error Capture
```python
logger = get_action_logger()

with logger.track_action("my_action", panel="my_panel", details={"param": value}) as details:
    # Your code here
    details["result"] = compute_something()
    # If exception occurs, it's logged automatically
```

### General Log
```python
logger.log_action(
    action="custom_action",
    panel="my_panel",
    details={"key": "value", "count": 42},
    duration_ms=123.4,  # optional
    error=None  # optional
)
```

## Benefits

1. **Non-Blocking**: Async writing doesn't freeze UI
2. **Complete**: Every action and error recorded
3. **Lightweight**: Minimal performance impact
4. **Reproducible**: Can recreate exact scenarios
5. **Diagnostic**: Timing info reveals performance issues
6. **Queryable**: JSON format works with standard tools (jq)
7. **Human-Readable**: Can be read in text editor

## Notes

- Logs are created as `phage_annotator_actions.jsonl` in current directory
- Background thread handles writing (non-blocking)
- Queue has max 10,000 records before dropping oldest
- Automatic filtering for sensitive data can be added if needed
- JSON format allows import to databases/analytics tools

---
**Status**: Fully integrated into lazy_loader, ready to extend to other panels
