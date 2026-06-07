"""Advanced brightness/contrast mapping with pre-computed Look-Up Tables (LUT).

Core implementation providing:
- ConverterSetup: Pre-computed LUT for instant brightness mapping
- MinMaxGroup: Coupled min/max value pair with validation
- Efficient linear mapping: output = ((input - min) / (max - min)) × 255

Phase ε.1: Core LUT engine for contrast adjustment.

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from phage_annotator.ui_qt.utils.contrast_lut_split1 import ConverterSetup
from phage_annotator.ui_qt.utils.contrast_lut_split2 import MinMaxGroup, computeHistogram, autoScaleHistogram
