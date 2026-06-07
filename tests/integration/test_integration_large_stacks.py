"""Integration and performance tests for mixed C/Z/T stack handling.

These tests are intentionally CI-safe: they validate memory-pressure behavior
by lowering the runtime threshold rather than allocating multi-GB arrays.

Tests moved into sibling split modules to keep file size below 300 lines.
"""
