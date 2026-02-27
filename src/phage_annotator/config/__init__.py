"""Application configuration management.

This package contains application and algorithm-specific configuration.
"""

from phage_annotator.config.performance import DEFAULT_SLO, PerformanceSLO, REFERENCE_DATASET
from phage_annotator.config.settings import AppConfig, DEFAULT_CONFIG, SUPPORTED_SUFFIXES

__all__ = [
    'settings',
    'density',
    'performance',
    'AppConfig',
    'DEFAULT_CONFIG',
    'SUPPORTED_SUFFIXES',
    'PerformanceSLO',
    'DEFAULT_SLO',
    'REFERENCE_DATASET',
]
