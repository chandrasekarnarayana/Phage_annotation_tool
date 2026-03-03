# ThunderSTORM JAR Integration Status & Gap Analysis

## Update (Operational Hardening Applied - March 2, 2026)

The bridge has moved from framework-complete to operationally hardened:

- Bundled default macro is shipped and auto-resolved (`external_plugins/thunderstorm_macro.ijm`).
- Strict manifest is shipped (`external_plugins/Thunder_STORM.json`) with typed parameters and CSV schema guardrails.
- `plugins.config` is parsed from JAR for command discovery and diagnostics.
- Preflight supports active probe mode (`--probe`) with deterministic exit codes:
  - `0` ok, `2` Fiji not runnable, `3` plugin not discoverable, `4` macro execution failed, `5` output marker missing.
- Backend errors are typed and actionable (`FijiNotFoundError`, `FijiTimeoutError`, `CSVSchemaMismatchError`, etc.).
- UI now includes an execution/debug plan panel with copyable diagnostics and generated macro visibility.
- Bridge failure path includes recovery actions (open logs, open error folder, copy report, retry internal backend).
- Integration invariants were strengthened for the optional Fiji E2E test.

Remaining runtime dependency: true E2E success still requires a real local Fiji installation configured via `FIJI_APP_PATH`/`FIJI_EXE_PATH`.

**Document Date:** March 2, 2026  
**JAR Artifact:** `external_plugins/Thunder_STORM.jar` (8.8 MB, verified valid)  
**Integration Framework:** Implemented with three execution backend modes  

---

## Executive Summary

The integration framework is **substantially implemented** with backend adapters, plugin discovery, and preflight validation. However, the integration is **not yet end-to-end functional** because:

1. **No Fiji macro provided** for ThunderSTORM.jar subprocess invocation
2. **No parity validation** against reference Fiji ThunderSTORM outputs
3. **Limited runtime testing** (PyImageJ mode untested; subprocess mode structure complete but not exercised with actual JAR)
4. **Documentation gaps** (how to use, expected outputs, troubleshooting)

---

## Current Integration Status

### ✅ Fully Implemented

#### 1. **Plugin Discovery & Inventory**
- **File:** `src/phage_annotator/smlm/external_plugins.py`
- **Functions:**
  - `discover_external_fiji_plugins()` — Scans `external_plugins/` for `*.jar` files + optional JSON manifests
  - `parse_plugins_config_from_jar()` — Extracts `plugins.config` metadata from JAR
  - `resolve_plugin_jar()` — Resolves JAR path from descriptor or manual override
  - `resolve_plugin_descriptor()` — Retrieves plugin metadata by ID

**Status for Thunder_STORM.jar:**
```
Plugin ID:        thunder_storm  (auto-derived from filename)
JAR Path:         external_plugins/Thunder_STORM.jar ✅ EXISTS (8.8 MB)
plugins.config:   Found ✅
Menu Entries:     Plugins>ThunderSTORM/*  (calibration, analysis, visualization, import/export...)
Commands:         "Run analysis", "Camera setup", "Visualization", etc.
Manifest:         None (legacy plugin, no strict JSON manifest required)
```

#### 2. **Backend Configuration & Dispatch**
- **File:** `src/phage_annotator/smlm/backends.py`
- **Class:** `ThunderstormBridgeConfig` (frozen dataclass)
  
**Supported backends:**
| Backend | Status | Requirements |
|---------|--------|--------------|
| `internal` | ✅ Native Python SMLM | None (no Fiji needed) |
| `fiji_subprocess` | ⚠️ Framework ready | Fiji executable + macro PATH |
| `fiji_pyimagej` | ⚠️ Framework ready | Fiji.app location + `imagej` package |

**Dispatch function:**
- `run_thunderstorm_backend()` — Routes to appropriate backend, standardizes outputs

#### 3. **Subprocess Backend (Fiji Headless)**
- **Function:** `_run_fiji_subprocess()` in `backends.py`

**Execution pipeline:**
1. Materializes frame stack from stream iterator
2. Writes temporary TIFF (`input_stack.tif`)
3. Serializes parameters to JSON (`params.json`)
4. **Builds Fiji command** (needs macro path)
5. Launches subprocess with environment variables:
   - `PHAGE_SMLM_INPUT` → input TIFF path
   - `PHAGE_SMLM_OUTPUT` → expected output CSV path
   - `PHAGE_SMLM_PARAMS_JSON` → parameters JSON
   - `PHAGE_PLUGIN_JAR` → ThunderSTORM.jar path
   - Plugin-specific env vars

