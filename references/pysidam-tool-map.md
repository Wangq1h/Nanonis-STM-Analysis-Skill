# pysidam Tool Map

Use this reference when `pysidam` is available as an installed package or source checkout. This map is based on the packaged layout in `origin/main` commit `f42e433a909e4347773ac2a45067c6f112cd5709` from 2026-06-11.

Treat PySIDAM as the preferred source for proven STM/SJTM routines. Treat its desktop windows as UI wrappers, not as the default agent interface.

For repeated agent work, prefer the `pysidam_agent` bridge scripts and the capability index before reading large PySIDAM modules. The compact routing files are `references/pysidam-capability-index.json` and `references/pysidam-capability-map.md`.

## Source And Sync

Before using a source checkout:

1. Run the runtime probe in `references/runtime-bootstrap.md`.
2. Record import path, git remote, branch, local HEAD, and `origin/main`.
3. Run `git fetch origin --prune` when network access is available.
4. If the checkout is dirty or diverged, do not merge, reset, or overwrite it. Use a clean clone or detached worktree at the fetched remote HEAD for code reading.

Do not instantiate Qt windows or `QApplication` for data analysis unless the user explicitly requests the GUI. If a module import fails because Qt or `pyqtgraph` is broken, use pure `pysidam.core.*` modules first and report which UI-wrapped helper is blocked.

## Core Headless Modules

Use these first:

- `pysidam.core.nanonis_io`: `read_nanonis_file`, `import_nanonispy`, `nanonis_available`, `NanonisUnavailableError`, `NanonisReadError`.
- `pysidam.core.dataset_utils`: `prepare_3ds_dataset`, `normalize_3ds_signal_dict`, `normalize_3ds_cube`, `choose_best_bias_axis`, `extract_3ds_topography_candidates`, `normalize_sxm_direction_map`.
- `pysidam.core.bias_utils`: `normalize_bias_with_divider`, `normalize_imported_bias_to_mv`, `apply_bias_divider_to_mv`, `is_bias_like_channel_name`.
- `pysidam.core.import_io`: `read_imported_file`, `imported_file_to_numeric_table`; supports text tables and PySIDAM's built-in `.ibw` reader.
- `pysidam.core.fft_windowing`: `prepare_fft_input`, `build_windowed_fft_complex`, `apply_fft_display_scale`, `apply_fft_dc_mask`, Igor-style window names.
- `pysidam.core.superconducting_gap_models`: gap model constants, defaults, parameter specs, `evaluate_gap_dos_model`.
- `pysidam.core.export`: `write_nanonis_spec_dat`, `write_nanonis_grid_3ds`; ignore Qt PDF/widget helpers for headless work.

PySIDAM normalizes 3DS cubes to `(x, y, bias)`. Convert to report-facing `(y, x, bias)` only with an explicit transpose and record that conversion.

## Nanonis And Imported Data

For raw `.3ds`, `.sxm`, and `.dat`, follow `references/nanonis-3ds-ingest.md` and `references/format-io-matrix.md`. The normal route is `pysidam.core.nanonis_io.read_nanonis_file`, which requires `nanonispy`.

For `.txt`, `.csv`, `.tsv`, and `.ibw`, use `pysidam.core.import_io.read_imported_file`. PySIDAM's `.ibw` reader parses Igor binary waves directly and classifies 1D spectra, 2D maps, 2D linecut-like spectral maps, 3D spectral cubes, FFT-like maps, and unknown ND waves.

Do not claim PySIDAM support for PXP until a PySIDAM reader or documented converter is added.

## Topography

Prefer pure or mostly headless pieces:

- `pysidam.topography.topography_correction.LFDriftCorrector`: FFT peak refinement, `get_q_vector`, `lockin_phase`, `compute_drift_field`, `warp_image`.
- `pysidam.topography.topography_ai_identificator._get_atom_detector_cls`: lazy loader for `Atom_Identificator_core.AtomDetector`.

For AI atom detection, call `AtomDetector` directly when available. Record detector config such as `patch_size`, `stride`, `resize_ratio`, `gaussian_blur_ksize`, `clip_percentile`, `min_dist`, `prob_threshold`, `force_cpu`, and `base_channels`.

Record raw map, corrected map, q vectors, displacement fields, scan size, pixel size, and every flip/transpose/warp.

## Spectroscopy And Fitting

Core model helpers:

- `pysidam.core.superconducting_gap_models.evaluate_gap_dos_model`: isotropic s, d-wave, anisotropic s, two-band, three-band, s+d, and FeSe two-band anisotropic model evaluation.
- `get_dynes_fit_model_defaults`, `get_deconvolution_fit_param_spec`, `map_deconvolution_fit_values`, `build_gap_model_summary_params`.

Peak and gap maps:

