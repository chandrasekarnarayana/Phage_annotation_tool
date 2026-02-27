# User Guide: Modality-Aware Brightness/Contrast Controls

## Overview

The Phage Annotation Tool now includes an advanced brightness/contrast (B&C) system designed for professional microscopy image analysis. This system lets you:

- **Adjust display settings** independently for each modality with precise control
- **Apply preset transformations** (Auto, Linear, Log, Sqrt) for different data distributions
- **Persist settings** across panel switches and sessions
- **Sync changes** across multiple modalities optionally
- **Use keyboard shortcuts** for rapid workflow efficiency

## What is a Modality?

Each image or image stack in your project is called a **modality**. You might have:

- **Raw image** (fluorescence intensity)- **Support image** (reference channel)
- **Deconvolved image** (processed data)
- **Custom projections** (mean intensity, std deviation, etc.)

Each modality has its own independent brightness/contrast settings that are automatically saved and restored.

---

## The Dual-Slider Interface

### Locating the B&C Controls

In the **Histogram/Display** panel on the right sidebar, you'll find:

```
┌─────────────────────────────────────┐
│   Brightness/Contrast Controls     │
├─────────────────────────────────────┤
│                                     │
│  ┌──────────────────────────────┐  │
│  │ █ Histogram Display          │  │
│  │  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄       │  │
│  │ ▄█  ◀──────○────────●──═► ▄█ │  │ ← Dual slider
│  └──────────────────────────────┘  │
│                                     │
│  Min: [ 50  ] ◀────● Range ●────▶ │
│  Max: [ 200 ]                       │
│                                     │
│  Brightness: ━━●━━━ (+5)           │
│  Contrast:   ━●━━━━ (-10)          │
│                                     │
│ [ Auto ] [ Linear ] [ Log ] [ Sqrt]│ ← Presets
│                                     │
└─────────────────────────────────────┘
```

### Using the Dual-Slider

**The dual-slider** shows your data's brightness distribution (histogram) with two draggable handles:

1. **Left Handle (■)** = Minimum display value (black point)
2. **Right Handle (■)** = Maximum display value (white point)

#### **Adjusting Manually**

```
Original: Pixel values range 0-65535, most between 1000-5000
                ▲
          Frequency│     ╱╲
              ╱╲  ╱─╲   │
          ╱──╴╲╱╴  ╰─╶──╱
         ├─────┼─────┼────┤
         0  1000 5000 65535
         ◀──○───────●───────▶ Move handles

Result: Only pixels 1000-5000 displayed, scaled to 0-255 output
```

**How to**:
1. **Click and drag** either handle left/right to adjust
2. **Keyboard**: Click slider, use arrow keys for fine tuning
3. **Spin boxes**: Type exact values in the Min/Max fields
4. **Double-click**: Reset to auto-range for that modality

#### **Preset Buttons**

Use presets for common data patterns:

| Preset | Best For | How It Works |
|--------|----------|------------|
| **Auto** | Quick setup | Auto-scales to 2-98 percentile |
| **Linear** | Well-distributed data | Uses full data range |
| **Log** | Exponential intensity gradients | Logarithmic scaling for faint details |
| **Sqrt** | Square-root intensity changes | √(intensity)-based scaling |

**Example**: Your image has bright spots on dark background.  
→ Try **Log** scale to bring out faint details in dark areas.

---

## Brightness & Contrast Sliders

Below the main B&C slider, you'll find separate controls:

### **Brightness Slider**
- **Effect**: Shifts the entire display range up/down
- **Use**: Lighten or darken overall image without changing range
- **Example**: Setting +20 makes all pixels 20 units brighter

### **Contrast Slider**
- **Effect**: Increases or decreases the range spread
- **Use**: Make features more distinct or blend them together
- **Example**: Setting +50 spreads 100-200 range to 50-250 (more spread)

---

## Modality Display Names

Modalities can have custom names for clarity:

```
Modality Selector: [ Raw Frame ▼ ]
                   [ Signal (Ch1) ]
                   [ Reference (Ch2) ]
                   [ Mean Projection ]
```

To **rename a modality**:
1. Right-click on the modality selector
2. Choose "Rename Modality"
3. Enter new name (letters, numbers, spaces OK)
4. Click OK

Reserved names (`frame`, `support`) cannot be overwritten.

---

## Projection Types

Each modality can display different projections of 3D data:

```
Projection Selector: [ Raw ▼ ]
                     [ Mean (avg over Z) ]
                     [ Std (std over Z) ]
                     [ Min (darkest pixel) ]
                     [ Max (brightest pixel) ]
```

**Why use projections?**

- **Raw**: See single frame clearly
- **Mean**: Get average intensity across depth (noise reduction)
- **Max**: Highlight brightest feature in Z-stack
- **Std**: Visualize intensity variation

Each projection has its own B&C settings.

---

## Synchronization Options

### **What is Sync?**

By default, each modality has **independent** B&C settings. Optional **sync** links changes:

```
Without Sync:
  Adjust Raw Frame B&C → only Raw changes
  Adjust Signal (Ch1) B&C → only Signal changes

With Sync (all linked):
  Adjust Raw Frame B&C → ALL modalities update together
```

### **Enabling Sync**

Look for the **Sync Panel** in the right sidebar:

```
┌──────────────────────┐
│ Synchronization      │
├──────────────────────┤
│ Sync vmin: ☐   Linked │
│ Sync vmax: ☐   Linked │
│ Sync Contrast: ☐ Linked│
└──────────────────────┘
```

- **☐** (unchecked) = Independent settings for each modality
- **☑** (checked) = Changes apply to all selected modalities