6. Captures exit code, stdout, stderr
7. Parses output CSV via `parse_thunderstorm_csv()`
8. Renders super-resolution image
9. Returns normalizedalizations + metadata

**Code Status:** ✅ Complete and syntactically correct  
**Runtime Status:** ⚠️ **UNTESTED** — Requires valid Fiji macro to proceed

#### 4. **PyImageJ Backend (In-Process)**
- **Function:** `_run_fiji_pyimagej()` in `backends.py`

**Execution pipeline:**
1. Initializes PyImageJ runtime once (singleton pattern)
2. Creates temp macro from manifest or provided macro path
3. Executes macro via `ij.eval()` or `ij.script()` (framework supports both)
4. Captures results from temp output directory
5. Parses and normalizes like subprocess backend

**Code Status:** ✅ Framework complete  
**Runtime Status:** ❌ **UNTESTED** — Requires actual PyImageJ invocation testing

#### 5. **Preflight Validation**
- **File:** `src/phage_annotator/smlm/preflight.py`
- **Function:** `run_preflight(config: ThunderstormBridgeConfig) → PreflightReport`

**Checks performed:**
- ✅ Fiji executable path exists and is runnable
- ✅ PyImageJ app path exists
- ✅ Plugin JAR exists
- ✅ Macro file exists (or plugin has manifest for auto-generation)
- ✅ Temp directory writable
- ⚠️ plugins.config commands present (warns if missing, but non-fatal)

**Integration:**
- Called from UI before execution
- Produces human-readable report with pass/fail per check
- Display in SMLM panel

#### 6. **UI Integration**
- **File:** `src/phage_annotator/smlm/widget.py`
- **Class:** `SmlmDockWidget` — Parameter panel with fields:
  - Backend selector dropdown (internal | fiji_subprocess | fiji_pyimagej)
  - Plugin combo (auto-populated from discovery)
  - Fiji executable path
  - Fiji macro path
  - ThunderSTORM JAR path
  - Command template (with placeholders for input/output/params)
  - PyImageJ app path
  - Reproducibility mode checkbox

- **File:** `src/phage_annotator/ui_qt/controls/smlm.py`
- **Method:** `_run_smlm()` — Orchestrates backend invocation
  - Reads config from UI
  - Applies reproducibility/runbook rules
  - Dispatches to backend
  - Collects localizations, renders SR image
  - Displays progress/results in status bar

---

### ⚠️ Partially Implemented / Untested

#### 1. **Fiji Macro Generation & Invocation**

**Current state:**
- Framework supports two invocation modes:
  a) **User-provided macro** — Path in UI, passed to Fiji with substitutions
  b) **Manifest-driven macro** — Auto-generated from plugin JSON manifest (not yet used for Thunder_STORM.jar)

**Issue:** Thunder_STORM.jar has no strict JSON manifest, is a legacy plugin. Requires **user-provided macro** OR manual stub macro.

**What's needed:**
- A macro file invoking ThunderSTORM "Run analysis" command
- Example structure:
  ```ijm
  open("${PHAGE_SMLM_INPUT}");
  run("Run analysis", "param1=value1 param2=value2 ...");
  saveAs("Results", "${PHAGE_SMLM_OUTPUT}");
  ```

#### 2. **Manifest-Based Plugin Definition**

**Current state:**
- Code supports optional JSON manifest for strict plugin contracts
- Structure defined in `PluginExecutionManifest` dataclass
- Can auto-generate macros from manifest + plugin parameters

**Status for Thunder_STORM.jar:**
- JAR is legacy (no strict manifest)
- Could create `external_plugins/Thunder_STORM.json` to enable manifest-driven invocation
- Would unlock fully automated parameter passing

#### 3. **Output Parsing & Localization Normalization**

- **Function:** `parse_thunderstorm_csv()` in `src/phage_annotator/io/readers/annotations.py`
- **Status:** ✅ Implemented and unit-tested
- **Handles:** Column mapping, unit conversions (px → nm), frame/z fields
- **Assumption:** Output CSV has standard ThunderSTORM format (x, y, frame, intensity, etc.)

---

### ❌ Missing / Not Implemented

#### 1. **No Example Fiji Macro**
**Blocking Issue:** Cannot invoke ThunderSTORM without macro  
**Effort:** Medium (1–2 hours to write + test macro, document expected CSV columns)

#### 2. **No Parity Validation Suite**
**Purpose:** Verify localizations from phage_annotator match Fiji ThunderSTORM outputs  
**Current Gap:** No reference dataset or comparison harness  
**Effort:** High (design test framework, gather reference data, build comparison metrics)

