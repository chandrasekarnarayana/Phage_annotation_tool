# Phage Annotator

Phage Annotator is a Qt + Matplotlib microscopy annotation IDE for 2D/3D/time TIFF workflows, with assistive suggestion review, reproducible project persistence, and dock-based expert UX.

## Clone

```bash
git clone https://github.com/<your-org-or-user>/phage-annotator.git
cd phage-annotator
```

## Run with Docker (recommended — isolated, no system changes)

Docker keeps Python, PyQt5, Qt's system libraries, and the full scientific
stack inside a container, so nothing is installed on the host and the exact
same environment runs on Linux and Windows.

**Prerequisites:** Docker Desktop (Windows/macOS) or Docker Engine + the
Compose plugin (Linux). On Windows, enable the WSL2 backend in Docker Desktop
(default since 2021) — this also gives GUI passthrough via WSLg with no extra
setup.

**Launch the GUI — Linux:**

```bash
xhost +local:docker
docker compose up app
```

**Launch the GUI — Windows** (run from a WSL2 terminal, e.g. Ubuntu on WSL,
with Docker Desktop's WSL2 integration enabled for that distro):

```bash
docker compose up app
```

WSLg (built into Windows 11 and current Windows 10 WSL updates) supplies
`DISPLAY` and the X11 socket automatically. If your Windows build predates
WSLg, install an X server such as VcXsrv, launch it with "Disable access
control", and set `DISPLAY=host.docker.internal:0.0` before running
`docker compose up app`.

Annotation projects, exports, and demo TIFFs persist under `./data` on the
host — the container itself is fully disposable and can be rebuilt or removed
at any time without losing work.

**Run the CLI without a GUI:**

```bash
docker compose run --rm app --help
```

**Verify the install is functional, in full isolation from your host Python:**

```bash
docker compose run --rm test
```

This builds a separate image with the `dev` extras and runs the full non-GUI
test suite headlessly (`QT_QPA_PLATFORM=offscreen`).

**Build/run manually, without Compose:**

```bash
docker build -t phage-annotator .
docker run --rm phage-annotator --help
```

Optional extras (`dev`, `ml`, `fiji`, `cache`) can be layered in at build
time:

```bash
docker build --build-arg EXTRAS=cache,ml -t phage-annotator:ml .
```

The Fiji bridge backends (`fiji_subprocess`, `fiji_pyimagej`) call an
external Fiji/ImageJ installation and are not bundled in the image; mount a
host Fiji install into the container and point the SMLM panel at it if you
need those backends.

## Native Install (without Docker)

Prefer this path if you already manage Python environments yourself, or need
`.venv-phage` for editor/IDE integration.

### Linux / macOS

```bash
python -m venv .venv-phage
source .venv-phage/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev,cache]
```

### Windows (PowerShell)

```powershell
python -m venv .venv-phage
.venv-phage\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev,cache]
```

### Conda / Mamba

```bash
conda env create -f project/environment.yml
conda activate phage-annotator
python -m pip install -e .[dev,cache]
```

The application checks `project/environment.yml` at startup and prints environment
warnings before the GUI launches if required runtime packages are missing or too
old.

### Optional Fiji bridge dependencies

```bash
python -m pip install -e .[fiji]
```

### Offline / Air-gapped Install

If your environment cannot reach package indexes:

```bash
python -m pip install -U pip setuptools wheel
python -m pip install -e . --no-build-isolation
```

## Run (native install)

```bash
phage-annotator
```

If the entrypoint command is not found:

```bash
python -m phage_annotator.cli
```

## Verify Install (native)

```bash
phage-annotator --help
python -m pytest -q --maxfail=1
```

For GUI-marker tests (`-m gui`), install dev extras first so `pytest-qt` is available:

```bash
python -m pip install -e .[dev,cache]
```

## Current Capabilities

- Central multi-view canvas for stack/projection annotation.
- VS Code-style dock architecture with panel switcher and layout presets.
- Annotation table + review queue + explain panel workflows.
- Assisted suggestions with heuristic and calibrated `p_accept` semantics.
- Undo/redo, command palette, keyboard-first review (`A/R/N/P`, etc.).
- Project save/load with schema migration support.
- Annotation import/export (legacy CSV, ThunderSTORM CSV parse, JSON).
- QC issue detection and navigation.
- Selectable ThunderSTORM backends (`internal`, `fiji_subprocess`, `fiji_pyimagej`).
- SMLM parity CLI (`phage-annotator-smlm-parity`) for internal-vs-Fiji comparisons.
- SMLM preflight CLI (`phage-annotator-smlm-preflight`) for runtime readiness checks.
- SMLM demo-run CLI (`phage-annotator-smlm-run-demo`) for deterministic smoke tests.
- Fiji plugin toolkit CLI (`phage-annotator-fiji-plugin-tool`) for manifest onboarding.

See [docs/user_guide/overview.md](docs/user_guide/overview.md) for a narrative walkthrough, or `docs/release_notes/index.md` for versioned change history.

## Production Validation Commands

```bash
.venv-phage/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen .venv-phage/bin/python -m pytest -m gui --run-gui
```

## Documentation

The documentation is a Sphinx site in `docs`, with narrative guides in Markdown
and API pages generated from source docstrings.

```bash
python -m pip install -e .[docs]
make -C docs html
```

Open `docs/_build/html/index.html` after building. Start from
`docs/index.md` for the source table of contents.

## Notes

- Fiji bridge mode executes JAR plugins through Fiji/ImageJ; configure executable + macro in the SMLM panel.
- If a CLI entrypoint is not found, reinstall in the active environment: `python -m pip install -e .`
- For release hygiene, generated artifacts (`*.egg-info`) and large demo binaries are intentionally not tracked.
- `Dockerfile` / `docker-compose.yml` at the repo root define the isolated container environment described in "Run with Docker" above.
