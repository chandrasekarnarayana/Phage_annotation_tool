"""Image rendering and visualization components."""

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    import importlib
    
    # Map requested names to their modules
    mapping = {
        'RendererMpl': ('phage_annotator.render_mpl', 'RendererMpl'),
        'RenderingMixin': ('phage_annotator.ui_qt.rendering.renderer', 'RenderingMixin'),
        'lut_names': ('phage_annotator.ui_qt.rendering.lut_manager', 'lut_names'),
        'apply_lut': ('phage_annotator.ui_qt.rendering.lut_manager', 'apply_lut'),
        'ScaleBar': ('phage_annotator.scalebar', 'ScaleBar'),
        'renderer': ('phage_annotator.ui_qt.rendering.renderer', None),
        'roi_crop': ('phage_annotator.ui_qt.rendering.roi_crop', None),
    }
    
    if name in mapping:
        module_name, attr_name = mapping[name]
        module = importlib.import_module(module_name)
        if attr_name:
            return getattr(module, attr_name)
        return module
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "RendererMpl",
    "RenderingMixin",
    "lut_names",
    "apply_lut",
    "ScaleBar",
    "renderer",
    "roi_crop",
]