#### 3. **No Error Handling/Retry Logic**
**Current:** Subprocess failures immediately raise exception  
**Missing:**
- Retry on timeout
- Graceful degradation to internal backend
- Detailed error messages for common failures (Fiji crash, out of memory, etc.)

**Effort:** Medium (2–4 hours)

#### 4. **No Documentation**
**Missing:**
- User guide for "How to run ThunderSTORM bridge mode"
- Expected CSV column format from macro
- Troubleshooting: common Fiji errors
- Macro template for custom parameters

**Effort:** Low–Medium (1–2 hours)

#### 5. **No Integration Tests**
**Current:** Unit tests exist for CSV parsing and parameter validation  
**Missing:**
- End-to-end test: subprocess Fiji invocation (requires Fiji installed)
- PyImageJ initialization test
- Output parity checks (internal vs. subprocess localizations)

**Effort:** Medium–High (4–6 hours, depends on CI environment)

---

## How ThunderSTORM JAR Integrates Today

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ USER: Select Backend + Fiji Paths + ThunderSTORM.jar Path   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ SMLM Panel: Preflight Checks (paths exist, Fiji runnable)   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ _run_smlm(): Load parameters, configure bridge               │
└─────────────────────────────────────────────────────────────┘
                              ↓
                  ┌───────────┴───────────┐
                  ↓                       ↓
       ┌──────────────────┐   ┌──────────────────┐
       │ internal backend │   │ fiji_subprocess  │
       │ (no JAR needed)  │   │ (uses JAR below) │
       └──────────────────┘   └──────────────────┘
                                       ↓
                    ┌──────────────────────────────┐
                    │ Materialize frame stack      │
                    │ Write temp TIFF + params.json│
                    └──────────────────────────────┘
                                    ↓
                    ┌──────────────────────────────┐
                    │ Build Fiji headless command  │
                    │ + environment variables      │
                    │ (references Thunder_STORM.jar)
                    └──────────────────────────────┘
                                    ↓
                    ┌──────────────────────────────┐
                    │ SUBPROCESS: Fiji --headless   │
                    │ Load Thunder_STORM.jar        │
                    │ Run macro → localizations CSV │
                    └──────────────────────────────┘
                                    ↓
                    ┌──────────────────────────────┐
                    │ Parse CSV → Keypoint objects │
                    │ Normalize to internal schema │
                    └──────────────────────────────┘
                                    ↓
                    ┌──────────────────────────────┐
                    │ Render SR image              │
                    │ Append to annotation session │
                    └──────────────────────────────┘
