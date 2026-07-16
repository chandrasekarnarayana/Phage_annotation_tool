# Quickstart

This page walks through a minimal annotation session.

## Start the application

```bash
phage-annotator
```

If the console entry point is unavailable, run the module directly:

```bash
python -m phage_annotator.cli
```

## Load image data

Use **File > Open Files** or press `Ctrl+O`. Supported microscopy images include
TIFF and OME-TIFF inputs. The application normalizes axes into frame, z, and
spatial dimensions so the same UI can handle 2D, time, z, and time-z data.

## Navigate the image

Use the display controls to change time index, z index, projection mode,
contrast, LUT, and modality links. Navigation shortcuts are listed in
`reference/keyboard_shortcuts`.

## Add annotations

Select the annotation tool, choose a label, and click in the canvas. Annotation
coordinates are stored in full-resolution image coordinates, not display
coordinates, so crop and downsample state do not corrupt exported positions.

## Review suggestions

Run candidate generation from the assist controls. Suggestions appear in the
review queue and can be accepted with `A`, rejected with `R`, advanced with `N`,
and revisited with `P`.

## Save work

Use project save for reproducible sessions. A project stores image links,
display state, annotations, suggestions, review state, QC state, and workspace
metadata.

## Validate the install

```bash
python -m pytest -q --maxfail=1
```