- `pysidam.linecutmap.linecutmap_gap_map_extraction.PeakFitter.fit_single_pixel`: Gaussian-assisted local peak extraction within a search range.
- Batch gap-map logic: fit left and right peak windows per pixel, then compute `(right_peak - left_peak) / 2`; report NaN/failure maps.

Multipeak fitting:

- `pysidam.linecutmap.linecutmap_multipeak_fitting.UniversalVortexFitterEngine`.
- Main methods: `run_fit`, `evaluate_at`, `collect_debug_state_payload`, `save_debug_state`.
- Supported profiles/backgrounds include Gaussian, Lorentzian, offset, full-trace linear, and Igor-style cubic background.

Some spectroscopy and linecut modules import Qt at module import time. If imports are blocked, use the documented algorithm contract and core model helpers, and report the blocked module.

## SIS/NIS And Deconvolution

Point-spectrum headless helpers live in `pysidam.useful_tools.usefultools_deconvolution_point`:

- Trace preparation: `symmetrize_bias_trace`, `resample_trace`, `build_symmetric_energy_grid`, `extract_temperature_from_header`, `normalize_sample_dos_display`.
- Dynes and thermal kernels: `dynes_dos`, `compute_nis_didv_from_dos`, `compute_sis_didv_from_dos`.
- Fixed-temperature fitting: `fit_nis_dynes_didv`, `fit_sis_dynes_didv`, `evaluate_fixed_nis_dynes_preview`, `evaluate_fixed_sis_dynes_preview`.
- SIS deconvolution: `build_sis_didv_matrix`, `solve_sis_sample_dos`, `build_sis_deconvolution_grids`, `run_sis_didv_deconvolution`.
- Gap DOS model fitting: `evaluate_selected_gap_dos_model`, `fit_selected_gap_dos_model`, `fit_selected_gap_dos_model_guarded`.

Grid deconvolution helpers in `pysidam.useful_tools.usefultools_deconvolution_grid` include bias-grid resampling, pseudo-inverse operators, trace integration, overlap stats, and R2 scoring.

Require tip state, temperature, normalization policy, fit window, zero-peak exclusion, broadening, and model assumptions before interpreting parameters physically.

## QPI, FFT, Lock-In, And Symmetry

Use:

- `pysidam.qpi_analysis.qpi_display`: `_compute_fft_base_volume`, `_postprocess_fft_volume`, `_prepare_fft_block`.
- `pysidam.qpi_analysis.qpi_phase_analysis`: `lockin_phase_extraction`, `_refine_peak_near`, `_unwrap_phase_2d`.
- `pysidam.qpi_analysis.qpi_real_phase`: `lockin_phase`, background helpers, phase wrapping helpers.
- `pysidam.qpi_analysis.qpi_pr_pqi`: `_compute_pr_qpi_volume` for PR-QPI/PQPI style volumes.
- `pysidam.qpi_analysis.qpi_symmetry`: `apply_affine_to_stack`, `build_affine_from_bragg_vectors`, `estimate_lf_displacement`, `apply_lf_displacement_to_stack`, `symmetrize_qpi`, `_compute_fft_volume`.

Save window type, DC mask, FFT display scale, q vectors, complex fields, amplitude, phase, masks, and threshold sweeps. Keep `+q`, `-q`, `qx`, and `qy` diagnostics separate until a justified merge.

## SJTM

Use SJTM window modules as source for algorithm contracts. They are UI-heavy, so import only when Qt works:

- `pysidam.sjtm.sjtm_ic.SJTMIcExtractionWindow._compute_ic_row` and `_compute_ic_map`: fit negative and positive Josephson branches with Gaussian windows; compute `|Ic|` from average absolute dip/peak currents.
- `pysidam.sjtm.sjtm_superfluid.SJTMSuperfluidDensityWindow._compute_metrics`: compute normal resistance from a low-bias linear slope, G(0) from a Gaussian window near zero, and a superfluid proxy `ns = G(0) * Rn^2`.
- `_resolve_g0_window_mask` and `_fit_gaussian_segment` define the zero-bias conductance window and fallback behavior.

Record bias scaling, fit windows, minimum points, fitting mode, fallback paths, units, and tip/sample assumptions.

## Intensity And Derived Maps

`pysidam.linecutmap.linecutmap_intensity` supports intensity modes:

- `dI/dV`: original spectral intensity.
- `d2`: numerical first derivative of dI/dV.
- `neg_d3`: negative second derivative of dI/dV so original peaks appear bright.

Record derivative order, bias spacing, smoothing, interpolation, baseline removal, integration windows, and denominator floors for ratios.

## SPSTM And Utilities

Use SPSTM, histogram, crop, path visualization, palette, and export modules only when the request calls for them. Keep them out of the default STM/SJTM path unless relevant.