```

### Key Integration Points

| Component | File | Role |
|-----------|------|------|
| **Plugin Discovery** | `smlm/external_plugins.py` | Finds Thunder_STORM.jar, parses plugins.config |
| **Backend Config** | `smlm/backends.py` | Holds paths, selects executor (internal/subprocess/pyimagej) |
| **Subprocess Executor** | `smlm/backends.py:_run_fiji_subprocess()` | Launches Fiji, reads results |
| **CSV Parser** | `io/readers/annotations.py:parse_thunderstorm_csv()` | Converts Fiji output to Keypoint objects |
| **SR Rendering** | `algorithms/smlm_thunderstorm.py:render_sr_image()` | Builds final super-resolution image |
| **UI Launcher** | `ui_qt/controls/smlm.py:_run_smlm()` | Start button, status updates, result display |
| **Preflight Checks** | `smlm/preflight.py` | Validates Fiji is available before run |

---

## Detailed Gap Analysis

### Gap 1: No Fiji Macro for ThunderSTORM
**Impact:** ⚠️ HIGH — Blocks subprocess backend entirely  
**Severity:** Critical

**Current State:**
- Code looks for `config.macro_path` (user-provided macro)
- If missing and no manifest, raises exception

**Resolution Path:**
1. **Option A (Recommended):** Create a simple macro file
   - Location: `external_plugins/thunderstorm_default.ijm`
   - Content: Open input TIFF, run "Run analysis", export CSV
   - Effort: 1–2 hours (write, test with actual Fiji, debug any CSV format issues)

2. **Option B:** Create strict JSON manifest
   - Location: `external_plugins/Thunder_STORM.json`
   - Define all parameters, run command, output format
   - Effort: 2–4 hours (research ThunderSTORM API, strict validation)
   - Benefit: Enables fully automated parameter control

3. **Option C:** Document manual invocation
   - Effort: 1 hour (write guide, screenshots)
   - Benefit: Unblocks user, but less automation

**Recommendation:** Implement **Option A + document** (3 hours total)

---

### Gap 2: No Parity Testing Against Fiji ThunderSTORM
**Impact:** ⚠️ HIGH — Cannot validate correctness  
**Severity:** High

**Current State:**
- CSV parser exists, but untested on real Fiji ThunderSTORM output
- Internal backend has mathematical differences from Fiji (filter order, rendering kernel, etc.)

**Validation Needed:**
- Run Fiji ThunderSTORM on reference dataset
- Run phage_annotator on same dataset (both backends)
- Compare localizations:
  - Spatial overlap (pixel precision)
  - Count differences
  - Intensity/photon agreement
  - Frame assignment

**Resolution Path:**
1. Gather reference SMLM dataset (synthetic or real)
2. Generate Fiji ground truth via subprocess invocation
3. Write parity harness (`tests/integration/test_thunderstorm_parity.py`)
4. Document acceptable delta thresholds
5. Add to CI pipeline

**Effort:** 4–8 hours (depending on reference data availability)

---

### Gap 3: No Error Handling/Graceful Degradation
**Impact:** ⚠️ MEDIUM — Poor user experience on Fiji failures  
**Severity:** Medium

**Current State:**
- Subprocess errors immediately raise exception
- No retry, no fallback, no detailed diagnostics

**Missing:**
- Timeout handling (Fiji hangs)
- Out-of-memory detection
- Macro execution failures (syntax error in macro, missing Fiji plugin)
- CSV format validation (unexpected columns)

**Resolution Path:**
1. Add rich exception types (e.g., `FijiTimeoutError`, `FijiPluginNotFoundError`)
2. Implement retry logic for transient failures
3. Add fallback offer: "Fall back to internal backend?"
4. Detailed error messages with remedies

**Effort:** 2–4 hours

---

### Gap 4: No Integration Tests
**Impact:** ⚠️ MEDIUM — Regressions undetected  
**Severity:** Medium

**Current State:**
- Unit tests for CSV parsing
- No end-to-end Fiji invocation tests

**Missing Test Cases:**
- Subprocess backend with actual Fiji (CI environment)
- PyImageJ backend (requires `imagej` package in CI)
- Output validation (compare CSV parsing before/after)
- Error scenarios (Fiji crash, bad macro, missing JAR)

**Effort:** 4–6 hours (infrastructure + test cases)

---

### Gap 5: Documentation
**Impact:** ⚠️ MEDIUM — Users cannot figure out how to use feature  
**Severity:** Medium

**Current State:**
- Code has docstrings
- No user-facing guide

**Missing Documentation:**
1. **User Guide** (`docs/THUNDERSTORM_BRIDGE_USER_GUIDE.md`)
   - How to set up Fiji executable path
   - How to provide (or auto-generate) macro
   - Expected CSV column format
   - Troubleshooting common errors

2. **Developer Guide** (`docs/THUNDERSTORM_BRIDGE_ARCHITECTURE.md`)
   - Plugin discovery algorithm
   - Backend abstraction
   - Macro generation from manifest
   - Output normalization

3. **Macro Template** (`external_plugins/thunderstorm_macro_template.ijm`)
   - Well-commented example
   - Shows expected parameter format
   - Documents how to adjust ThunderSTORM settings

**Effort:** 2–3 hours

---

## Remaining Work to "Fully Functional Product"

### Phase 1: Enable Subprocess Invocation (CRITICAL)
**Effort:** ~3 hours | **Blocking:** End-to-end workflow

- [ ] Create `external_plugins/thunderstorm_macro.ijm` with proper ThunderSTORM API calls
- [ ] Test macro manually in Fiji with reference dataset
- [ ] Update UI to auto-populate macro path if present
- [ ] Write minimal documentation

**Definition of Done:** User can select "fiji_subprocess" backend, provide JAR + macro paths, and get results

---

### Phase 2: Parity Validation (HIGH PRIORITY)
**Effort:** ~6 hours | **Blocking:** Confidence in results

- [ ] Gather or generate reference SMLM dataset
- [ ] Create parity test harness with metrics
- [ ] Document acceptable delta thresholds
- [ ] Document any known differences (internal vs. Fiji approaches)

**Definition of Done:** Test suite passes; documented accuracy bounds

---

### Phase 3: Error Handling & Robustness (MEDIUM PRIORITY)
**Effort:** ~3 hours | **Blocking:** Production readiness

- [ ] Rich exception types
- [ ] Retry logic for transients
- [ ] Fallback offers (switch to internal backend)
- [ ] Detailed error messages with remedies

**Definition of Done:** All error paths have user-friendly messages; no silent failures

---

### Phase 4: Integration Tests (MEDIUM PRIORITY)
**Effort:** ~4 hours | **Blocking:** CI/CD confidence

- [ ] Subprocess backend test (requires Fiji in CI)
- [ ] Output validation test
- [ ] Error scenario tests
- [ ] Macro parsing test

**Definition of Done:** CI runs tests; reports coverage

---

### Phase 5: Documentation (LOW PRIORITY)
**Effort:** ~2 hours | **Blocking:** User adoption

- [ ] User guide
- [ ] Developer guide
- [ ] Macro template with examples
- [ ] FAQ / troubleshooting

**Definition of Done:** New users can follow guide without support

---

## Questions & Ambiguities Remaining

### 1. **Macro Specification**
- **Q:** What are the exact parameter names and types expected by ThunderSTORM "Run analysis"?
- **A:** Available from plugins.config parsing (menu command name), but full parameter list needs exploration in Fiji
- **Action:** Run interactive Fiji with Thunder_STORM.jar, open "Plugins > ThunderSTORM > Run analysis", inspect dialog fields

### 2. **Output CSV Format**
- **Q:** What columns does ThunderSTORM CSV contain? (x, y, z, intensity, psf_size, offset, frame, etc.?)
- **A:** Partially documented in parser, but needs validation against actual Fiji output
- **Action:** Run Fiji on reference dataset, inspect CSV output, compare to parser expectations

### 3. **Pixel Size Calibration**
- **Q:** How does ThunderSTORM handle pixel size? Does macro accept nm/px argument?
- **A:** Not yet clear; may be embedded in Fiji settings or macro parameters
- **Action:** Test macro parameterization with different pixel sizes

### 4. **Memory/Performance Envelope**
- **Q:** How large a frame stack can Fiji handle? Are there memory constraints?
- **A:** Depends on Fiji heap settings, not yet known from our setup
- **Action:** Stress test with varying frame counts

### 5. **Macro Syntax & Fiji API**
- **Q:** Should macro use legacy ImageJ Macro language (.ijm) or SciJava script?
- **A:** plugins.config suggests legacy ImageJ plugins; macro should use .ijm
- **Action:** Reference Fiji documentation for "Run analysis" API

### 6. **PyImageJ Viability**
- **Q:** Is PyImageJ approach practical for ThunderSTORM, or should we stick with subprocess?
- **A:** Unknown; subprocess is simpler, but PyImageJ avoids subprocess overhead
- **Action:** Implement subprocess first; defer PyImageJ unless performance becomes issue

---

## Recommended Action Plan

### **Immediate (this week):**
1. ✅ Add JAR to repo — **DONE**
2. ✅ Document current state — **DONE (this document)**
3. Create example Fiji macro (2 hours)
4. Test macro with reference dataset (1.5 hours)

### **Short-term (next 2–3 weeks):**
1. Implement parity test harness (4 hours)
2. Add error handling + fallback logic (2 hours)
3. Write user guide + troubleshooting (2 hours)

### **Medium-term (next 1–2 months):**
1. Integration tests in CI (3 hours)
2. PyImageJ mode testing (if needed) (2 hours)
3. Performance profiling + optimization (2 hours)

---

## Summary Table

| Component | Status | Effort to Complete | Blocking? |
|-----------|--------|---------------------|-----------|
| Plugin discovery | ✅ Done | 0 | No |
| Backend config | ✅ Done | 0 | No |
| Subprocess executor | ✅ Code ready | 3h (macro) | **YES** |
| CSV parser | ✅ Done | 0 | No |
| SR rendering | ✅ Done | 0 | No |
| UI integration | ✅ Done | 0 | No |
| **Fiji macro** | ❌ Missing | 2h | **CRITICAL** |
| Parity testing | ❌ Missing | 6h | High |
| Error handling | ⚠️ Partial | 3h | Medium |
| Integration tests | ❌ Missing | 4h | Medium |
| Documentation | ❌ Missing | 2h | Medium |

---

## Conclusion

The ThunderSTORM JAR integration framework is **production-ready in architecture** but requires **3–20 hours of work** to be fully functional:

- **Blocking issue:** No Fiji macro (3 hours to fix)
- **High-priority issues:** Parity validation, error handling, documentation (15 hours)
- **Nice-to-have:** Full test coverage, PyImageJ mode (6 hours)

With the macro in place and parity tests passing, users can confidently use the ThunderSTORM bridge mode as an alternative to the internal Python backend.
