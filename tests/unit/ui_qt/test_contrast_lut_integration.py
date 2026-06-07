"""Integration tests for contrast LUT (Look-Up Table) engine.

This module validates all components of the contrast adjustment system:
- SliderPanelDouble with dual-handle interaction
- ConverterSetup with pre-computed LUT
- MinMaxGroup with validation
- DisplayMapping with per-modality vmin/vmax storage
- Contrast presets (Auto, Linear, Log, Sqrt)
- Async rendering pipeline
- Performance targets (<1ms LUT, <200ms rendering)

Tests moved into sibling split modules to keep file size below 300 lines.
"""
