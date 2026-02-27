"""Qt-based GUI application for microscopy image annotation (Layer 6).

This package implements the Presentation Layer,
providing the PyQt5-based GUI for image annotation and analysis.

**Layer 6 Responsibilities**:
- Main window window: KeypointAnnotator class with all UI state
- Submodules for UI organization:
  - panels/: Feature-specific panels (threshold, particles, SMLM, density)
  - actions/: Menu and toolbar action implementations
  - rendering/: Image visualization and matplotlib integration
  - docks/: Dock widgets for metadata and diagnostics
  - widgets/: Custom Qt widgets (sliders, tables, etc.)
  - services/: Qt-specific service implementations
  - controls/: UI control grouping (density, threshold, ROI, etc.)
- Event handling: Mouse clicks, keyboard shortcuts, slider movements
- State synchronization: Qt signal/slot for state updates

**Key Concepts**:
1. **Presentation isolation**: Only Qt/GUI code in this package
2. **Event subscriptions**: Listen to framework events for updates
3. **Controller pattern**: SessionController owns state, GUI reacts
4. **Mixin composition**: Large window composed of functional mixins
5. **Headless-free**: Can be completely disabled for CLI/testing

**Dependencies**:
- framework: EventService, LogService, SettingsService (for decoupling)
- data: LazyImage, DisplayMapping (read-only access)
- core: Keypoint, SessionState, ViewState (models)
- On: PyQt5 (Qt framework)
- Not on: algorithms, cache (indirect via framework)

**Design Patterns**:
- Mixin composition: Organize large class into focused mixins
- Signal/slot: Qt event handling
- Event subscription: Listen to application-level events
- Double dispatch: Tool pattern for mouse event routing
- Lazy import: Avoid circular imports on module load

**Key Classes**:
- KeypointAnnotator: Main window inheriting from 10+ mixins
- RenderingMixin: Image rendering and matplotlib integration
- EventsMixin: Qt/matplotlib event handling + application events
- StateMixin: GUI state synchronization with SessionController
- FileActionsMixin: File I/O dialogs and operations
- ControlsMixin: Control panel functionality

**Usage**:
    from phage_annotator.ui_qt import KeypointAnnotator, run_gui
    from phage_annotator.data.models import LazyImage
    
    # Create GUI window
    images = [LazyImage.from_path("stack1.tiff")]
    window = KeypointAnnotator(images, labels=["nucleus", "cytoplasm"])
    
    # Run application
    window.show()
    run_gui()  # Starts Qt event loop

**Mixin Architecture**:
    KeypointAnnotator =
        UiSetupMixin (UI building)
      + UiExtrasMixin (extra panels)
      + JobsMixin (background tasks)
      + EventsMixin (Qt + app-level events)
      + StateMixin (state sync)
      + PlaybackMixin (T/Z playback)
      + RenderingMixin (image drawing)
      + RoiCropMixin (ROI/crop tools)
      + AnnotationsMixin (annotation ops)
      + ActionsMixin (standard actions)
      + FileActionsMixin (file operations)
      + ControlsMixin (control panels)
      + TableStatusMixin (table/status bar)
      + ExportMixin (export capabilities)

**Architecture Evolution**:
- Initial Qt GUI structure
- Mixin decomposition for maintainability
- Data source interfaces for renderer decoupling
- Event subscription and full integration complete
"""

# Lazy imports to avoid circular dependencies during module initialization
def __getattr__(name):
    if name == 'KeypointAnnotator':
        from phage_annotator.ui_qt.main_window import KeypointAnnotator
        return KeypointAnnotator
    elif name == 'run_gui':
        from phage_annotator.ui_qt.main_window import run_gui
        return run_gui
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "KeypointAnnotator",
    "run_gui",
]
