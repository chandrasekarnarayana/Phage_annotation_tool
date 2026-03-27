# Retraining and Stack Optimization Summary

Last updated: March 26, 2026

## Purpose

This document is the canonical summary for historical F1-threshold retraining
notes and stack-detection optimization notes that were previously duplicated as
many root-level markdown files.

## Consolidated Topics

- F1-threshold retraining rationale and behavior.
- Validated-data-centric evaluation framing.
- Stack detection optimization direction and expected performance impact.
- Migration from exploratory notes to maintainable documentation paths.

## Canonical References

Use these as active sources of truth:

- `docs/CURRENT_CAPABILITIES.md`
- `docs/PLANNED_FEATURES.md`
- `docs/reports/Technical_Appendix.md`
- `docs/reports/Reproducibility_and_Validation.md`

## Engineering Policy

- Experimental analysis notes should move directly into `docs/reports/` (reviewer
  facing) or `docs/_internal/` (internal reference), not repository root.
- Performance and retraining claims must link to executable tests or benchmark
  artifacts.
- Documentation should prefer one maintained summary over many milestone snapshots.

## Historical Material

Superseded root-level optimization markdown files were archived under:

- `docs/_internal/archive/root_markdown_legacy/2026-03-root-consolidation/`

Those files are preserved for audit history only.