# Assisted Annotation System: Complete Architecture & Workflow Guide

## Table of Contents

1. [Overview & Trust States](#overview--trust-states)
2. [How Suggestions Are Generated](#how-suggestions-are-generated)
3. [Ranking & Calibration](#ranking--calibration)
4. [Training & Learning](#training--learning)
5. [Integration with Annotation](#integration-with-annotation)
6. [QC & Diagnostics](#qc--diagnostics)
7. [Review Workflow](#review-workflow)
8. [Detection & Error Handling](#detection--error-handling)

---

## Overview & Trust States

### Three Canonical Assist States

The system operates in **three progressive trust levels**, which communicate confidence in suggestions:

#### 1. **HEURISTIC** (Gray, `#9e9e9e`)
- **Trust Level:** Low / No learning data yet
- **Status:** Pure model-based suggestions without user feedback
- **When Active:**
  - Application startup (no training samples)
  - First image load (no accept/reject decisions yet)
  - Learning disabled manually
- **Scoring:** Raw model confidence only (no user-informed ranking)
- **UI Cue:** Suggestions appear in neutral gray; model state shows "Heuristic"

#### 2. **LEARNED_UNCALIBRATED** (Yellow, `#fdd835`)
- **Trust Level:** Medium / Model learning active, confidence uncalibrated
- **Status:** User feedback collected, ranker trained, but no probability calibration
- **When Active:**
  - ≥ training samples recorded (default: 25)
  - Auto-retrain enabled
  - Ranker weights updated from accept/reject decisions
- **Scoring:** Logistic model applied to feature vectors; outputs range [0, 1] but may be miscalibrated
- **UI Cue:** Suggestions ranked by learned importance; yellow indicator shows "Learned (Uncalibrated)"

#### 3. **CALIBRATED** (Green, `#43a047`)
- **Trust Level:** High / Learned model with well-calibrated probabilities
- **Status:** Probability estimates match real accuracy
- **When Active:**
  - Suggestions have `meta["confidence_available"] == True`
  - Platt calibrator fitted on validation hold-out
  - Systematic distortion removed
- **Scoring:** Logistic output post-processed through Platt scaling to match observed acceptance rate
- **UI Cue:** Green badge "Calibrated"; confidence scores directly interpretable as "% likely to accept"

**State Transition Flow:**
```
App Start
   ↓
HEURISTIC (no training data)
   ↓ [User accepts/rejects suggestions, ≥25 labeled samples]
LEARNED_UNCALIBRATED (ranker trained)
   ↓ [Platt calibrator fitted, confidence_available set]
CALIBRATED (ready for production confidence use)
```

---

## How Suggestions Are Generated

### Generation Pipeline

**Entry Point:** User clicks "Generate Suggestions" or "Generate for Current Slice/Image"

#### 1. **Model: LocalPeakSuggestionModel**

The system uses a **fast heuristic model** based on local maxima detection:

```python
LocalPeakSuggestionModel(
    min_distance_px=6,          # Non-maximal suppression radius
    max_points=200,             # Hard cap on candidates per slice
    threshold_quantile=0.995,   # 99.5th percentile intensity = threshold
    scale_sigma=1.0,            # Gaussian scale for fitting
    model_name="local_peaks"
)
```

#### 2. **Candidate Collection**

For each 2D slice (single t/z frame):

```
A. Illumination Correction
   - Subtract local mean (9-neighborhood) to suppress uneven background
   
B. Threshold Computation
   - Find 99.5th percentile of finite intensity values
   - Skip pixels below threshold
   
C. Local Maxima Detection
   - For each pixel with intensity > threshold:
     * Check if it's local max in 3×3 window
     * Skip if outside ROI (if ROI specified)
     
D. Feature Extraction (per peak found)
   - Peak intensity (normalized by max in frame)
   - SNR (peak - median) / std
   - Local contrast (peak / local background)
   - Laplacian response (edge detection)
   - Gaussian fitting (amplitude, sigma, residual fit)
   
E. Scoring
   Composite = 0.45×peak_norm + 0.2×snr + 0.15×contrast + 0.2×residual_penalty
```

#### 3. **Multi-Strategy Generation**

The model supports **three strategies** to handle different imaging conditions:

| Strategy | Source | Description |
|----------|--------|-------------|
| **raw** | Original image | Local peaks on raw intensity |
| **corrected** | Local-mean subtracted | Peaks on illumination-corrected signal |
| **consensus** | Intersection of raw + corrected | Merged peaks (within 6px radius) scored as average |

**Generation Call:**
```python
# For current slice:
proposals = model.predict(
    image_slice=image_data[t, z, :, :],
    image_id=image_id,
    image_name="image_001",
    t=t,
    z=z,
    label="phage",
    strategy="raw",  # or "consensus"
    roi_id=roi_id,
    roi_shape="box",
    roi_rect=(x0, y0, x1, y1)
)
```

#### 4. **Enrichment for Training**

After generation, each proposal is enriched with **contextual features** that help the ranker learn:

```python
Suggestion.meta.update({
    "distance_to_nearest_accepted": distance,  # Proximity to user's existing annotations
    "border_proximity": min(x, y, w-x, h-y),  # Distance from image edge
    "derived_from_accepted_area": bool,         # Within PSF of accepted annotation
    "confidence_available": False,              # Set to True only if calibrated
})
```

---

## Ranking & Calibration

### Two-Tier Ranking System

Suggestions go through **two independent filters** before display:

#### **Tier 1: Model-Based Ranking** (Always Active)

The **LocalPeakSuggestionModel** produces initial scores (0–1 range).

**Used for:**
- Sorting candidates by plausibility in HEURISTIC state
- Initial filtering (score ≥ threshold)

**Output:** Ordered list of proposals, roughly sorted by "model confidence"

#### **Tier 2: Learned Ranker** (Optional, When Trained)

**LightweightSuggestionRanker** learns from accept/reject decisions.

```python
@dataclass
class LightweightSuggestionRanker:
    weights: np.ndarray         # Learned logistic weights (16 features)
    bias: float                 # Intercept
    mean, std: np.ndarray       # Feature normalization stats
    calibrator_a, b: float      # Platt scaling parameters
    trained_samples: int        # Count of labeled samples used
```

### Feature Vector (16 features)

Extracted from each proposal and its metadata:

| Index | Feature | Source | Meaning |
|-------|---------|--------|---------|
| 0 | `score` | Model | Initial confidence from LocalPeak |
| 1–8 | `peak`, `snr`, `contrast`, `std`, `bg`, `amplitude_fit`, `sigma_fit`, `residual_fit` | `score_components` | Microspeckle properties |
| 9 | `log_response` | Laplacian | Edge-like quality |
| 10 | `distance_to_nearest_accepted` | Meta | How close to existing points |
| 11 | `border_proximity` | Meta | Distance from image edge |
| 12–15 | `strategy_raw`, `strategy_corrected`, `strategy_consensus`, `strategy_channel_rule` | Source modality | One-hot encoding of generation method |

### Logistic Ranking Pipeline

```
Raw Features (16D)
    ↓ [Z-normalize by learned mean/std]
Normalized Features
    ↓ [Logistic transform: p = 1/(1 + exp(-(w·x + b)))]
Logits → Probabilities [0, 1]
    ↓ [Optional: Platt calibration if >= confidence_available]
Final p_accept (user would accept this proposal)
```

#### Training from Feedback

**Training Data Source:** Accept/Reject decision history

```python
# When user accepts a proposal:
training_sample = {
    "features": feature_vector_from_suggestion(proposal),
    "label": 1,                          # Positive (accepted)
    "weight": 1.0,                       # Can upweight recent decisions
    "timestamp": time.time(),
}

# When user rejects:
training_sample["label"] = 0             # Negative
```

**Training Algorithm:** Stochastic gradient descent with L2 regularization

```python
def fit(features, labels, sample_weight=None, lr=0.1, epochs=250, l2=1e-3):
    """
    Logistic regression training:
    
    For each epoch:
        For each batch:
            logits = X @ w + b
            p = sigmoid(logits)
            error = p - y (weighted)
            grad_w = (X.T @ error) / n + l2*w
            grad_b = mean(error)
            w -= lr * grad_w
            b -= lr * grad_b
    """
```

**Convergence Check:**
- Stops if only one class in training data (can't learn)
- Monitor gradient magnitude for early stopping (optional)

### Calibration (Platt Scaling)

After ranker is trained, **Platt calibration** is applied:

```python
def calibrate(logits_on_validation_set, labels_on_validation_set):
    """
    Fit: p_calibrated = sigmoid(a * logit + b)
    
    by minimizing -log-likelihood with SGD (200 iterations).
    Adjusts ranker's miscalibration (e.g., too confident, too conservative).
    """
```

**Prevents:**
- Overconfident scores (ranker says 95% accept but users only accept 60%)
- Conservative bias (ranker says 40% but users accept 80%)

**Result:** Calibrated probabilities match observed acceptance rate ± a few percent

---

## Training & Learning

### Warmup Mode: Guided Bootstrap

**Purpose:** Accelerate initial learning by guiding users to label diverse examples

**Entry:** User clicks "Start Assist Warmup" or after first 10 suggestions generated

**Flow:**

```
1. Display breakdown of needed labels per context:
   Context "image1|stack|current_view":
     Total needed: 30  
     Positive (accept) needed: 15
     Negative (reject) needed: 15
     Per-context minimum: 10
   
2. Guide user through proposals with N/P (next/prev) and A/R (accept/reject)
3. Show progress: "Accept 8/15  Reject 4/15"
4. Auto-trigger training when all conditions met
```

**Warmup Conditions (Configurable):**
- Minimum 30 labeled proposals total
- ≥ 15 accepted, ≥ 15 rejected (balanced)
- ≥ 10 labels per annotation context (e.g., per image + annotation space)

**Why Balanced?**
- Logistic model handles class imbalance poorly
- Balanced sampling stabilizes early learning
- Prevents ranker from defaulting to "always accept"

### Auto-Retrain Trigger

**Monitoring:** After each accept/reject decision

```python
pending_label_count += 1

if (pending_label_count >= auto_retrain_min_labels  # Default: 25
    and controller.session_state.suggestion_auto_retrain_enabled):
    train_ranker_now()  # Refit from all accumulated decisions
    pending_label_count = 0
```

### Training Data Sources

**PointSuggestion Tracking:**
```python
# When user accepts a suggestion:
suggestion.status = "accepted"
suggestion.meta["accepted_at"] = timestamp

# When rejected:
suggestion.status = "rejected"

# Stored in session_state.suggestion_history for audit trail
```

**Building Training Set:**
```python
training_samples = []
for suggestion in session_state.suggestion_history:
    context_key = controller._context_key(
        suggestion=suggestion,
        annotation_space="stack"
    )
    training_samples.append({
        "features": feature_vector_from_suggestion(suggestion),
        "label": 1 if suggestion.status == "accepted" else 0,
        "context": context_key,
        "weight": 1.0,
    })
```

**Context-Aware Training:**
Ranker is **per-annotation-space** (e.g., separate for "stack" vs "frame" annotation modes):

```python
suggestion_rankers_by_space = {
    "stack": LightweightSuggestionRanker(...),    # For multi-z annotations
    "frame": LightweightSuggestionRanker(...),    # For single-z annotations
}
```

### Training Curves & Diagnostics

**Exportable metrics:**
```python
suggestion_metrics = {
    "generated": 127,          # Total proposals produced
    "accepted": 73,            # User approved
    "rejected": 54,            # User rejected
    "uncertain": 0,            # Still pending
    "mean_correction_distance": 2.1,  # Avg pixels from user to suggestion
}
```

**Logged to audit:**
```json
{
    "event": "ranker_trained",
    "timestamp": "2026-03-04T10:30:00Z",
    "trained_samples": 127,
    "feature_dims": 16,
    "learning_rate": 0.1,
    "epochs_completed": 250,
    "final_loss": 0.234,
    "validation_accuracy": 0.82,
    "state": "learned_uncalibrated"
}
```

---

## Integration with Annotation

### Workflow: Generate → Review → Accept/Reject → Train

#### **Step 1: Generate Suggestions**

User navigates to image & clicks "Generate Suggestions for Current Slice" or "Generate for All Slices":

```python
# In ActionsMixin._suggest_points_current_slice:
image_data = self._slice_data(self.primary_image)
proposals = self._gating_strategy_candidates(
    image=self.primary_image,
    t_idx=t_idx, z_idx=z_idx,
    strategy="consensus",  # or "raw"
    label=self.current_label
)

# Rank with learned ranker if available
proposals = self._rank_and_calibrate_suggestions(proposals)

# Enrich with training-relevant metadata
self._enrich_suggestions_for_training(proposals, image_data)

# Store and sort
self.suggestions[image_id].extend(proposals)
self.controller.session_state.suggestion_history[image_id].extend(proposals)
```

#### **Step 2: Display in Review Queue**

Suggestions appear in **Review Queue Panel** sorted by confidence (descending):

```
[Suggestion #1: score=0.92]  Position: (123, 456)  ← Accept (A) | Reject (R) | Skip (N)
[Suggestion #2: score=0.87]  Position: (234, 567)  
[Suggestion #3: score=0.62]  Position: (345, 678)
...
```

#### **Step 3: Accept/Reject Decision**

User navigates with `N` (next) and makes decision with `A` (accept) or `R` (reject):

```python
def _on_accept_suggestion(self, suggestion: PointSuggestion) -> None:
    """User approved this suggestion."""
    cmd = AcceptSuggestionCommand(
        controller=self.controller,
        suggestion=suggestion,
        image_id=self.primary_image.id
    )
    self.controller.execute_command(cmd)
    # Keypoint added to annotations
    # Suggestion marked "accepted" in history
    
def _on_reject_suggestion(self, suggestion: PointSuggestion) -> None:
    """User rejected this suggestion."""
    cmd = RejectSuggestionCommand(
        controller=self.controller,
        suggestion=suggestion,
        image_id=self.primary_image.id
    )
    self.controller.execute_command(cmd)
    # Suggestion removed from queue
    # Marked "rejected" in history
```

#### **Step 4: Auto-Train When Threshold Crossed**

After 25 new accept/reject decisions:

```python
if pending_labels >= auto_retrain_min_labels:
    self.controller.train_suggestion_ranker_now()
    # UI updates: "Training ranker..."
    # After completion: "Learned (Uncalibrated)" state
```

### Command Pattern: Ensuring Undo/Redo for Suggestions

All suggestion decisions are **undoable** via command pattern:

```python
class AcceptSuggestionCommand(Command):
    def execute(self) -> bool:
        # Add Keypoint to annotations
        # Mark suggestion.status = "accepted"
        # Record in training history
        
    def undo(self) -> bool:
        # Remove Keypoint
        # Restore suggestion.status = "pending"
        # Revert training count
        
    def redo(self) -> bool:
        # Re-execute

class RejectSuggestionCommand(Command):
    # Similar, but removes from queue instead of adding point
```

**Invariant:** Undo/redo always keeps training history consistent with displayed annotations.

---

## QC & Diagnostics

### Quality Checkpoints

#### **Before Ranking: Suggestion Quality**

```python
# LocalPeakSuggestionModel validates each proposal:
for proposal in candidates:
    assert proposal.image_id >= 0, "Image ID not set"
    assert np.isfinite(proposal.score), "Score is NaN"
    assert 0 <= proposal.score <= 1, "Score out of [0, 1]"
    assert proposal.x >= 0 and proposal.y >= 0, "Negative coordinates"
    assert proposal.score_components is not None, "Missing features"
```

#### **Before Training: Training Data Quality**

```python
def validate_training_data(samples):
    """Ensure ranker input is well-formed."""
    for sample in samples:
        features = sample["features"]
        label = sample["label"]
        
        assert features.shape == (16,), f"Wrong feature count: {features.shape}"
        assert np.all(np.isfinite(features)), "NaN in features"
        assert label in [0, 1], f"Invalid label: {label}"
        assert np.all(features >= -100) and np.all(features <= 1000), "Feature out of range"
```

#### **After Training: Ranker Status**

```python
ranker = LightweightSuggestionRanker()
ranker.fit(features, labels, sample_weight=weights)

# Diagnostics:
print(f"Trained on {ranker.trained_samples} samples")
print(f"Weight norms: {np.linalg.norm(ranker.weights):.3f}")
print(f"Calibrator: a={ranker.calibrator_a:.3f}, b={ranker.calibrator_b:.3f}")

if ranker.calibrator_a < 0.5 or ranker.calibrator_a > 2.0:
    warnings.warn("Ranker may be poorly calibrated")
```

### Visualization: "Why Was This Suggested?"

**Suggestion Explain Panel** shows breakdown per proposal:

```
Current Suggestion: "phage" at (234, 567)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Assist State: Learned (Uncalibrated)
Confidence: 0.78 (78% likely to accept)

Feature Importance (approximated):
  Peak intensity:              ▓▓▓▓▓  (0.35)
  SNR:                         ▓▓▓    (0.18)
  Gaussian fit quality:        ▓▓     (0.12)
  Distance to nearest:         ▓      (0.08)
  ...

Prediction Path:
  1. LocalPeak detected local maximum at (234, 567)
  2. Extracted 16 features from neighborhood
  3. Learned ranker scored: logit = 1.12 → p = 0.75
  4. Platt calibrator adjusted: p = 0.75 * 1.04 + 0.02 = 0.78

Context: image_001 | stack | current_view
```

### Anomaly Detection

**System alerts on:**

```python
if mean(all_proposal_scores) < 0.2:
    warning("Suggestions very low confidence; check image quality")

if accepted > total * 0.95:
    warning("Suspiciously high acceptance rate; user may be auto-clicking")

if distance_to_nearest > 20 on average:
    warning("Suggestions far from user annotations; model drift detected")
```

---

## Review Workflow

### Queue Navigation

**Keyboard shortcuts:**
- `N` / arrow-right: Jump to next suggestion
- `P` / arrow-left: Jump to previous
- `A`: Accept current
- `R`: Reject current
- `W`: Focus on next uncertain (lowest confidence)
- `Space`: Pan view to center on suggestion

**Mouse:**
- Click suggestion in queue panel → jumps to that location, highlights in image

### Batch Operations

**Clear all suggestions:**
```python
cmd = ClearSuggestionsCommand(controller, image_id)
self.controller.execute_command(cmd)
# Clears self.suggestions[image_id]
# Clears corresponding entries from history
```

**Regenerate with different strategy:**
```python
# Clear old
self._suggest_points_current_slice(strategy="corrected")  # Instead of "raw"
# New proposals ranked and enriched
```

### Re-Decision Support

If user **changes mind** about an accepted suggestion:

```python
def _confirm_suggestion_redecision(self, target_status: str) -> bool:
    """Confirm potentially destructive re-decision."""
    if target_status == "rejected" and current.status == "accepted":
        reply = QMessageBox.question(
            self,
            "Reverse Accept?",
            f"Remove '{current.label}' at ({x:.0f}, {y:.0f}) from annotations?"
        )
        return reply == QMessageBox.Yes
```

Action: Executes `RejectionDecisionCommand` to undo the accept.

---

## Detection & Error Handling

### Common Error Scenarios

#### **Error: "Model initialization failed"**
- **Cause:** Image data is invalid (NaN, inf, wrong shape)
- **Fix:** 
  ```python
  image_data = self._slice_data(self.primary_image)
  if image_data is None or not np.isfinite(image_data).any():
      self._set_status("Error: Image data invalid")
      return
  ```

#### **Error: "Ranker training failed"**
- **Cause:** Features are constant or all NaN
- **Fix:**
  ```python
  if np.std(features, axis=0).sum() == 0:
      logger.warn("Cannot train ranker: features constant")
      return False
  ```

#### **Error: "Confidence unavailable"**
- **Cause:** Platt calibrator not fitted yet
- **Fix:**
  ```python
  if not getattr(suggestion, "meta", {}).get("confidence_available"):
      confidence_str = "N/A (uncalibrated)"
  else:
      confidence_str = f"{suggestion.meta['confidence']:.0%}"
  ```

### Logging & Audit Trail

**All key events logged:**

```python
self.controller.append_audit_event(
    "suggestions_generated",
    image_id=image_id,
    count=len(generated),
    strategy=strategy,
    model_name="local_peaks",
    timestamp=time.time()
)

self.controller.append_audit_event(
    "suggestion_accepted",
    suggestion_id=suggestion.suggestion_id,
    image_id=image_id,
    nearest_distance=meta["distance_to_nearest_accepted"],
    confidence_score=suggestion.score,
    assist_state=infer_assist_state(...)
)

self.controller.append_audit_event(
    "ranker_trained",
    trained_samples=ranker.trained_samples,
    validation_accuracy=accuracy,
    state="learned_uncalibrated"
)
```

### Recovery from Partial Failures

**If training crashes mid-epoch:**
```python
try:
    ranker.fit(features, labels, epochs=250)
except Exception as e:
    logger.error(f"Training failed: {e}")
    # Keep old ranker state if recovery possible
    if ranker.trained_samples > 0:
        logger.info("Falling back to previous ranker")
    else:
        self.assist_state = AssistState.HEURISTIC
```

---

## Advanced Topics

### Per-Context Learning

Ranker can be **specific to annotation context** to handle biased regions:

```
Context Key Format: "{image_name}|{annotation_space}|{strategy}"
  Example: "image_001|stack|current_view"
           "image_001|frame|all_slices"
           
Benefits:
  - learn that user prefers central regions (context=current_view)
  - learns different criteria for frame vs stack mode
  - separate calibration per context
```

### Feature Importance Estimation

Approximate which features matter most:

```python
def estimate_feature_importance(ranker):
    """Abs(weight) × mean(feature) ~ importance."""
    importance = np.abs(ranker.weights) * np.abs(ranker.mean)
    for i, feat_name in enumerate(FEATURE_NAMES):
        if ranker.std[i] > 0:
            # Normalize by feature variance
            importance[i] /= ranker.std[i]
    return importance
```

**Displayed in "Why Was This Suggested?" panel.**

### Offline Calibration

If deploying to production, **pre-calibrate** on historical data:

```python
# Collect 500+ accept/reject decisions in development
dev_suggestions = load_dev_history()
dev_features = np.vstack([
    feature_vector_from_suggestion(s) for s in dev_suggestions
])
dev_labels = np.array([s.status == "accepted" for s in dev_suggestions])

# Train offline
ranker = LightweightSuggestionRanker()
ranker.fit(dev_features, dev_labels)

# Serialize
save_model(ranker, "production_ranker.pkl")

# In production, load and apply
ranker = load_model("production_ranker.pkl")
```

---

## Summary Table

| Component | Purpose | Inputs | Outputs | State |
|-----------|---------|--------|---------|-------|
| **LocalPeakSuggestionModel** | Generate candidates | Image slice, ROI, strategy | Proposals with 16 features | Always active |
| **LightweightSuggestionRanker** | Learn from feedback | Feature vectors + accept/reject labels | Logistic weights, calibrator params | Trained after 25+ labels |
| **FeatureEnrichment** | Attach training context | Proposals + annotations + image | Metadata with proximity, border, etc. | Per-generation |
| **Platt Calibration** | Calibrate confidences | Validation logits + labels | Calibrator a, b | Optional, if confidence needed |
| **Warmup Mode** | Bootstrap learning | User decisions | Balanced training set | Initial phase only |

---

## Key Takeaways

✅ **Heuristic (Gray) →** Fast baseline, no learning data  
✅ **Learned Uncalibrated (Yellow) →** User feedback incorporated, but probabilities may be miscalibrated  
✅ **Calibrated (Green) →** Probabilities match user acceptance rates; ready for confidence-driven workflows  

✅ **Generation** is always model-based (local peaks)  
✅ **Ranking** becomes user-aware after ~25 labeled examples  
✅ **Calibration** ensures confidence scores are trustworthy  

✅ **Integrate tightly** with annotation (undo/redo, audit logging)  
✅ **QC continuously** (feature validation, anomaly detection)  
✅ **Diagnose visually** ("Why Was This Suggested?" panel)
