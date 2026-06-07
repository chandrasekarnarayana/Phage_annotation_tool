"""Data source protocols impl helpers for the phage annotation tool.

This module was split from a larger implementation to keep responsibilities
small and file sizes manageable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np
from phage_annotator.data.source_abstracts import (
    AnnotationDataSource,
    CalibratedDataSource,
    OverlayDataSource,
)
from phage_annotator.data.source_protocols_overlays import SourceProtocolsOverlaysMixin
from phage_annotator.data.source_protocols import SourceProtocolsMixin



class ComprehensiveDataSource(
    AnnotationDataSource,
    OverlayDataSource,
    CalibratedDataSource, SourceProtocolsMixin, SourceProtocolsOverlaysMixin):
    """Base class for data sources implementing all interfaces.
    
    This abstract base class combines all data source interfaces.
    Subclasses must implement all abstract methods from the parent interfaces.
    """
    
    pass
