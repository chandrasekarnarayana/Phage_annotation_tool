# Environment

Runtime environment metadata is stored under the `project` folder.

## Environment manifest

`project/environment.yml` is the canonical Conda/Mamba environment manifest.
The application checks this file at startup and reports runtime mismatches.

## Runtime specification

`project/runtime.spec.yml` describes startup policy and operational defaults:

- environment manifest path;
- worker thread cap;
- cache budget fraction and bounds;
- environment variable overrides.

## Documentation environment

Documentation dependencies are intentionally kept in `docs/requirements.txt`.
This avoids forcing Sphinx dependencies into minimal runtime installs.
