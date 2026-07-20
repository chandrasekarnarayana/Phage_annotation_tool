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

### Step 1 — Install Docker

- **Windows/macOS:** install Docker Desktop, then enable the WSL2 backend
  (Windows, default since 2021) — this also gives GUI passthrough via WSLg
  with no extra setup.
- **Linux:** install Docker Engine + the Compose plugin. On Ubuntu, either
  `sudo apt install docker.io` or `sudo snap install docker` both work; the
  steps below call out where snap-installed Docker behaves differently.

### Step 2 — Let your user run `docker` without `sudo` (Linux only)

```bash
sudo usermod -aG docker "$USER"
newgrp docker    # or just log out and back in
```

If this prints `usermod: group 'docker' does not exist`, you're on the snap
package, which sets up permissions differently — skip this step and just use
`sudo docker ...` / `sudo docker compose ...` for every command below
instead. Both work; the only difference is who owns files Docker creates for
you (see Step 3).

### Step 3 — Create the data folder as yourself, before Docker does

```bash
cd phage-annotator     # or wherever you cloned it
mkdir -p data
```

Annotation projects, exports, and demo TIFFs persist under `./data` on the
host, and the app runs as a non-root user *inside* the container. If Docker
(or `sudo`) creates `./data` for you instead of you creating it first, it
ends up owned by root and the container can't write into it — you'll see
`PermissionError: [Errno 13] Permission denied: '/data/...'` the first time
the app tries to save something. Creating it yourself up front avoids that.

### Step 4 — Launch the GUI

**Linux:**

```bash
xhost +local:docker
docker compose up app
```

(prefix with `sudo` if you skipped Step 2)

**Windows** (run from a WSL2 terminal, e.g. Ubuntu on WSL, with Docker
Desktop's WSL2 integration enabled for that distro):

```bash
docker compose up app
```

WSLg (built into Windows 11 and current Windows 10 WSL updates) supplies
`DISPLAY` and the X11 socket automatically. If your Windows build predates
WSLg, install an X server such as VcXsrv, launch it with "Disable access
control", and set `DISPLAY=host.docker.internal:0.0` before running
`docker compose up app`.

The container is fully disposable — it can be rebuilt or removed at any time
without losing work, since everything you create lives in `./data` on the
host.

### Troubleshooting

**`permission denied while trying to connect to the docker API at
unix:///var/run/docker.sock`** — your user isn't authorized to talk to the
Docker daemon yet. Either finish Step 2, or prefix the command with `sudo`.

**`PermissionError: [Errno 13] Permission denied: '/data/...'`** — `./data`
is owned by someone other than the container's user (this happens if it got
auto-created while running under `sudo`). Fix the ownership directly; the
container always runs as uid 1000:

```bash
sudo chown -R 1000:1000 data
docker compose up app
```

No rebuild needed for this — it's a host-side fix only. If you ever want to
double-check the container's actual uid instead of trusting the 1000 above:

```bash
docker compose run --rm --entrypoint id app
```

**Nothing shows up on screen at all (no error, no window)** — check the
mount in `docker-compose.yml` isn't accidentally read-only or misconfigured:

```bash
grep -A3 volumes docker-compose.yml
```

It should show `- ./data:/data` (no trailing `:ro`).

### Other Docker commands

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
