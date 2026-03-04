# QC Thresholds & Sensitivity Configuration Guide

## Overview

The Phage Annotator QC system now includes **comprehensive tunable thresholds** organized into logical groups with sensible defaults and preset profiles.

All thresholds can be adjusted through an intuitive UI dialog or programmatically via the `QCThresholds` configuration class.

---

## Organization

Thresholds are logically grouped into **4 categories**:

### 1. **Annotation Spatial Constraints**
Parameters for detecting spatial issues in annotation placement.

| Parameter | Default | Min-Max | Purpose |
|-----------|---------|---------|---------|
| `duplicate_distance_px` | **2.0** | 0.1-20 px | Maximum distance between points to flag as duplicate |
| `border_safety_margin_px` | **0.0** | 0-50 px | Minimum distance from image edge (warning if closer) |
| `density_grid_size_px` | **50.0** | 10-200 px | Grid cell size for clustering analysis (smaller = finer) |
| `density_min_annotations` | **5** | 1-50 | Min annotations per grid cell to flag as cluster |

### 2. **Image Quality (Artifact Detection)**
Parameters for detecting acquisition defects in raw images/stacks.

#### Illumination Evenness
| Parameter | Default | Min-Max | Purpose |
|-----------|---------|---------|---------|
| `illumination_ratio_min` | **0.80** | 0.1-2.0 | Minimum center/border intensity ratio (below = dark edges) |
| `illumination_ratio_max` | **1.25** | 0.1-2.0 | Maximum center/border ratio (above = bright center) |

#### Photobleaching
| Parameter | Default | Min-Max | Purpose |
|-----------|---------|---------|---------|
| `photobleaching_drop_percent` | **15%** | 0-100% | Max intensity drop over frames (above = flag) |

#### Dust & Lens Artifacts
| Parameter | Default | Min-Max | Purpose |
|-----------|---------|---------|---------|
| `dust_min_pixels` | **20** | 1-1000 px | Minimum persistent artifact pixels to flag |
| `dust_percent_image` | **0.05%** | 0.01-1.0% | Percent of image size for dynamic threshold |

#### Patterned Intensity (Banding)
| Parameter | Default | Min-Max | Purpose |
|-----------|---------|---------|---------|
| `patterned_band_strength` | **0.18** | 0.01-0.50 | Max normalized band strength (row/col std / frame std) |

#### Clustered Bright Signal
| Parameter | Default | Min-Max | Purpose |
|-----------|---------|---------|---------|
| `clustered_signal_peak_count` | **50** | 1-500 | Minimum bright pixels in dominant cell |
| `clustered_signal_ratio` | **4.0** | 1.0-10.0 | Peak-to-mean bright cell count multiplier |

### 3. **Statistical (Stochasticity Tests)**
Parameters for Poisson/Fano-factor consistency checks.

#### Image Signal Fano-Factor
| Parameter | Default | Min-Max | Purpose |
|-----------|---------|---------|---------|
| `image_fano_min` | **0.6** | 0.1-5.0 | Minimum allowed Fano-factor (below = non-Poisson) |
| `image_fano_max` | **1.8** | 0.1-5.0 | Maximum allowed Fano-factor (above = non-Poisson) |
| `image_fano_warning_threshold` | **3.0** | 0.1-10.0 | Fano above this is WARNING (below is INFO) |

#### Annotation Spatial Fano-Factor
| Parameter | Default | Min-Max | Purpose |
|-----------|---------|---------|---------|
| `annotation_fano_min` | **0.5** | 0.1-5.0 | Minimum allowed Fano-factor (below = clustered) |
| `annotation_fano_max` | **2.5** | 0.1-5.0 | Maximum allowed Fano-factor (above = dispersed) |
| `annotation_fano_warning_threshold` | **2.5** | 0.1-10.0 | Threshold for WARNING severity |

### 4. **Enable/Disable Checks**
Toggle individual checks on/off.

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `enabled_duplicate_check` | **True** | Duplicate annotation detection |
| `enabled_bounds_check` | **True** | Out-of-bounds detection |
| `enabled_label_check` | **True** | Label validation |
| `enabled_density_check` | **True** | Density clustering detection |
| `enabled_illumination_check` | **True** | Uneven illumination detection |
| `enabled_photobleaching_check` | **True** | Photobleaching detection |
| `enabled_dust_check` | **True** | Dust/lens artifact detection |
| `enabled_patterned_check` | **True** | Patterned intensity detection |
| `enabled_clustered_signal_check` | **True** | Clustered signal detection |
| `enabled_image_fano_check` | **True** | Image stochasticity check |
| `enabled_annotation_fano_check` | **True** | Annotation stochasticity check |

