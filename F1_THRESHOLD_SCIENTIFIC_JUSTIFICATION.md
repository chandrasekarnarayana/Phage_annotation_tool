# F1 Threshold Selection: Data-Driven Analysis

## Problem 1: Why 0.75? (My Arbitrary Choice ❌)

**What I did**: Set F1=0.75 without justification (pretty much guessed).

**Why that's wrong**:
- 0.75 is arbitrary
- Different domains need different thresholds
- Phage detection might need 0.80, 0.85, or 0.90
- No analysis of actual task requirements

---

## Problem 2: F1 Calculation Must Be On VALIDATED Data Only ✅

**Critical insight from you**: F1 should reflect only decisions the user made!

### Your Framework (Correct!)

For every decision the user makes:

```
1. "there is a suggestion we accept it"
   → User marked as ACCEPTED
   → If matches GT: TRUE POSITIVE (TP) ✓
   → If doesn't match GT: FALSE POSITIVE (FP) ✗

2. "there is a suggestion as point but we reject"
   → User marked as REJECTED
   → This is a FALSE POSITIVE (FP) we caught
   (We suggested something that wasn't valid)

3. "there is a point we identify but not suggested"
   → We didn't suggest it, but GT has it
   → FALSE NEGATIVE (FN)
   (We missed something we should have found)

4. "trivial case: no suggestion no point"
   → Not relevant for F1 (both absent = no decision to evaluate)
```

### Correct F1 Calculation

```python
# Only on VALIDATED user feedback
def compute_f1_on_validated_data(user_decisions, gt_points):
    """
    Compute F1 based only on suggestions user accepted/rejected.
    
    Parameters:
    -----------
    user_decisions : List[Dict]
        {
            'suggestion': (y, x),
            'accepted': bool,  # User said yes or no
        }
    
    gt_points : List[(y, x)]
        Ground truth points
    """
    
    # TP: User accepted AND matches GT
    tp_count = 0
    for decision in user_decisions:
        if decision['accepted']:
            # Check if suggestion matches GT
            sugg_y, sugg_x = decision['suggestion']
            is_match = any(
                euclidean_distance((sugg_y, sugg_x), (gt_y, gt_x)) < 5.0
                for gt_y, gt_x in gt_points
            )
            if is_match:
                tp_count += 1
    
    # FP: User accepted BUT doesn't match GT
    fp_count = 0
    for decision in user_decisions:
        if decision['accepted']:
            sugg_y, sugg_x = decision['suggestion']
            is_match = any(
                euclidean_distance((sugg_y, sugg_x), (gt_y, gt_x)) < 5.0
                for gt_y, gt_x in gt_points
            )
            if not is_match:
                fp_count += 1
    
    # FN: GT points we never suggested (or user rejected)
    matched_gt = set()
    for decision in user_decisions:
        if decision['accepted']:
            sugg_y, sugg_x = decision['suggestion']
            for gt_idx, (gt_y, gt_x) in enumerate(gt_points):
                if euclidean_distance((sugg_y, sugg_x), (gt_y, gt_x)) < 5.0:
                    matched_gt.add(gt_idx)
    
    fn_count = len(gt_points) - len(matched_gt)
    
    # Calculate metrics
    precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
    recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        'f1': f1,
        'precision': precision,
        'recall': recall,
        'tp': tp_count,
        'fp': fp_count,
        'fn': fn_count,
    }
```

---

## How This Should Work In Practice

### Example: User processes 10 suggestions

```
Suggestion 1 (y=100, x=200): User ACCEPTS
  → Matches GT at (99, 201)? YES → TP ✓

Suggestion 2 (y=150, x=250): User REJECTS
  → This means our model suggested noise
  → Counted as FP (false suggestion) ✗

Suggestion 3 (y=300, x=350): User ACCEPTS
  → Matches GT? NO → FP ✗

Suggestion 4 (y=400, x=450): User ACCEPTS
  → Matches GT? YES → TP ✓

... (10 suggestions total)

Results on VALIDATED data only:
  TP = 6 (user accepted, matched GT)
  FP = 2 (user accepted, didn't match GT) + 1 (user rejected - model false alarm)
  FN = ? (need to check vs all GT points for ones we missed)
  
  If total GT = 10 and we matched 6:
    FN = 10 - 6 = 4 (missed 4 points)
  
  Precision = 6 / (6 + 3) = 0.67
  Recall = 6 / (6 + 4) = 0.60
  F1 = 2 × 0.67 × 0.60 / (0.67 + 0.60) = 0.63
```

---

## Choosing the RIGHT Threshold

NOT by guessing! By analyzing:

### 1. **What Does Each Threshold Mean?**

```
F1 = 0.50: Precision ~0.50, Recall ~0.50 (Very poor - frequent retraining NEEDED)
F1 = 0.60: Precision ~0.60, Recall ~0.60 (Below acceptable - needs improvement)
F1 = 0.70: Precision ~0.75, Recall ~0.65 (Acceptable but not great)
F1 = 0.75: Precision ~0.80, Recall ~0.70 (Good - maybe OK to skip retrain)
F1 = 0.80: Precision ~0.85, Recall ~0.75 (Very good - definitely skip)
F1 = 0.85: Precision ~0.88, Recall ~0.82 (Excellent - very rarely need retrain)
F1 = 0.90: Precision ~0.92, Recall ~0.88 (Outstanding - almost never retrain)
```

### 2. **Domain-Specific: Phage Detection Requirements**

