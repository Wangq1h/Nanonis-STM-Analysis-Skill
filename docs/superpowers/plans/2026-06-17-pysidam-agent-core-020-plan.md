# PySIDAM Agent Core 0.2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bundled `pysidam_agent_core` headless package and route gap fitting through it without PyQt5/pyqtgraph.

**Architecture:** Keep bridge scripts as CLI wrappers and move reusable numerical fitting into `pysidam_agent_core`. The core may use NumPy/SciPy and PySIDAM pure core models, but must not import PySIDAM GUI modules or Qt/pyqtgraph. Validation enforces the boundary.

**Tech Stack:** Python 3.10+, NumPy, SciPy, Matplotlib for plots, PySIDAM core model helpers, existing skill runtime resolver.

---

### Task 1: Validation Contract

**Files:**
- Modify: `scripts/validate_package.py`
- Create: `docs/releases/RELEASE_NOTES_v0.2.0.md`

- [x] Add required files for `pysidam_agent_core/__init__.py`, `io.py`, `models.py`, `numerics.py`, `gap_fitting.py`, and release notes.
- [x] Add validation that `pysidam_agent_core` and `scripts/pysidam_agent/fit_gap.py` do not import `PyQt5`, `pyqtgraph`, `QApplication`, or `pysidam.useful_tools.usefultools_deconvolution_point`.
- [x] Add validation that `fit_gap.py` imports `pysidam_agent_core.gap_fitting`.
- [x] Run `python3 scripts/validate_package.py` and confirm it fails before implementation.

### Task 2: Headless Core Package

**Files:**
- Create: `pysidam_agent_core/__init__.py`
- Create: `pysidam_agent_core/models.py`
- Create: `pysidam_agent_core/numerics.py`
- Create: `pysidam_agent_core/gap_fitting.py`
- Create: `pysidam_agent_core/io.py`

- [x] Implement model wrappers around `pysidam.core.superconducting_gap_models` only.
- [x] Implement numerical helpers for array normalization, resampling, feature weights, peak-derived starts, affine scale/offset, and guarded time budgets.
- [x] Implement `fit_gap_model_guarded` with JSON-friendly result schema and no GUI imports.
- [x] Implement lightweight `io.py` helpers for future reuse without moving bridge-specific plotting into core.

### Task 3: Bridge Migration

**Files:**
- Modify: `scripts/pysidam_agent/fit_gap.py`
- Modify: `references/task-cards/gap-fit-quick.md`
- Modify: `SKILL.md`, `README.md`, `references/fitting-recipes.md`, `references/pysidam-capability-index.json`, `references/pysidam-capability-map.md`, `CHANGELOG.md`

- [x] Change `fit_gap.py` to import `pysidam_agent_core.gap_fitting.fit_gap_model_guarded`.
- [x] Change probe output to report `fit_engine="pysidam_agent_core.gap_fitting.fit_gap_model_guarded"`.
- [x] Remove UI bootstrap guidance from the default gap fitting path.
- [x] Update documentation and release line to 0.2.0.

### Task 4: Runtime Verification

**Files:**
- No source edits unless verification finds an issue.

- [x] Run `python3 scripts/validate_package.py`.
- [x] Run `python3 scripts/pysidam_agent/fit_gap.py --probe-fitter`.
- [x] Run gap fitting on the clean test `.dat` files.
- [x] Build a temporary headless-only venv without `PyQt5/pyqtgraph`; run `fit_gap.py --probe-fitter` and one no-plot fit in that venv.
- [x] Sync installed skill and verify installed copy.

### Task 5: Release

**Files:**
- All changed source and docs.

- [ ] Commit implementation.
- [ ] Push `main`.
- [ ] Tag and publish `v0.2.0`.
