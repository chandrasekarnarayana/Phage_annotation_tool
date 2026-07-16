# Projects and Workspace State

Project files preserve work across sessions. They are designed to survive path
changes, schema evolution, and multi-modal review workflows.

## What is saved

A project can store:

- image paths and relink metadata;
- annotations and annotation import records;
- pending suggestions and suggestion history;
- display settings and modality links;
- active annotation and generation spaces;
- QC configuration and issue state;
- SMLM runbook metadata;
- workspace layout and panel state.

## Relinking

If images move, project load can relink data by path, image name, and project
metadata. Relink reports are stored in session state for user review.

## Schema migration

Project persistence includes migration hooks so older project files can be
opened by newer versions. New fields should have safe defaults and should not
break legacy sessions.
