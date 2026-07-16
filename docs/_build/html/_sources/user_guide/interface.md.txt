# Interface Guide

The GUI is organized as a central canvas with docked panels. The layout is meant
for repeated scientific review: common operations are keyboard accessible,
panels are dense but scannable, and long-running work is dispatched outside the
paint path.

## Main canvas

The central canvas renders the active frame or projection. It displays image
data, annotations, ROI overlays, particle overlays, optional scale bars, and
review context overlays.

## Panels

Important panels include:

- annotation table for committed keypoints;
- review queue for candidate suggestions;
- explain panel for suggestion evidence;
- QC issue panel for validator output;
- threshold and particle panels for preprocessing;
- SMLM panel for ThunderSTORM and Fiji bridge workflows;
- performance panel for cache and memory telemetry.

## Responsiveness model

The GUI should never perform large image computation directly in interactive
event handlers. Expensive work belongs in jobs, services, caches, or chunked
render/export helpers. UI code coordinates commands and refreshes views.

## Status and logging

User-visible status updates are routed through status services. Action logs are
written under `docs/reports` by default so runtime logging does not pollute the
repository root.
