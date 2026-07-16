# Quality Control

QC validators inspect annotations, metadata, density, and image-derived
signals. The goal is to surface likely issues without blocking manual work.

## Issue model

QC issues include severity, category, message, image id, optional annotation id,
and contextual metadata. Validators emit structured issues that can be shown in
the GUI, exported, or tested directly.

## Validator groups

The codebase separates validator concerns:

- density validators inspect crowded or sparse annotation regions;
- image validators inspect image artifacts and data availability;
- metadata validators inspect required fields and review state;
- composite validators combine multiple checks into project-level reports.

## User workflow

Run validation from the QC panel, inspect issues, navigate to affected
annotations, edit metadata or positions, then rerun validation. QC output should
guide review rather than replace scientific judgment.