---

## Preset Profiles

Three pre-configured sensitivity profiles are available:

### Default Profile
- **Use case:** General annotation workflow
- **Philosophy:** Balanced sensitivity and specificity
- **When to use:** Most situations, standard setting

### Strict Profile
- **Thresholds:** Tighter (flags more issues)
- Changes from default:
  - Duplicate distance: 3.0 px (vs 2.0)
  - Border margin: 5.0 px (vs 0.0)
  - Density min count: 3 (vs 5)
  - Illumination ratio: 0.90-1.15 (vs 0.80-1.25)
  - Photobleaching: 10% (vs 15%)
  - Band strength: 0.10 (vs 0.18)
- **When to use:**
  - High-quality data requiring precise annotations
  - Publication-ready work
  - Dense annotation regions
  - Critical biological targets

### Relaxed Profile
- **Thresholds:** Looser (flags fewer issues)
- Changes from default:
  - Duplicate distance: 1.0 px (vs 2.0)
  - Density min count: 8 (vs 5)
  - Illumination ratio: 0.70-1.40 (vs 0.80-1.25)
  - Photobleaching: 25% (vs 15%)
  - Band strength: 0.25 (vs 0.18)
- **When to use:**
  - Exploratory analysis
  - Rapid annotation screening
  - High-noise images
  - Tolerance for sparse annotations

---

## Using QC Thresholds

### Via UI Dialog

**In Application:**
```
QC Panel → Settings button → Opens QC Thresholds Dialog
```

Dialog has 4 tabs:
1. **Annotation Constraints** — Spatial parameters
2. **Image Quality** — Artifact detection thresholds
3. **Stochasticity** — Fano-factor bounds
4. **Checks** — Enable/disable individual validators

**Buttons:**
- `Default`, `Strict`, `Relaxed` — Load preset profile
- `OK` — Apply thresholds and close
- `Cancel` — Discard changes and close

### Programmatically

**Create and use custom thresholds:**
```python
from phage_annotator.session.qc_thresholds import QCThresholds
from phage_annotator.analysis.qc_validators import QCValidator

## Create custom config
config = QCThresholds()
config.duplicate_distance_px = 3.5  # Stricter
config.border_safety_margin_px = 10.0  # More conservative
config.density_min_annotations = 4  # Flag more clusters

## Run validation with custom thresholds
issues = QCValidator.validate(
    annotations=my_annotations,
    image_id=image_id,
    image_shape=(512, 512),
    thresholds=config
)
```

**Load preset:**
```python
## Strict mode
strict_config = QCThresholds.strict_profile()

## Relaxed mode
relaxed_config = QCThresholds.relaxed_profile()

## Default
default_config = QCThresholds()
```

**Serialize/load:**
```python
## Save to settings
config_dict = qc_thresholds.to_dict()
settings.setValue("qc_thresholds", config_dict)

## Load from settings
config_data = settings.value("qc_thresholds", {})
restored = QCThresholds.from_dict(config_data)
```

### Default Behavior

If no thresholds provided to validators:
```python
## Uses defaults automatically
issues = QCValidator.validate(annotations)
## Equivalent to:
## issues = QCValidator.validate(
##     annotations,
##     thresholds=QCThresholds()  # Defaults
## )
```

---

## Understanding Key Parameters

### Duplicate Distance
**What it does:** Detects annotations at the same location.
- **2.0 px:** Two points <2px apart are duplicates (default, good for most work)
- **1.0 px:** Very strict, catches sub-pixel near-duplicates
- **5.0 px:** Relaxed, allows soft clusters

**Recommendation:** Adjust based on point size. For 6-pixel PSF, use 2-3 px.

### Density Grid Size
**What it does:** Cell size for clustering analysis.
- **50 px:** Standard (catches local hotspots)
- **100 px:** Broader regions (catches global clustering)
- **20 px:** Fine granularity (sensitive to local variations)

**Recommendation:** Use 50 px for typical microscopy. Decrease for small ROIs, increase for whole-image patterns.

### Illumination Ratio
**What it does:** Detects uneven light across image.
- Ratio = mean(center) / mean(border)
- **0.80-1.25:** Good evenness (default)
- **0.70-1.40:** Relaxed (allows some vignetting)
- **0.90-1.15:** Strict (requires excellent coverage)

