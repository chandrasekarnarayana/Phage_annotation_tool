# Documentation Index

This is the canonical index for tracked project documentation.

## Source-of-Truth Locations

- `docs/PLANNED_FEATURES.md`: active implementation backlog and completed cleanup ledger.
- `docs/CURRENT_CAPABILITIES.md`: canonical snapshot of implemented runtime capabilities.
- `docs/ARCHITECTURE.md`: package boundaries, test tiers, deployment flow, and source-quality rules.
- `docs/FEATURE_ACCESS_GUIDE.md`: feature list with GUI and CLI access paths.
- `docs/SOURCE_REFERENCE.md`: generated source reference from Python docstrings.
- `docs/SOURCE_QUALITY_AUDIT.md`: current modularity and function-docstring audit.
- `docs/ASSIST_GUIDE.md`: user-facing assist feature access and workflow guide.
- `docs/TESTING.md`: test-suite layout, naming, GUI markers, and coverage workflow.
- `docs/feature_control_matrix.md`: feature flags, controls, and operational matrix.
- `docs/FIJI_THUNDERSTORM_BRIDGE.md`: Fiji/ThunderSTORM bridge backend setup and contract.
- `docs/FIJI_PLUGIN_MANIFEST_SDK.md`: strict SDK contract for manifest-based Fiji plugin execution.
- `docs/SMLM_REPRODUCIBILITY_RUNBOOK.md`: runbook mode semantics and provenance export behavior.
- `docs/BACKGROUND_QC_MONITORING.md`: QC monitoring architecture and operational behavior.
- `docs/QC_THRESHOLDS_CONFIGURATION_GUIDE.md`: QC threshold tuning and safety guidance.
- `docs/reports/`: reviewer-facing reports and evaluations.
- `docs/_internal/logging/`: internal logging architecture and action-log guides.
- `docs/_internal/`: internal notes, migration guides, and archived runtime-adjacent material.
- `docs/_generated/`: generated artifacts only (non-authored outputs).
- `docs/_internal/CHANGE_MONITORING_LOG.md`: active migration change-tracking log.

## Reports

Reviewer and evaluation docs must live in `docs/reports/` and be linked from `docs/reports/README.md`.

Current tracked report set includes:

- `docs/reports/Design_Report.md`
- `docs/reports/Technical_Appendix.md`
- `docs/reports/Reproducibility_and_Validation.md`
- `docs/reports/Testing_Strategy.md`
- `docs/reports/THUNDERSTORM_JAR_INTEGRATION_STATUS.md`
- `docs/reports/ASSIST_ANNOTATION_VALIDATION_SUMMARY.md`
- `docs/reports/RETRAINING_AND_STACK_OPTIMIZATION_SUMMARY.md`

## Archive Policy

- Historical one-off implementation notes and transient milestone updates are stored under:
  - `docs/_internal/archive/root_markdown_legacy/`
- Archived legacy specs and historical test writeups are stored under:
  - `docs/_internal/archive/legacy_specs/`
  - `docs/_internal/archive/legacy_reports/`
- Root-level Markdown files are not used for project documentation (except top-level `README.md`).

## Contributor Rule

Do not rely on IDE-only tabs for docs that are not tracked in the repository.
If a doc is referenced in review, planning, or PR notes, it must exist under `docs/` and be indexed here.
