# Tutorial: Annotate and Review a Time Series

This tutorial demonstrates a complete workflow using a time-series image.

## 1. Open data

Launch the application and open a TIFF or OME-TIFF stack with `Ctrl+O`.

## 2. Set display state

Choose the active frame, LUT, contrast window, and projection settings. If the
image is large, rely on lazy loading and projection cache behavior rather than
exporting full-resolution views immediately.

## 3. Add seed annotations

Create several manual keypoints. These become ground truth for review and can
also warm up assisted workflows.

## 4. Generate suggestions

Run suggestion generation from the assist controls. Inspect the review queue and
open the explain panel when a score is unclear.

## 5. Accept and reject candidates

Use `A`, `R`, `N`, and `P` for a fast review loop. Correct uncertain or stale
states before bulk accepting.

## 6. Run QC

Run QC validation, navigate to issues, and repair metadata or positions.

## 7. Save and export

Save a project for full reproducibility. Export annotations to CSV or JSON for
analysis pipelines.
