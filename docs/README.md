# Documentation Index

This is the canonical index for tracked project documentation.

## Source-of-Truth Locations

- `docs/PLANNED_FEATURES.md`: active implementation backlog and completed cleanup ledger.
- `docs/CURRENT_CAPABILITIES.md`: canonical snapshot of implemented runtime capabilities.
- `docs/ARCHITECTURE_DETAILED.md`: architecture and subsystem design details.
- `docs/feature_control_matrix.md`: feature flags, controls, and operational matrix.
- `docs/FIJI_THUNDERSTORM_BRIDGE.md`: Fiji/ThunderSTORM bridge backend setup and contract.
- `docs/FIJI_PLUGIN_MANIFEST_SDK.md`: strict SDK contract for manifest-based Fiji plugin execution.
- `docs/SMLM_REPRODUCIBILITY_RUNBOOK.md`: runbook mode semantics and provenance export behavior.
- `docs/reports/`: reviewer-facing reports and evaluations.
- `docs/_internal/`: internal notes, migration guides, and archived runtime-adjacent material.
- `docs/_generated/`: generated artifacts only (non-authored outputs).

## Reports

Reviewer and evaluation docs must live in `docs/reports/` and be linked from `docs/reports/README.md`.

Current tracked report set includes:

- `docs/reports/Design_Report.md`
- `docs/reports/Technical_Appendix.md`
- `docs/reports/Reproducibility_and_Validation.md`
- `docs/reports/Testing_Strategy.md`

## Contributor Rule

Do not rely on IDE-only tabs for docs that are not tracked in the repository.
If a doc is referenced in review, planning, or PR notes, it must exist under `docs/` and be indexed here.
