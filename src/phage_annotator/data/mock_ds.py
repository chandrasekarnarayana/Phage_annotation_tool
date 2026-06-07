"""Mock data sources for testing render/data separation.

This module provides simple mock implementations of data source interfaces,
enabling isolated testing of renderers and other components that consume
data source interfaces.
"""

from __future__ import annotations

from phage_annotator.data.mock_data_source import MockDataSource

__all__ = ["MockDataSource"]