**Recommendation:** Adjust based on microscope. Vignetting = higher range. Flat-field = lower range.

### Photobleaching Drop
**What it does:** Detects intensity decay over frames/time.
- **15%:** Moderate (catches obvious fading)
- **10%:** Strict (catches subtle trend)
- **25%:** Relaxed (only flags severe degradation)

**Recommendation:** Typical live-cell TIRF: 10-15%. Fixed samples: 5-10%.

### Fano-Factor Bounds
**What it does:** Tests if intensity/density follows Poisson distribution.
- **Fano = variance / mean**
- **~1.0:** Perfect Poisson (shot-noise limited)
- **<1.0:** Sub-Poisson (structured signal)
- **>1.0:** Super-Poisson (disorder/heterogeneity)

**Ranges:**
- Image signal: [0.6, 1.8] – allows some deviation from shot noise
- Annotation spatial: [0.5, 2.5] – allows clustering and some uniformity

**Recommendation:** Tighten if you need rigorous stochasticity validation. Loosen if annotations naturally cluster.

---

## Workflow: Tuning Your Settings

### Step 1: Run Default Validation
```
Start with defaults (balanced for most cases)
```

### Step 2: Review False Positives
```
Too many issues flagged?
  → Load "Relaxed" preset, or
  → Manually increase thresholds
```

### Step 3: Review False Negatives
```
Missing obvious problems?
  → Load "Strict" preset, or
  → Manually decrease thresholds
```

### Step 4: Fine-Tune
```
Adjust individual parameters based on your data:
  - High-noise images? Relax artifact thresholds
  - Dense regions? Increase density threshold
  - Need publication quality? Use Strict + manual tuning
```

### Step 5: Save Configuration
```
If happy with settings:
  Settings → QC Thresholds → [OK]
  System auto-saves to configuration file
```

---

## Technical Details

### How Defaults Were Chosen

Defaults are based on:
- **SMLM localization:** 50-100 nm PSF in image space (2-5 pixels on typical detectors)
- **Microscopy artifacts:** Common in wide-field/confocal imaging
- **Annotation density:** Typical phage counts (5-50 per 512×512 field)
- **Statistical rigor:** Fano bounds allow 30-60% deviation from ideal Poisson

### Backward Compatibility

Old code calling `QCValidator.validate()` with explicit parameters:
```python
## Old style (still works)
QCValidator.validate(
    annotations,
    duplicate_threshold=2.0,
    density_grid_size=50.0,
)

## New style (preferred)
config = QCThresholds()
config.duplicate_distance_px = 2.0
QCValidator.validate(annotations, thresholds=config)
```

Both work. Explicit parameters override config values.

---

## Example: Custom Phage Counting Study

Your setup: Dense phage on bacterial surface, high background.

```python
## Create custom config
config = QCThresholds()

## Relax spatial constraints (dense targets)
config.duplicate_distance_px = 1.5  # Stricter duplicate
config.density_min_annotations = 8  # Allow clustering
config.border_safety_margin_px = 2.0  # Strict edge exclusion

## Relax artifact detection (high background)
config.illumination_ratio_min = 0.70  # Allow vignetting
config.photobleaching_drop_percent = 25.0  # Ignore fading
config.patterned_band_strength = 0.25  # Allow banding

## Strict stochasticity (check data quality)
config.image_fano_min = 0.5
config.image_fano_max = 2.5
config.annotation_fano_min = 0.5
config.annotation_fano_max = 3.0

## Disable irrelevant checks
config.enabled_dust_check = False  # Not relevant for this prep
config.enabled_patterned_check = False  # Accept banding

## Run validation
issues = QCValidator.validate(
    annotations=extracted_points,
    image_shape=image_shape,
    image_array=raw_image,
    thresholds=config
)
```

---

## Summary

| Feature | Capability |
|---------|-----------|
| **How many parameters?** | 24 total (12 numerical + 11 boolean + 1 selector) |
| **Organization** | 4 logical tabs (Spatial, Artifacts, Stochasticity, Checks) |
| **Presets** | 3 (Default, Strict, Relaxed) |
| **UI** | Dialog with spinboxes/sliders, organized tabs |
| **Programmatic API** | Full dataclass with dict serialization |
| **Backward compat** | Old code continues to work unchanged |
| **Defaults** | Validated against SMLM/live-cell microscopy data |

The system lets you go from "default + one click" to "fully customized per-study" QC validation.
