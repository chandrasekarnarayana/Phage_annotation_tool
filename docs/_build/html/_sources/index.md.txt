# Phage Annotator

Phage Annotator is a scientific desktop application for microscopy keypoint
annotation, assisted review, SMLM bridge validation, and reproducible project
state management. The documentation is organized like a scientific Python
project: start with installation and tutorials, then move into user guides,
architecture, deployment, and API reference.

```{toctree}
:maxdepth: 2
:caption: Getting started

user_guide/overview
user_guide/installation
user_guide/quickstart
tutorials/annotation_workflow
```

```{toctree}
:maxdepth: 2
:caption: User guide

user_guide/interface
user_guide/annotations
user_guide/assisted_review
user_guide/qc
user_guide/smlm
user_guide/deepstorm
user_guide/density
user_guide/projects
```

```{toctree}
:maxdepth: 2
:caption: Developer guide

development/architecture
development/modularity
development/testing
development/documentation
development/contributing
```

```{toctree}
:maxdepth: 2
:caption: Deployment and reference

deployment/environment
deployment/runtime
deployment/release
reference/features
reference/keyboard_shortcuts
reference/file_formats
api/index
release_notes/index
```

## Documentation goals

The documentation follows the conventions used by Matplotlib and scikit-learn:

- narrative tutorials explain complete workflows;
- user-guide pages describe concepts and everyday operations;
- developer pages explain architecture, testing, extension points, and
  maintenance rules;
- API pages are generated from source-code docstrings so implementation details
  and public reference material stay close together;
- deployment pages describe environment files, startup checks, and release
  validation.

## Build the HTML site

Install the documentation dependencies, generate API pages, then build HTML:

```bash
python -m pip install -r docs/requirements.txt
make -C docs html
```

The generated site is written to `docs/_build/html/index.html`.
