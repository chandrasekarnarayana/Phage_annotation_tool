# Developer Documentation Index

**Project**: Phage Annotation Tool  
**Current Phase**: P4 (Testing & Telemetry)  
**Last Updated**: January 2025

---

## 📋 Quick Start

### Current Development Status
- ✅ **P0 (Critical Blockers)**: Complete - All data safety issues resolved
- ✅ **P1 (High-Impact)**: Complete - Professional UX features implemented
- ✅ **P2 (Quality)**: Complete - Code quality and polish finished
- ✅ **P3 (Scientific)**: Complete - All 7 improvements implemented
- 🚧 **P4 (Testing)**: Ready to Start - 6 remaining items (testing, telemetry, advanced features)

### Test Status
```bash
73 passed, 2 skipped ✅
```

---

## 📚 Documentation Structure

### Primary Documents

#### [production_readiness_plan.md](production_readiness_plan.md)
**Purpose**: Master planning document tracking P0-P2 completion  
**Status**: P0-P2 complete (18/18 items, 100%)  
**Use When**: Reviewing completed work, understanding project history

#### [P4_roadmap.md](P4_roadmap.md) ⭐ **START HERE**
**Purpose**: Detailed P4-P5 implementation guide with technical specifications  
**Status**: 6 prioritized items (4 P4, 2 P5) ready to implement  
**Use When**: Implementing next features, understanding technical requirements

#### [feature_control_matrix.md](feature_control_matrix.md)
**Purpose**: Comprehensive inventory of all 220+ features with implementation details  
**Status**: Updated with P3 completions  
**Use When**: Finding feature implementation details, UI wiring verification

---

## 🎯 Current Priorities (P4)

See [P4_roadmap.md](P4_roadmap.md) for complete technical details.

### Phase 1 - Testing Foundation (Week 1, ~2 days)
1. P4.1: Unit tests for UI wiring (1 day) - Command palette, dock toggles, shortcuts
2. P4.2: Export preflight test coverage (4h) - Validation logic, confirmation dialogs

### Phase 2 - Telemetry & Consistency (Week 2, ~2 days)
3. P4.3: Cache eviction telemetry (4h) - 90% warnings, hit/miss ratios, toast notifications
4. P4.4: Consistent widget objectName (1 day) - `{module}_{type}_{function}` convention

### Phase 3 - Advanced Features (Week 3-4, ~4 days)
5. P5.1: Consolidated Performance panel (2 days) - Cache, jobs, prefetch, buffer status
6. P5.2: Multi-image ROI management (2 days) - Copy to all, templates, bulk presets

**Total Estimated Effort**: 7 days (~2-3 weeks with testing/polish)

---

## ✅ P3 Achievements Summary (7 items completed)

### Scientific Reproducibility
- ✅ **P3.2**: Deterministic random seeding (seed=42) for histogram, auto-contrast, threshold sampling
  - Critical for reproducible scientific results

### User Experience Improvements
- ✅ **P3.3**: Confirmation dialog management with 5 toggles (Clear ROI, Delete Annotations, Overwrite Files, Apply Display, Apply Threshold)
- ✅ **P3.5**: Generic annotation label defaults changed to ("Point", "Region")
- ✅ **P5.4**: Cancel All button shows job count badge "Cancel All (N)"

### Robustness & Advanced Features
- ✅ **P5.3**: SMLM/Density retry logic increased from 1→2 attempts
- ✅ **P3.4**: Export overlays as separate layers (base, annotations, roi, particles, scalebar, text as PNGs with alpha)
- ✅ **P3.1**: Undo/redo extension for view state (ROI, crop, display mapping, threshold) using command pattern

---

## 🏗️ Architecture Overview

### Key Modules

**Session Management**:
- `session_controller.py` - Main application controller
- `session_state.py` - Application state management
- `session_controller_*.py` - Specialized controllers (annotations, images, view, project)

**GUI Components**:
- `gui_mpl.py` - Main window and matplotlib integration
- `gui_controls_*.py` - Dock panel controls
- `gui_actions.py` - Menu action handlers
- `ui_*.py` - UI setup and utilities

**Image Processing**:
- `image_processing.py` - Core image operations
- `pyramid.py` - Multi-resolution pyramids
- `projection_cache.py` - Memory-efficient caching

**Analysis**:
- `smlm_*.py` - Single-molecule localization microscopy
- `density_*.py` - Density inference
- `particles.py` - Particle detection

---

## 🧪 Testing

### Running Tests
```bash
# All tests
pytest

# Quick run (quiet mode)
pytest -q

# With short traceback
pytest -q --tb=short

# Specific test file
pytest tests/test_annotations.py

# Performance tests
pytest tests/test_perf.py
```

