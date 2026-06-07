"""Memory pressure monitoring and adaptive tile sizing tests.

Memory pressure monitoring:
- Monitor available system RAM via psutil
- Detect memory pressure: HIGH (<20%), MEDIUM (20-80%), LOW (>80%)
- Show real-time status in performance panel
- Trigger mitigation when pressure threshold exceeded

Adaptive tile sizing:
- Reduce inference tile size from 512 -> 256 -> 128 under memory pressure
- Persist settings in AppConfig
- Display current tile size in status

Tests moved into sibling split modules to keep file size below 300 lines.
"""
