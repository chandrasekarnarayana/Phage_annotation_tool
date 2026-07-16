# Annotation Workflow

Annotations are keypoints with coordinates, label, frame metadata, provenance,
and flexible metadata fields.

## Coordinate model

Annotations store `x` and `y` in full-resolution image coordinates. A view may
be cropped, downsampled, projected, or linked across modalities, but the stored
annotation remains anchored to the underlying image space.

## Annotation metadata

Each annotation carries normalized metadata fields such as status, confidence,
ROI name, notes, review state, assignee, reviewer, and comment. Importers fill
defaults for missing metadata so legacy CSV files remain usable.

## Undo and redo

Annotation edits are represented by command objects. Commands capture before
and after mementos, which makes annotation edits undoable and serializable for
controller-level history.

## Import and export

Supported annotation formats include legacy CSV, canonical CSV, JSON, and
ThunderSTORM-compatible CSV paths. Exported rows preserve image name, time,
z-slice, full-resolution coordinates, label, source, and metadata.

## Review state

Manual annotations and accepted suggestions can be marked active, uncertain,
accepted, rejected, conflict, or reviewed depending on workflow. QC pages and
review queues use these fields for filtering and navigation.
