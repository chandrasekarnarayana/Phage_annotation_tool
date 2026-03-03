# SMLM Reproducibility Runbook

Last updated: March 2, 2026

## What It Does

Runbook mode adds reproducibility guardrails for SMLM runs:

- lock method profile (backend + parameters)
- capture provenance events (requested/completed/toggled)
- export reproducibility bundle JSON for audit/replay

## UI Flow

In `SMLM -> ThunderSTORM`:

- enable `Runbook mode`
- click `Lock Profile` after setting approved parameters
- run SMLM as usual (locked profile is enforced when runbook mode is enabled)
- click `Export Runbook` to generate a bundle

## Persisted Data

Saved in project settings:

- `smlm_runbook_enabled`
- `smlm_runbook_locked_profiles`
- `smlm_runbook_provenance`

## Bundle Contents

Exported JSON contains:

- schema version
- export timestamp
- runbook state
- locked profiles
- provenance events
- optional session summary payload
- SHA-256 integrity checksum