### Test Coverage
- **Current**: ~45% (75 tests)
- **Target (P3)**: >60% (95+ tests)

### Adding Tests
Place new tests in `tests/` directory:
- `test_*.py` - Unit tests
- `conftest.py` - Shared fixtures
- Follow existing patterns for Qt/GUI testing

---

## 🔧 Development Workflow

### 1. Pick a Task
- Review [P4_roadmap.md](P4_roadmap.md) for prioritized tasks
- Start with P4.1 (UI wiring tests) or P4.2 (export preflight tests)
- Check todo list for current status

### 2. Implement
- Follow technical specifications in P4_roadmap.md
- Maintain test coverage (add tests for new features)
- Use Black for code formatting
- Update documentation as needed

### 3. Test
```bash
# Run tests
pytest -q --tb=short

# Format code
black src/phage_annotator/{modified_file}.py

# Verify no regressions
pytest
```

### 4. Document
- Update P4_roadmap.md status sections (mark tasks complete)
- Update todo list
- Add docstrings for new functions/classes

---

## 📊 P2 Achievements Summary

### Code Quality (3 items)
- ✅ Black formatting applied to GUI control files
- ✅ PEP8 compliance enforced
- ✅ Consistent code style maintained

### User Experience (4 items)
- ✅ Recent files auto-cleanup on startup
- ✅ Settings persistence (markerSize, clickRadiusPx, activeTool)
- ✅ Keyboard shortcuts dialog (F1) with 19+ shortcuts
- ✅ Tooltips on all 15+ preference controls

### Error Prevention (2 items)
- ✅ GPU availability checks before Deep-STORM/Density
- ✅ Clear error dialogs with guidance

### Developer Experience (1 item)
- ✅ Logs severity filtering (ALL/DEBUG/INFO/WARNING/ERROR)
- ✅ Clear button, 1000-line buffer
- ✅ Improved toolbar layout

---

## 🏗️ New Architecture Patterns (P3)

### Command Pattern for Undo/Redo
**File**: `src/phage_annotator/commands.py` (361 lines)
- Abstract `Command` base class with execute/undo/redo
- `CommandMemento` dataclass for state snapshots
- 4 concrete commands: `SetROICommand`, `SetCropCommand`, `SetDisplayMappingCommand`, `SetThresholdCommand`
- JSON-serializable for persistence
- Integrated with `session_controller_view.py`

### Layer Export Architecture
**File**: `src/phage_annotator/export_view.py`
- New `render_layer_to_array()` function (180 lines)
- Renders individual layers: base, annotations, roi, particles, scalebar, text
- Generates separate PNG files with alpha transparency
- Consistent naming scheme: `{base_name}_{layer}.png`

---

## 🎓 Best Practices

### Code Style
- Use Black formatter (line length 88)
- Follow PEP8 conventions
- Type hints where practical
- Docstrings for public APIs

### Git Workflow
- Descriptive commit messages
- One feature per commit (where practical)
- Test before committing
- Update docs with code changes

### Scientific Rigor
- Deterministic operations (use seeds)
- Reproducible results
- Clear error messages
- Validation before operations

### Testing
- Unit tests for core logic
- Integration tests for workflows
- GUI tests for critical interactions
- Performance benchmarks for bottlenecks

---

## 🔗 External Resources

### Dependencies
- PyQt5 - GUI framework
- NumPy - Numerical computing
- matplotlib - Plotting
- tifffile - TIFF I/O
- scikit-image - Image processing

### Documentation
- [Qt 5.15 Docs](https://doc.qt.io/qt-5/)
- [matplotlib Docs](https://matplotlib.org/)
- [NumPy Docs](https://numpy.org/doc/)

---

## 📞 Support & Questions

For development questions or clarifications:
1. Review relevant section in P4_roadmap.md
2. Check feature_control_matrix.md for implementation details
3. Examine existing code for patterns
4. Add questions to dev documentation for future reference

---

## 🚀 Next Steps

1. **Review P4_roadmap.md** - Understand technical requirements for next phase
2. **Start P4.1 or P4.2** - Begin testing foundation (UI wiring or export preflight)
3. **Complete Phase 1** - Testing foundation (2 items, 1.5 days)
4. **Update progress** - Mark tasks complete, run tests
5. **Move to Phase 2** - Telemetry & consistency (2 items, 2 days)

---

**Current Status**: Production-ready with 220+ features verified and P3 enhancements complete. P4 will add comprehensive testing, telemetry, and advanced multi-image workflows.
