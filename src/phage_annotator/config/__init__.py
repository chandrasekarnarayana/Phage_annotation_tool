"""Application configuration management.

This package contains application and algorithm-specific configuration.
"""

from phage_annotator.config.settings import AppConfig, DEFAULT_CONFIG, SUPPORTED_SUFFIXES

__all__ = [
    'settings',
    'density',
    'AppConfig',
    'DEFAULT_CONFIG',
    'SUPPORTED_SUFFIXES',
]
