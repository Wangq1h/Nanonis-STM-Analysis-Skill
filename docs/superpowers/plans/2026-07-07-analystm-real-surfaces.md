# AnalySTM Real Surfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the reserved `gap-map`, `sjtm`, and `deconvolve` CLI surfaces with true headless migrations of the corresponding PySIDAM non-UI algorithms.

**Architecture:** Add focused backend modules under `src/analystm` for gap-map peak fitting, SJTM Ic/superfluid metrics, and SIS/NIS deconvolution. CLI commands load `.npz` inputs, call those modules, and write NPZ/CSV/JSON outputs without importing PySIDAM or Qt.

**Tech Stack:** Python 3.10+, NumPy, SciPy, existing AnalySTM CLI/test framework.

## Global Constraints

- Do not substitute proxy algorithms for PySIDAM deconvolution.
- Do not import PyQt5, pyqtgraph, `QApplication`, `pysidam.*`, private paths, or dataset-specific paths from `src/analystm`.
- Preserve PySIDAM algorithm contracts except for removing UI/window/widget code.
- Use TDD: write failing tests before production code.
- Standard outputs are NPZ data, CSV summaries, and `report.json`.

---

### Task 1: Gap Map Peak Extraction

**Files:**
- Create: `src/analystm/gap_map.py`
- Modify: `src/analystm/cli/main.py`
- Test: `tests/test_analystm_real_surfaces.py`

**Interfaces:**
- Produces: `fit_single_peak(bias, spectrum, search_range, interp_factor=5, interp_kind="cubic", smooth_param=0.0, smooth_method="Gaussian") -> float`
- Produces: `extract_gap_map(bias, cube_yxb, left_range, right_range, ...) -> dict`

- [ ] Write CLI and unit tests showing `analystm gap-map` writes `gap_map_outputs.npz`, `gap_map_summary.csv`, and `report.json`.
- [ ] Verify tests fail because command is reserved.
- [ ] Migrate `PeakFitter.fit_single_pixel` and batch gap-map logic.
- [ ] Wire CLI arguments and outputs.
- [ ] Verify targeted tests pass.

### Task 2: SJTM Ic And Superfluid Metrics

**Files:**
- Create: `src/analystm/sjtm.py`
- Modify: `src/analystm/cli/main.py`
- Test: `tests/test_analystm_real_surfaces.py`

**Interfaces:**
- Produces: `compute_ic_map(bias, current_cube_yxb, neg_window, pos_window, min_points=5, algorithm="quick") -> dict`
- Produces: `compute_superfluid_metrics(bias, conductance_cube_yxb, rn_window, g0_window, min_points=5) -> dict`

- [ ] Write tests showing `analystm sjtm` computes finite `ic_map`, `rn_map`, `g0_map`, and `ns_map`.
- [ ] Verify tests fail before implementation.
- [ ] Migrate PySIDAM Gaussian Ic extraction and superfluid metric logic.
- [ ] Wire CLI arguments and outputs.
- [ ] Verify targeted tests pass.

### Task 3: SIS/NIS Point And Grid Deconvolution

**Files:**
- Create: `src/analystm/deconvolution.py`
- Modify: `src/analystm/cli/main.py`
- Test: `tests/test_analystm_real_surfaces.py`

**Interfaces:**
- Produces: `fit_nis_dynes_didv(...) -> dict`
- Produces: `fit_sis_dynes_didv(...) -> dict`
- Produces: `build_sis_didv_matrix(...) -> ndarray`
- Produces: `solve_sis_sample_dos(...) -> dict`
- Produces: `run_sis_didv_deconvolution(...) -> dict`
- Produces: `run_grid_deconvolution(...) -> dict`

- [ ] Write tests showing `analystm deconvolve` with SIS mode writes real `sample_dos`, reconvolution, R2, and method provenance.
- [ ] Verify tests fail before implementation.
- [ ] Migrate PySIDAM NIS/SIS Dynes kernels, SIS matrix construction, weighted pseudo-inverse solver, and deconvolution grids.
- [ ] Wire point and grid CLI modes.
- [ ] Verify targeted tests pass.

### Task 4: Validation And Docs

**Files:**
- Modify: `scripts/validate_package.py`
- Modify: `README.md`
- Modify: `RELEASE_NOTES_v3.0.md`
- Modify: `CHANGELOG.md`

- [ ] Update validation required files/tokens to include real backend modules.
- [ ] Remove “reserved” wording for the three surfaces.
- [ ] Run validation, full tests, clean install smoke, and forbidden-boundary scan.