```
Question: What's acceptable error rate for phage annotation?

Scenario A: Research (high precision preferred)
  → False positives = wasted manual verification time
  → Better: Use F1_threshold = 0.85
  → Only skip retrain if Precision > 0.90

Scenario B: Screening (high recall preferred)
  → False negatives = missed phages (bad!)
  → Better: F1_threshold = 0.75
  → Ensure Recall > 0.70 before skipping

Scenario C: Balanced (production use)
  → F1_threshold = 0.80
  → Ensures both P and R are reasonable
```

### 3. **Practical Analysis: Run on Your Data**

```python
# After first few iterations, track F1 history:

Batch 1: F1=0.62 → Retrain (LOW)
Batch 2: F1=0.71 → Retrain (LOW)
Batch 3: F1=0.78 → Skip? (MEDIUM)
Batch 4: F1=0.85 → Definitely skip (HIGH)
Batch 5: F1=0.88 → Definitely skip (HIGH)

Observation: After F1 ~0.78, model stabilizes
Recommendation: Set threshold to 0.75-0.80

But for YOUR domain, it might be different!
```

---

## Updated Approach: Data-Driven Threshold Selection

Instead of hardcoding 0.75, let the data tell us:

```python
class AdaptiveF1Threshold:
    """Learn the optimal threshold from data."""
    
    def __init__(self):
        self.f1_history = []
        self.retrain_happened_list = []  # Did we retrain after this F1?
        self.quality_after_retrain = []
    
    def analyze_optimal_threshold(self):
        """
        Find the F1 value where retraining has highest ROI.
        
        Below this F1: Retraining significantly improves next batch
        Above this F1: Retraining doesn't improve much
        """
        
        # Find "break point" where retraining stops helping
        improvements = []
        for i in range(1, len(self.f1_history) - 1):
            f1_before = self.f1_history[i]
            f1_after = self.f1_history[i + 1]
            improvement = f1_after - f1_before
            
            improvements.append({
                'f1_threshold': f1_before,
                'improvement': improvement,
            })
        
        # F1 where average improvement drops < 5%
        optimal = 0.75  # Default
        for item in improvements:
            if item['improvement'] < 0.05:  # <5% improvement
                optimal = item['f1_threshold']
                break
        
        return optimal
```

---

## Revised Recommendation

### Change from "fixed 0.75" to "data-driven + domain tuning"

```python
# New approach
class AdaptiveRetrainingStrategy:
    def __init__(self, domain='balanced', initial_threshold=0.75):
        self.f1_history = []
        
        # Set based on domain
        self.domain_thresholds = {
            'high_precision': 0.85,  # Research - avoid false positives
            'high_recall': 0.65,     # Screening - catch everything
            'balanced': 0.75,        # Default - good for most tasks
        }
        
        self.f1_threshold = self.domain_thresholds.get(domain, initial_threshold)
    
    def should_retrain(self, current_f1, validator_feedback_size=None):
        """
        Smart decision: retrain if F1 < threshold
        
        But also consider:
        - How many decisions made so far (need N>10 to be confident)
        - Whether last retrain actually helped
        - Trending of F1 (is it improving or degrading?)
        """
        self.f1_history.append(current_f1)
        
        # Need minimum decisions before trusting F1 score
        if len(self.f1_history) < 10:
            return False
        
        # Check trend: Is F1 improving?
        recent_f1s = self.f1_history[-3:]
        is_improving = recent_f1s[-1] >= recent_f1s[0]
        
        # Retrain if:
        # 1. F1 below threshold AND
        # 2. F1 not improving on its own
        if current_f1 < self.f1_threshold and not is_improving:
            return True
        
        return False
```

---

## Summary: Why Not 0.9, 0.95, or 0.99?

### 0.9 (Too High)
```
✗ Too strict - retrains constantly
✗ F1=0.90 means Precision~0.92, Recall~0.88 (nearly perfect)
✗ Real-world data rarely stays perfect
✗ Wastes computation with excessive retraining
```

### 0.95 / 0.99 (Way Too High)
```
✗ Unrealistic - would need ~perfect performance
✗ Essentially "always retrain"
✗ Defeats purpose of adaptive threshold
✗ Phage detection can't be >99% accurate (biological variation)
```

### 0.75 (Reasonable but Arbitrary)
```
✓ Means Precision ~0.80, Recall ~0.70 (acceptable)
✓ Allows some model degradation before retraining
✓ Reduces excessive retraining
✗ But: No data-driven justification!
```

### 0.65-0.70 (Too Low - Don't Use)
```
✗ Model performs poorly before retraining
✗ User sees many wrong suggestions before fix
✗ Defeats purpose of maintaining quality
```

---

## THE RIGHT ANSWER

**It depends on your domain requirements!**

```
For Phage Annotation:
  • If research (need high accuracy): F1_threshold = 0.80-0.85
  • If screening (catch everything): F1_threshold = 0.65-0.70
  • If balanced (typical): F1_threshold = 0.75
  
Choose based on:
  1. What error types cost the most?
     - False positives (extra work) → Use higher threshold
     - False negatives (missed phages) → Use lower threshold
  
  2. What's your reference experiment's F1?
     - If human baseline is F1=0.85 → Set threshold = 0.80
     - If human baseline is F1=0.75 → Set threshold = 0.70
```

---

## Action Items

1. **Calculate F1 correctly on validated data** (user's framework)
2. **Analyze your data** to find natural break point
3. **Set threshold based on domain**, not guessing
4. **Make it configurable** in code:

```bash
python test_assist.py --f1-threshold 0.75 --domain balanced
python test_assist.py --f1-threshold 0.85 --domain high_precision
python test_assist.py --f1-threshold 0.65 --domain high_recall
```

Your question revealed a critical gap - thank you for pushing for the real answer!
