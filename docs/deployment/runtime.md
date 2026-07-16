# Runtime Behavior

Phage Annotator is a desktop application with background services for jobs,
status updates, logging, caching, and long-running scientific workflows.

## Startup checks

At startup the application validates key runtime dependencies against the
environment manifest. Warnings should be clear and actionable.

## Memory management

Large microscopy data is handled through lazy readers, projection caches,
compressed disk cache support, and chunked export. Cache defaults are bounded by
the runtime spec and can be overridden with environment variables.

## Worker limits

Worker thread counts are capped so background analysis does not starve the GUI.
Long-running jobs should report progress and return control to the event loop.

## Logs

Runtime action logs are stored under `docs/reports` by default. Generated logs
are operational artifacts and should not be treated as hand-written
documentation.
