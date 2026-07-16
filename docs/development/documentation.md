# Documentation Workflow

The documentation is a Sphinx site with Markdown source pages and generated API
reference pages.

## Build commands

```bash
python -m pip install -r docs/requirements.txt
make -C docs html
```

The `api` target runs `docs/tools/generate_api_reference.py`, which scans
`src/phage_annotator` and writes module pages under `docs/api/generated`.

## Writing style

Follow the style of Matplotlib and scikit-learn:

- start with a concept before listing options;
- show commands in copyable code blocks;
- prefer concrete workflow examples;
- link to API pages for exact signatures;
- keep reference pages factual and versionable.

## API documentation

API pages are generated from docstrings using Sphinx autodoc and autosummary.
This means code docstrings are part of the documentation contract. When a public
function changes behavior, update its docstring in the same change.

## HTML output

Generated HTML lives in `docs/_build/html`. It should not be edited by hand.
