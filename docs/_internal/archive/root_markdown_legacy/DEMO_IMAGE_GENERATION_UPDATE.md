# Demo Image Generation - Enhanced Features

## ✅ New Capabilities

### 1. **Variable Spot Count (50-300)**
- Spots no longer fixed to 100
- Random count between 50-300 if not specified
- Can override with explicit `--spots` parameter

### 2. **System Time Random Seed**
- Default: Uses current system time (microsecond precision)
- Ensures unique demos each run
- Can override with `--seed` for reproducibility

### 3. **Annotation CSV File**
- Auto-generated alongside TIFF image
- Named `<image_name>.csv`
- Contains spot coordinates and properties

### 4. **Requested Spot Count**
- Specify exact number: `-n 100 --spots 200`
- Accepts any value (clamped to 1-1000 range)

---

## 📋 CSV Format

Each row represents a spot appearance in a frame:
```
timepoint,y,x,sigma,intensity
1,512,726,3.49,277.80
2,512,726,3.49,277.80
3,512,726,3.49,277.80
...
```

**Columns:**
- **timepoint**: Frame number (0-based, or dimension-specific)
- **y**: Y coordinate (pixels)
- **x**: X coordinate (pixels)  
- **sigma**: Gaussian width (pixels)
- **intensity**: Peak intensity value

---

## 🎯 Usage Examples

### Generate with random spots (50-300):
```bash
python -m phage_annotator
# Creates: phage_annotator_demo.tif + phage_annotator_demo.csv
```

### Generate with specific spot count:
```bash
python -m phage_annotator -n 150
# Creates 150 spots (will appear in 1-20 frames each)
```

### Generate with fixed seed (reproducible):
```bash
python -m phage_annotator -n 100 -s 42
# Same seed → same image every time
```

### Both options together:
```bash
python -m phage_annotator -n 200 -s 12345
# 200 spots, reproducible with seed 12345
```

### Provide custom images (unaffected):
```bash
python -m phage_annotator -i image1.tif image2.tif
# No demo generation; loads your images
```

---

## 📊 Implementation Details

### Code Changes

**`src/phage_annotator/demo.py`:**
- `_add_gaussian_spots()`: Now tracks and returns spot annotations
- `generate_dummy_image()`: 
  - Parameters: `n_spots=None`, `seed=None`
  - Returns: `(image_path, csv_path)` tuple
- `run_demo()`: Prints confirmation with file paths

**`src/phage_annotator/cli.py`:**
- New options: `-n/--spots` and `-s/--seed`
- Passes parameters to `generate_dummy_image()`
- Prints file paths for confirmation

### Features Used
- **numpy.random.Generator**: Modern RNG with reproducible seeds
- **csv module**: Standard CSV writing
- **time.time()**: System time for non-reproducible defaults
- **Gaussian spots**: Each spans 4-16 frames (20-80% of 20-frame stack)

### CSV Generation
- One row per spot-frame pair (not per unique particle)
- Example: 75 particles × 10 avg frames = 750 annotations
- Allows frame-by-frame tracking for validation

---

## ✨ Key Features

| Feature | Before | After |
|---------|--------|-------|
| Spot count | Fixed 100 | Variable 50-300 |
| Seed | Hardcoded (42) | System time (or specified) |
| Annotations | None | CSV with coordinates |
| Reproducibility | No | Yes (with seed) |
| Return value | Path | (Path, Path) tuple |

---

## 🔬 Testing

**Verification performed:**
- ✅ Random spot generation (50-300): Works
- ✅ Specific spot count: Works (e.g., 100 spots → 947 annotations)
- ✅ Fixed seed reproducibility: Verified (same seed = identical CSV)
- ✅ System time seed: Different runs produce different results
- ✅ CSV format: Correct headers and data
- ✅ File linking: Image and CSV both created

**Example output:**
```
✓ Generated demo image: /tmp/phage_annotator_demo.tif (55M, 20 frames × 1200×1200)
✓ Generated annotations: /tmp/phage_annotator_demo.csv (36K, 754 rows)
```

---

## 🚀 Next Steps

1. Link image and CSV in your annotation workflow
2. Use CSV for validation plots
3. Export training data with ground truth from CSV
4. Compare ML predictions against CSV coordinates

---

## 📝 Notes

- **Spot tracking**: Each spot can appear in multiple frames
- **CSV rows ≠ unique spots**: If 75 spots appear in avg 10 frames each, you get ~750 rows
- **Reproducibility**: Set seed if doing comparative testing
- **CLI backward compatible**: Existing commands work unchanged
