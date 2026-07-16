# Architecture

Phage Annotator uses a layered architecture to keep scientific logic testable
and the GUI responsive.

## Layers

### Core layer

The core layer contains dataclasses, serialization helpers, state models, and
pure business rules. It must not import Qt. Core modules should be usable from
CLI tools, tests, and batch jobs.

### Data and IO layer

The data layer provides lazy image access, display mappings, data-source
interfaces, and ring-buffer behavior. The IO layer handles metadata, image
readers, annotation formats, and project files.

### Analysis layer

The analysis layer contains candidate generation, feature extraction,
interactive learning, suggestion ranking, QC validators, thresholding, and
scientific algorithms.

### Session layer

The session layer owns mutable application state. It coordinates annotations,
suggestions, view state, project persistence, modality state, undo/redo, and
signals through explicit commands and state-owner modules.

### UI layer

The Qt layer owns widgets, panels, actions, rendering integration, worker
services, and user feedback. It may call session and analysis services, but core
and analysis modules should not depend on Qt.

## Dependency direction

Dependencies should flow inward:

```text
ui_qt -> session -> analysis/data/io -> core
```

Reverse dependencies are architecture violations unless an explicit protocol or
callback boundary is introduced.

## State mutation discipline

Direct writes to session state are restricted to state-owner modules. Tests in
`tests/unit/architecture` scan for accidental mutation leaks, direct signal
emits, and annotation writes outside approved modules.

## Rendering and memory

Rendering uses Matplotlib and array utilities, but large data should flow
through lazy readers, caches, and chunked export helpers. Full-frame copies
should be avoided unless the workflow genuinely requires them.
