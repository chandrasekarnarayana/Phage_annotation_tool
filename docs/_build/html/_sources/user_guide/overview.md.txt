# Overview

Phage Annotator is a Qt and Matplotlib application for microscopy image
annotation. It is designed for 2D images, z-stacks, time series, and combined
time-z microscopy volumes. The project combines manual annotation, assisted
candidate review, quality control, and reproducible project persistence in one
desktop workflow.

## Main capabilities

Phage Annotator supports:

- loading TIFF and OME-TIFF microscopy data;
- viewing raw frames, projections, and linked modalities;
- creating, editing, importing, and exporting keypoint annotations;
- reviewing candidate points suggested by local peak and learning workflows;
- tracking accepted, rejected, uncertain, and reviewed annotation states;
- running QC validators for density, metadata, image artifacts, and consistency;
- saving project state with image links, display settings, annotation context,
  review state, SMLM run metadata, and workspace layout;
- bridging to Fiji/ThunderSTORM workflows through subprocess, PyImageJ, and
  external plugin manifests.

## Design philosophy

The application is built around three constraints.

First, image data can be large. Display operations use lazy loading, cache
budgets, projection caches, and chunked export paths so routine UI actions do
not require loading every pixel into memory at once.

Second, annotation decisions need provenance. The command layer records
undoable changes, the session layer owns project state, and export paths preserve
metadata needed for downstream analysis.

Third, the GUI must stay responsive. Long-running work belongs in services,
workers, caches, or command objects. UI modules coordinate interaction and
rendering, while core modules remain headless and testable.

## Documentation map

Use the quickstart for a first run, the user guide for everyday workflows, the
developer guide for architecture and contribution rules, and the API reference
when you need exact class or function behavior.
