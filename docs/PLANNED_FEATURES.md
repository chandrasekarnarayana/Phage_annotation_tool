# Planned Features (Active Backlog)

Last updated: February 27, 2026

## Scope
This file tracks only not-yet-implemented capabilities.
Completed capabilities are documented in implementation summaries and test reports.

## Priority Backlog

| Priority | Capability | Why It Matters | MVP Target |
|---|---|---|---|
| P0 | Assisted annotation (model-in-the-loop) | Biggest throughput gain for dense keypoint labeling | Suggest + accept/reject workflow with online quality tracking |
| P1 | Standard export suite | Interop with external tooling and model training pipelines | COCO keypoints + normalized CSV/JSON export |
| P1 | Collaboration and review workflow | Team-scale quality control and reproducibility | Review states, assignment, and audit trail in project data |
| P2 | Reviewer analytics | Measure annotation velocity and disagreement hotspots | Per-user metrics and issue trend dashboard |

## 1) Assisted Annotation (Model-in-the-Loop)

### Productized version for this tool
- Point proposal mode for current T/Z slice and optional batch proposal for full stack.
- Confidence-gated suggestions with color-coded certainty and one-click accept/reject.
- "Correct and learn" loop: accepted/rejected edits are logged as training signals.
- Slice-aware priors using existing local-maximum snapping and QC detectors.

### MVP
- Add a `Suggest Points` action in the annotation toolbar.
- Render suggestions as non-committed overlays.
- Add bulk actions: `Accept Visible`, `Reject Visible`, `Accept In ROI`.
- Track suggestion precision/recall proxy metrics:
  - accept rate
  - correction distance (suggested -> final)
  - reject reasons

### Technical hooks
- New session state bucket for ephemeral suggestions.
- Command objects for accept/reject operations (undo/redo safe).
- Lightweight model interface (`predict(image_slice) -> point proposals`).

### Success criteria
- 30%+ reduction in manual click count for dense annotation tasks.
- No regression in final QC issue rate.

## 2) Standard Export Suite

### Productized version for this tool
- COCO keypoints export for ML interoperability.
- Flat CSV/JSON export with explicit T/Z/image/channel metadata.
- Review-ready "evidence bundle" export:
  - annotations
  - QC report
  - reviewer decisions
  - tool/version metadata

### MVP
- Add export dialog with schema presets:
  - `COCO Keypoints`
  - `Canonical CSV`
  - `Canonical JSON`
- Add validation pass before export with actionable errors.
- Add importer round-trip tests for each schema.

### Technical hooks
- Extend existing export module with schema adapters.
- Version each export schema (`schema_version`) to preserve compatibility.

### Success criteria
- Deterministic export output for same project state.
- Round-trip parity tests pass in CI for all supported formats.

## 3) Collaboration and Review Workflow

### Productized version for this tool
- Annotation lifecycle states:
  - `new`
  - `in_review`
  - `approved`
  - `needs_changes`
- Assignment fields on image regions or task queues.
- Immutable audit trail for all annotation edits and review decisions.

### MVP (desktop-first)
- Add per-annotation review state and reviewer metadata.
- Add project-level activity log with timestamped command history.
- Add filtered views: "My queue", "Needs review", "Blocked by QC".

### Phase 2 (multi-user service)
- Optional server-backed project store with optimistic locking.
- Conflict resolution UI for concurrent edits.
- Role-based permissions (annotator/reviewer/admin).

### Success criteria
- Full traceability from final annotation to edit/review history.
- Reduced review turnaround time via queue-based workflows.

## Naming and Documentation Policy

- File names and docstrings use capability-oriented naming.
- Milestone labels and rollout-order labels are intentionally removed from active file names, comments, and docstrings.
- Backward compatibility comments remain focused on behavior and interfaces.
