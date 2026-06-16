# pysidam Tool Map

Use this reference when `pysidam` is available as an installed package or source checkout. Treat it as a preferred implementation source, not a hard dependency.

## Discovery

Before relying on `pysidam`, an agent should:

1. Check whether `import pysidam` works.
2. If import fails, search for a source checkout only when the user has provided one or the workspace clearly contains it.
3. Record the source path, package version, or git commit when available.
4. If `pysidam` is unavailable, follow the portable workflow and use standard Python tools.

## Data Standardization

Use `common.py` for:

- 3DS cube normalization.
- Bias-axis selection.
- Bias divider handling.
- Scan-size extraction.
- Topography candidate extraction.
- SXM direction handling.

Key contract: keep analysis cubes as `(y, x, bias)` unless a selected function explicitly requires a transposed fitting view.

## Topography

Use:

- `topography_display.py` for topography viewing.
- `topography_filter.py` for FFT filtering workflows.
- `topography_correction.py` for low-frequency drift correction using lock-in phases and displacement fields.
- `topography_ai_identificator.py` for atom or lattice-site detection and coordinate export.

Record the raw map, corrected map, Bragg or lattice q vectors, displacement fields, and coordinate-frame transforms.

## Spectroscopy And Fitting

Use:

- `spectroscopy_display.py` for single-spectrum inspection.
- `spectroscopy_dynes_fitting.py` for interactive Dynes-style fitting.
- `superconducting_gap_models.py` for reusable superconducting model helpers.
- `linecutmap_gap_map_extraction.py` for left/right peak extraction and gap maps.
- `linecutmap_multipeak_fitting.py` for multipeak linecut and map workflows.

When extracting headless helpers from GUI modules, record the source module and function names in the report.

## SIS/NIS And Deconvolution

Use:

- `usefultools_deconvolution_point.py` for point-spectrum NIS/SIS fitting and deconvolution.
- `usefultools_deconvolution_grid.py` for grid deconvolution workflows.

Require tip state, temperature, normalization policy, and model assumptions before interpreting fit parameters physically.

## QPI, FFT, And Lock-In

Use:

- `fft_windowing.py` for window functions, FFT input preparation, display scaling, and DC masking.
- `qpi_display.py` for QPI visualization.
- `qpi_filter.py` for QPI filtering.
- `qpi_phase_analysis.py` for complex lock-in phase extraction.
- `qpi_real_phase.py` for real-space phase workflows.
- `qpi_pr_pqi.py` for PR-QPI style workflows.

Do not merge `+q`, `-q`, `qx`, and `qy` products until the independent diagnostics are saved.

## SJTM

Use:

- `sjtm_ic.py` for Josephson critical-current extraction workflows.
- `sjtm_superfluid.py` for zero-bias conductance, superfluid proxy, and related SJTM map workflows.

Record bias scaling, fitting windows, fit status, and tip/sample assumptions.

## SPSTM And Utilities

Use `spstm_*`, `usefultools_histogram.py`, `usefultools_path_viz.py`, and palette/export tools as supporting modules when the user request calls for them. Keep them out of the default STM/SJTM path unless relevant.
