# Where to Click for Assist Features in the GUI

## Quick Access Locations

### 1. **Main Assist Menu (Recommended)**
   - Look at the **Menu Bar** at the top of the window
   - Click on **"Assist"** or **"Annotation"** menu
   - Select **"Suggest Points - Current Slice"** or **"Suggest Points - Current Image"**

   This will run the assist prediction and generate suggestions for the current frame or entire image.

### 2. **Status Bar (Bottom of Window)**
   - The **status bar** at the bottom has controls for the assist system
   - Look for:
     - **"Strategy"** dropdown: Change how suggestions are generated
       - Options: Raw, Corrected, Consensus, etc.
     - **"Modality"** dropdown: Select which imaging modality to analyze
     - **Assist Mode toggle**: Enable/disable assisted annotation

### 3. **Right-Side Panels**
   - **Suggestions Panel**: Shows a list of all detected suggestions
     - Click on a suggestion to navigate to it
     - Right-click to accept/reject
   - **Settings Panel**: Configure assist parameters
     - Min distance between spots
     - Score threshold
     - Auto-training options

### 4. **Keyboard Shortcuts (if configured)**
   - **A**: Accept visible suggestion
   - **R**: Reject current suggestion
   - **N**: Next suggestion
   - **P**: Previous suggestion

### 5. **Suggestion Strategy**
   - **Current View**: Detects peaks in the current frame only
   - **Corrected**: Applies background correction before detection
   - **Stack-Aware** (optimized): Uses mean/max from multiple frames for better SNR
     - This is the recommended method for improved detection

## How Assist Works

1. **Generate Suggestions**
   - Go to Assist menu → "Suggest Points - Current Slice" (or Image)
   - The system scans for local maxima (bright spots)
   - Shows a list of detected spots ranked by confidence

2. **Review Suggestions**
   - Navigate through suggestions using keyboard (N/P) or mouse click
   - Each suggestion shows:
     - Position (X, Y coordinates)
     - Score (0-1 confidence)
     - SNR (Signal-to-Noise Ratio)

3. **Accept/Reject**
   - **A** to accept and add to annotations
   - **R** to reject and skip
   - Green overlay shows accepted, red shows rejected

4. **Fine-tune Detection**
   - Adjust **threshold** if too many false positives or missing spots
   - Change **min_distance_px** to filter clustered detections
   - Use **strategy** dropdown to try different detection modes

## Detection Parameters Explained

- **threshold_quantile**: Controls sensitivity (higher = more selective)
  - 0.995 (99.5th %ile): ~200 spots/frame (many false positives)
  - 0.9995 (99.95th %ile): ~20 spots/frame (high precision)
  - 0.9999 (99.99th %ile): ~10 spots/frame (very selective)

- **min_distance_px**: Minimum spacing between detected spots
  - Default: 6 pixels
  - Increase to reduce clustered detections

- **Strategy options**:
  - "current_view": Uses single frame
  - "corrected": Subtracts illumination artifacts
  - "stack_mean": Uses mean of nearby frames (RECOMMENDED)
  - "consensus": Only detects spots appearing across modalities

## Demo Image Tips

The generated demo image contains:
- **100 Gaussian spots** (sigma 3-6 pixels)
- **Intensity**: 1.2-3x background
- **Visible in**: 20-80% of frames
- **Expected detections**: ~40 spots per frame with default settings

For best results:
1. Use "Stack-Aware" or "Stack Mean" strategy if available
2. Set threshold_quantile to 0.9995 or higher
3. Check "Auto-retrain" in the ranker settings for ML refinement
