# SMLM and Fiji Bridge

The SMLM subsystem provides single-molecule localisation microscopy analysis
through three independent execution paths. Choose the backend that best fits
your environment and accuracy requirements.

## Execution backends

### Internal Python pipeline

The default backend reimplements the ThunderSTORM algorithm in pure Python.
No Fiji installation is required.

**Pipeline stages:**

1. **Image filtering** — Wavelet B-spline (recommended) or Difference-of-Gaussians.
2. **Candidate detection** — Local intensity maxima above a MAD-based threshold.
3. **Gaussian fitting** — Symmetric 2D Gaussian fit for sub-pixel coordinates and precision.
4. **Post-filtering** — Reject detections below minimum photon count or above maximum uncertainty.
5. **Merging** — Merge multi-frame emitters within a configurable radius.
6. **SR rendering** — Histogram or Gaussian scatter super-resolution image.

### Fiji subprocess bridge

Spawns a headless Fiji process and runs a ThunderSTORM ImageJ macro. The
ThunderSTORM JAR is bundled with the software — no separate download is needed.

**Setup:**

1. Download and install [Fiji](https://fiji.sc) for your operating system.
2. Open the SMLM panel → **Execution Backend**.
3. The Fiji executable field is auto-populated if Fiji is found in a standard location.
4. Run **Preflight check** to validate the configuration before a full analysis run.

**Platform-standard Fiji locations (auto-discovery):**

- **Linux**: `~/Fiji.app`, `/opt/Fiji.app`, `/usr/local/Fiji.app`
- **macOS**: `/Applications/Fiji.app`, `~/Applications/Fiji.app`
- **Windows**: `C:\Fiji.app`, `%ProgramFiles%\Fiji.app`

Override auto-detection by setting the `FIJI_EXECUTABLE` environment variable to
the full path of the Fiji binary, or `FIJI_APP` to the `Fiji.app` directory.

### PyImageJ bridge

Runs Fiji in-process via the PyImageJ / JPype JVM bridge.
Install the optional dependency group first:

```bash
pip install "phage-annotator[fiji]"
```

Set the **PyImageJ app path** to your `Fiji.app` directory in the SMLM panel.

## Key parameters

| Parameter | Typical range | Description |
| --- | --- | --- |
| Pixel size | 50–200 nm/px | Camera pixel pitch ÷ objective magnification |
| PSF sigma | 0.8–2.5 px | Expected PSF σ ≈ 0.21 × λ / (NA × pixel_size_nm) |
| Detection threshold | 1.5–5 MAD σ | Lower = more detections, higher false-positive rate |
| Fit radius | 3–6 px | Gaussian fitting half-window (≥ 2 × PSF σ recommended) |
| Min photons | 25–500 | Minimum integrated photon count to accept a localisation |
| Max uncertainty | 5–50 nm | Maximum localisation precision (Cramér–Rao bound estimate) |
| Merge radius | 0.5–2 px | Merge threshold across consecutive frames |
| Upsample factor | 4–10 | SR pixel size = camera pixel size ÷ upsample |

## Preflight

Validate the Fiji bridge configuration before a full run:

```bash
phage-annotator-smlm-preflight
```

Preflight verifies the executable path, macro file, plugin JAR, and bridge
configuration readiness.

## Parity validation

Compare the internal pipeline against the Fiji bridge on the same dataset:

```bash
phage-annotator-smlm-parity
```

Parity output reports precision, recall, and mean XY error (px) at a
configurable matching tolerance. Use this to confirm equivalent results
when switching backends or upgrading ThunderSTORM.

## Reproducibility

Enable **Runbook mode** in the SMLM panel to capture the complete parameter set,
executed macro text, and bridge metadata alongside every result set.

Export a runbook bundle for audit or replication:

```bash
phage-annotator-smlm-run-demo --runbook <runbook_file>
```

## External plugin manifests

Third-party Fiji plugins can be registered via JSON manifests in the
`external_plugins/` directory. The manifest declares the plugin command,
menu path, parameter schema, and I/O contract so the GUI presents
appropriate controls and builds reproducible macro invocations automatically.

```bash
phage-annotator-fiji-plugin-tool --list
phage-annotator-fiji-plugin-tool --validate Thunder_STORM.json
```