### **Use Cases**

| Scenario | Recommended Setting |
|----------|-------------------|
| Compare raw vs processed | Don't sync (independent) |
| Multiple channels of same experiment | Sync vmin/vmax (see same range) |
| Multi-generational data | Sync contrast (same look-and-feel) |
| Different scanners | Don't sync (different brightness) |

---

## Keyboard Shortcuts

Speed up your workflow with keyboard shortcuts:

| Shortcut | Action |
|----------|--------|
| **Ctrl+1** to **Ctrl+9** | Switch to modality 1-9 |
| **Ctrl+L** | Open contrast adjustment dialog |
| **Ctrl+Alt+L** | Reset contrast to default |
| **Shift+A** | Apply auto-contrast |
| **Ctrl+T** | Open threshold analysis |
| **Ctrl+P** | Open particle analysis |
| **Ctrl+Alt+Z** | Toggle zoom/pan linking |
| **Space** | Play/pause playback |
| **←** and **→** | Previous/next frame |

---

## Common Workflows

### **Workflow 1: Quick Image Review**

```
1. Open image → Automatically loads last modality's B&C settings
2. Press Shift+A → Auto-contrast applied instantly
3. Adjust with dual-slider if needed → Changes saved automatically
4. Switch modality Ctrl+2 → Settings restored for that modality
```

### **Workflow 2: Preparing for Publication**

```
1. Open raw image (Modality 1)
2. Set B&C to 2-98 percentile (✓ Auto button)
3. Open processed version (Modality 2)
4. Match lighting (✓ Sync vmin checkbox)
5. Export → B&C settings persist in project file
```

### **Workflow 3: Comparative Analysis**

```
1. Import Control and Treated samples (Modalities 1-2)
2. ☐ Uncheck all Sync options
3. Adjust Control: Auto-contrast
4. Adjust Treated: Auto-contrast (independent)
5. Compare side-by-side without artificial matching
```

---

## Persistence & Sessions

### **Where Settings Are Saved**

- **Within Session**: Changes saved automatically to memory
  - Close tool = settings lost
  - Switch modalities = settings restored

- **In Project File** (`*.phageproj`):
  - Save project → B&C settings saved
  - Load project → Settings automatically restored
  - Share project → Collaborators see your B&C choices

### **Resetting Settings**

**To reset ONE modality**:
- Ctrl+Alt+L or button in B&C panel

**To reset ALL settings**:
- Edit → Preferences → Reset Display Settings → Confirm

---

## Troubleshooting

### **Problem: Slider range seems wrong**

**Solution**: The range adapts to actual data values (0-65535 for 16-bit).
- Verify image data type: Tools → Image Information
- If range is 0-255, your image is 8-bit (smaller range expected)

### **Problem: Log preset doesn't work**

**Solution**: Log scale requires positive-only data.
- If image has 0 values, log preset shifts data (log(0.0001) ≈ -4)
- Try **Sqrt** instead if this causes issues

### **Problem: Changes not persisting**

**Solution**: Ensure project is saved.
- File → Save Project (Ctrl+S)
- If unsaved indicator (•) visible in title bar, not saved yet

### **Problem: Modality won't rename**

**Solution**: Check for reserved names
- Cannot use names: `frame`, `support`, `modality` (reserved)
- Use names like `Raw Channel 1` instead

---

## Visual Indicators

When you look at display controls, you'll see status indicators:

```
Status Bar:
┌────────────────────────────────────────────────────────┐
│ Raw Frame (Raw) │ Auto │ Sync: ☑ vmin ☑ vmax ☐ C │
└────────────────────────────────────────────────────────┘
         ▲          ▲         ▲          ▲      ▲
    Modality    Display    Synchronization Status Badges
         Name      Mode
```

### **Modality Indicator**
Shows current modality name and projection type

### **Display Mode Badge**
- **Auto** (blue): Using automatic contrast
- **Linear** (green): Manual linear adjustment
- **Log** (orange): Logarithmic scaling
- **Sqrt** (purple): Square-root scaling
- **\*** (asterisk): Indicates you've modified from defaults

### **Sync Status**
Shows which properties are synchronized across modalities:
- **vmin**: Minimum value linked
- **vmax**: Maximum value linked
- **C**: Contrast fully linked

---

## Advanced: Multi-Modality Analysis

### **Using B&C with Multi-Modality Annotations**

When working with multiple modalities:

1. **Annotate on primary modality** (e.g., raw image)
2. **Switch to derived modality** (e.g., processed)
3. **Annotations appear automatically** because they're modality-aware
4. **Adjust B&C** for clarity without affecting annotations

### **Batch B&C Application**

Want to apply B&C to all modalities at once?

```
1. Open first modality
2. Adjust B&C to perfect settings
3. ✓ Enable all Sync checkboxes
4. Switch modalities one-by-one (adjustments cascade)
5. ☐ Uncheck Sync when done
6. Each modality now has coordinated B&C
```

---

## Tips & Tricks

✓ **Auto-contrast first**, then fine-tune manually  
✓ **Keyboard shortcuts** for 10x faster workflow  
✓ **Presets for standard data** (log for faint details)  
✓ **Sync for publications** (consistent appearance)  
✓ **Save projects** to persist your B&C work  

---

## Getting Help

- **Keyboard Shortcuts Reference**: Help → Show Shortcuts
- **Image Information**: Tools → Image Information (see data range)
- **Preferences**: Tools → Preferences → Display Settings
- **Documentation**: Help → User Guide

**Still stuck?** Check the Developer Documentation or contact support.
