# GUI Map (Refactor Safety Net)

## 1) Entry points + Main Window + Matplotlib embedding

- CLI entry point
  - `src/phage_annotator/__main__.py` -> `phage_annotator.cli.main`
  - `src/phage_annotator/cli.py:main`

- GUI entry point / app creation
  - `src/phage_annotator/gui_mpl.py:run_gui`
  - `src/phage_annotator/gui_mpl.py:create_app`

- Main window class
  - `src/phage_annotator/gui_mpl.py:KeypointAnnotator` (QMainWindow)

- Matplotlib embedding
  - Canvas: `FigureCanvasQTAgg` in `KeypointAnnotator._setup_ui`
  - Toolbar: `NavigationToolbar2QT` in `KeypointAnnotator._setup_ui`
  - Image axes are created in `KeypointAnnotator._rebuild_figure_layout`
  - Histogram and Line Profile now use separate Matplotlib figures in docks

## 2) Image loading, caching, and projections

- Metadata-only image discovery
  - `src/phage_annotator/gui_mpl.py:_read_metadata`

- Image loading (full array / memmap)
  - `src/phage_annotator/gui_mpl.py:_load_array`
  - Uses `tif.imread` or `tif.memmap` based on `BIG_TIFF_BYTES_THRESHOLD`

- Cache management
  - `src/phage_annotator/gui_mpl.py:LazyImage` (array + cached projections)
  - `src/phage_annotator/gui_mpl.py:_ensure_loaded`
  - `src/phage_annotator/gui_mpl.py:_evict_image_cache`
  - `src/phage_annotator/gui_mpl.py:_clear_cache`

- Projections
  - `src/phage_annotator/gui_mpl.py:_ensure_projections`
  - `src/phage_annotator/gui_mpl.py:_projection` (mean)
  - `src/phage_annotator/gui_mpl.py:_std_projection` (std)

## 3) QSettings usage (keys + load/save)

- Settings object
  - `src/phage_annotator/gui_mpl.py:KeypointAnnotator.__init__`
  - `self._settings = QtCore.QSettings("PhageAnnotator", "PhageAnnotator")`

- Keys used
  - Custom layout:
    - `customGeometry`
    - `customState`
  - Sidebar mode:
    - `sidebarMode`

- Load/save locations
  - Load layout: `KeypointAnnotator._restore_layout`
  - Save layout: `KeypointAnnotator._save_layout`
  - Save default: `KeypointAnnotator._save_layout_default`
  - Sidebar mode: `KeypointAnnotator._restore_sidebar_mode`, `KeypointAnnotator._set_sidebar_mode`

## 4) Dev-only logging helper

- Module
  - `src/phage_annotator/logger.py`

- Usage in GUI
  - `src/phage_annotator/gui_mpl.py:_debug_log` -> `get_logger().debug(...)`

## 5) Notes

- The GUI uses lazy loading for images; only primary/support images are kept resident.
- Projection caches are tied to the `LazyImage` and cleared on eviction.
- Debug logging is gated by `DEBUG_CACHE` and does not change behavior.
