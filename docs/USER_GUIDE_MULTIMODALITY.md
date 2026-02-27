# User Guide: Multi-Modality Workflow

## Overview

The Phage Annotation Tool supports working with multiple image modalities simultaneously. This guide covers everything you need to know about managing, annotating, and analyzing multi-modality data.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Working with Modalities](#working-with-modalities)
3. [Annotations in Multi-Modality](#annotations-in-multi-modality)
4. [Display and Contrast Controls](#display-and-contrast-controls)
5. [Analysis with Multiple Modalities](#analysis-with-multiple-modalities)
6. [Keyboard Shortcuts](#keyboard-shortcuts)
7. [Tips and Best Practices](#tips-and-best-practices)

---

## Getting Started

### Opening a Multi-Modality Project

1. Launch the Phage Annotation Tool
2. Go to **File → Open Project** and select a `.phageproj` file
3. The tool automatically loads all configured modalities
4. Modality tabs appear at the top of the canvas area

### Creating Your First Multi-Modality Project

1. **File → New Project**
2. **Settings → Modalities → Add Modality**
3. Select your image files (raw, TIFF, HDF5, etc.)
4. Name each modality descriptively (e.g., "DAPI", "GFP", "mCherry")
5. Click **Save As** to create your `.phageproj` file

---

## Working with Modalities

### Modality Tabs

Modality tabs are displayed at the top of the canvas area:

```
[DAPI]  [GFP]  [mCherry]  [+]
 ↑       ↑        ↑        └─ Add new modality
 └───────┴────────┴─ Click to switch between modalities
```

- **Click a tab** to switch to that modality
- **Right-click a tab** to rename or remove the modality
- **Click [+]** to add a new modality to the project

### Renaming a Modality

1. Right-click on a modality tab
2. Select **Rename Modality**
3. Enter a new name (alphanumeric + spaces, 1-30 chars)
4. Reserved names (e.g., "__system__") are prevented
5. Click OK to save

### Removing a Modality

1. Right-click on a modality tab
2. Select **Remove Modality**
3. Confirm the deletion
4. **Note**: Annotations specific to this modality will also be removed

---

## Annotations in Multi-Modality

### Adding Annotations to a Modality

1. Select the target modality via the tabs
2. Click the **Annotation Tool** in the toolbar
3. Click on the image to place keypoints
4. Annotations are automatically tagged with the current modality
5. Press Escape or click the arrow tool to finish annotating

### Viewing Annotations Across Modalities

- **Current Modality Only**: Annotations are filtered to show only those tagged for the active modality
- **Modality-Independent Annotations**: Annotations without explicit modality tags (legacy) appear on all modalities
- **Visibility**: Use the **Annotations** panel (left sidebar) to toggle annotation visibility

### Propagating Annotations

To copy annotations from one modality to another:

1. Select source modality
2. Right-click annotation in the Annotations panel
3. Select **Propagate to Modality**
4. Select target modality
5. Annotations are copied with modality-specific tags

---

## Display and Contrast Controls

### Accessing Contrast Controls

1. **Window → Contrast Panel** (or press `Ctrl+K`)
2. Or use the **Display** section in the left sidebar

### Per-Modality Contrast Adjustment

Each modality has independent contrast settings:

1. Select the modality via tabs
2. In the Contrast Panel:
   - **Histogram**: Shows intensity distribution
   - **Min/Max Sliders**: Adjust brightness range
   - **Gamma**: Control mid-tone brightness
   - **Mode**: Choose Linear, Log, or Sqrt scaling

### Preset Buttons

- **Auto**: Automatically adjust to fit data distribution
- **Linear**: Standard linear contrast mapping
- **Log**: Logarithmic scaling for dim features
- **Sqrt**: Square-root scaling for balanced contrast

### Synchronizing Contrast

To apply changes to multiple modalities at once:

1. Select **Sync Options** in the Contrast Panel
2. Check **Link Contrast** for target modalities
3. Adjust any slider on the source modality
4. Changes propagate to all linked modalities

---

## Analysis with Multiple Modalities

### Running Analysis on Specific Modalities

1. Select the **Analysis** panel (right sidebar, or **Window → Analysis**)
2. Click **Select Modalities for Analysis**
3. Check the modalities you want to include
4. Select analysis method (Particle Detection, Density Estimation, etc.)
5. Click **Run Analysis**

### Viewing Results by Modality

Results are automatically grouped by modality:

```
Results
├─ DAPI
│  ├─ Particle Detection (423 found)
│  └─ Density Map
├─ GFP
│  ├─ Particle Detection (156 found)
│  └─ Density Map
└─ mCherry
   ├─ Particle Detection (89 found)
   └─ Density Map
```

- Click on a result to visualize it on the corresponding modality
- Results are color-coded by modality for easy identification

### Comparing Results Across Modalities

1. Open results for two modalities side-by-side
2. Use **Window → Split View** to display modalities horizontally or vertically
3. Use **View → Zoom Link** to keep spatial alignment between modalities
4. Pan and zoom are synchronized across linked views

---

## Keyboard Shortcuts

### Modality Switching

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` | Switch to Modality 1 |
| `Ctrl+2` | Switch to Modality 2 |
| `Ctrl+3` | Switch to Modality 3 |
| `Ctrl+9` | Switch to Modality 9 |

### Common Actions

| Shortcut | Action |
|----------|--------|
| `Ctrl+A` | Select all annotations |
| `Ctrl+D` | Delete selected annotations |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+K` | Toggle Contrast Panel |
| `Space` | Play/Pause stack |
| `Z` | Zoom to fit |

---

## Tips and Best Practices

### Project Organization

- Use descriptive modality names (e.g., "DAPI-405nm" vs "ch1")
- Group related modalities in the same project
- Save projects in a dedicated folder with associated images

### Annotation Workflow

1. Start with high-contrast modality for initial annotations
2. Propagate to other modalities and refine as needed
3. Use keyboard shortcuts for rapid annotation
4. Regularly save your work (`Ctrl+S`)

### Performance Optimization

1. **Stack Size**: For stacks >2GB, consider working with subregions (ROI)
2. **Contrast Adjustment**: Use preview mode to avoid re-rendering entire stack
3. **Analysis**: Run on highest-resolution modality; downsampling loses information
4. **Memory**: Monitor memory usage in taskbar; consider closing other applications

### Troubleshooting

**Modality not appearing**: Check that image files are accessible and format is supported (TIFF, HDF5, CZI, etc.)

**Slow performance**: Reduce stack size or disable real-time contrast preview while adjusting

**Annotations disappearing**: Ensure modality filter is set correctly (check Annotations panel)

**Sync not working**: Verify modalities are linked via **Sync Options** in Contrast Panel

---

## Advanced Features

### Custom Projection Types

1. Right-click modality tab
2. Select **Projection Type**
3. Choose from: Raw, Mean Projection, Max Projection, Std Projection, Min Projection
4. Useful for visualizing 3D structure (e.g., Max Projection for MIP)

### Export Multi-Modality Results

1. **File → Export Results**
2. Select format: CSV, JSON, HDF5
3. Choose **Export All Modalities** option
4. Specify output folder
5. Results include modality tags for easy post-processing

### 3D Visualization (For Z-Stack Support)

1. **Window → 3D Viewer**
2. Select modalities to include
3. Adjust opacity and color per modality
4. Rotate, pan, and zoom in 3D space

---

## FAQ

**Q: Can I work with more than 3 modalities?**  
A: Yes! The tool supports unlimited modalities. Performance depends on your system RAM.

**Q: Do annotations automatically sync between modalities?**  
A: No, annotations are modality-specific. Use **Propagate** to copy them explicitly.

**Q: Can I change a modality's image file?**  
A: Yes, right-click modality tab → **Edit Modality** → select new image file.

**Q: How do I export annotations with modality tags?**  
A: **File → Export** → choose JSON format (includes modality_idx for each annotation).

**Q: What if I accidentally delete a modality?**  
A: Press `Ctrl+Z` immediately. Once saved, deletion cannot be undone.

---

## Getting Help

- **Built-in Help**: Press `F1` or go to **Help → User Guide**
- **Issue Tracker**: Report bugs at https://github.com/chandrasekarnarayana/Phage_annotation_tool/issues
- **Documentation**: Full documentation at /docs/ in the repository
