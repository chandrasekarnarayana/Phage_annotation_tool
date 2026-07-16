# Installation

Phage Annotator supports editable development installs, Conda/Mamba
environments, and optional Fiji bridge dependencies.

## Python requirements

The package requires Python 3.9 or newer. The main runtime dependencies are
NumPy, pandas, Matplotlib, Qt, tifffile, SciPy, scikit-image, scikit-learn,
lmfit, QtAwesome, and Simple Icons.

## Editable install

```bash
python -m venv .venv-phage
source .venv-phage/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev,cache]
```

On Windows PowerShell:

```powershell
python -m venv .venv-phage
.venv-phage\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev,cache]
```

## Conda or Mamba

The canonical environment file lives in `project/environment.yml`.

```bash
conda env create -f project/environment.yml
conda activate phage-annotator
python -m pip install -e .[dev,cache]
```

The application checks this environment manifest at startup and reports missing
or stale runtime packages before the GUI launches.

## Optional Fiji bridge dependencies

```bash
python -m pip install -e .[fiji]
```

Use the SMLM preflight CLI to validate the Fiji bridge environment:

```bash
phage-annotator-smlm-preflight
```

## Documentation dependencies

```bash
python -m pip install -r docs/requirements.txt
make -C docs html
```

The HTML documentation is written to `docs/_build/html`.
