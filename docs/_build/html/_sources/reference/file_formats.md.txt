# File Formats

## Image data

TIFF and OME-TIFF inputs are loaded through reader abstractions that normalize
axes into application frame, z, and spatial dimensions.

## Annotation CSV

Canonical annotation rows include image name, time index, z index, y coordinate,
x coordinate, label, source, and metadata fields. Legacy CSV files with only
coordinate columns are normalized during import.

## Annotation JSON

JSON exports preserve richer metadata and are preferred when downstream tools
need annotation IDs, review state, or provenance.

## Project files

Project files preserve image links, annotations, suggestions, display state,
review state, QC configuration, SMLM metadata, and workspace layout. Schema
migration code supplies safe defaults for older files.

## Fiji plugin manifests

External plugin manifests describe plugin parameters, execution behavior, and
argument conversion so Fiji workflows can be launched reproducibly.
