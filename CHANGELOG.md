# Changelog

## v3.0.1 - 2026-07-09

- Made the default AnalySTM runtime independent of PySIDAM, PyQt5, and pyqtgraph.
- Changed `probe_runtime.py` so default probes report only public/headless dependencies and mark external AI atom detection as a planned integration.
- Changed `bootstrap_runtime.py` and `resolve_runtime.py` so PySIDAM source discovery is opt-in through explicit legacy mode.
- Removed the UI dependency manifest from the current runtime and kept AI detector dependencies behind explicit `headless,ai` testing.
- Added runtime-default regression tests and updated README/SKILL/runtime docs to prevent future install summaries from treating legacy PySIDAM or UI modules as required.

## v3.0 - 2026-07-07

- Added the public AnalySTM backend package under `src/analystm`, with `import analystm` and the `analystm` CLI as the default agent runtime surface.
- Added public CLI routes for `read`, `plot-spectrum`, `spectroscopy`, `fit-gap`, `gap-map`, `multipeak`, `intensity`, `waterfall`, `qpi`, `topography`, `histogram`, `crop`, `path-viz`, `publication`, `export`, `bragg`, `phase-lockin`, `atom`, `domain-wall`, `sjtm`, and `deconvolve`.
- Added true headless PySIDAM-derived implementations for gap-map peak extraction, SJTM Ic/superfluid calculations, and SIS dI/dV deconvolution.
- Reframed AnalySTM as the replacement backend: reports now name `analystm.*` engines and keep PySIDAM names as source mappings for auditability.
- Replaced the simplified SIS forward-model shortcut and DOS display normalization with the migrated direct integral and robust-tail normalization behavior.
- Migrated grid deconvolution helper APIs for linear resampling, weighted pseudo-inverse operators, R2 scoring, and masked cube means.
- Migrated Nanonis `.dat` spectroscopy export, `.3ds` grid export, and optional Igor Binary Wave export into `analystm.export` and `analystm export`.
- Migrated linecut intensity processing, derivative signal modes, H/V cuts, peak-align-zero bias calibration, and negative/positive Z-ratio maps into `analystm.intensity` and `analystm intensity`.
- Migrated waterfall linecut-map fitting and peak-align-zero calibration, including linecut flat-index selection, optional spatial interpolation, Gaussian/manual peak extraction, baseline/offset handling, export tables, and point JSON payloads, into `analystm.waterfall` and `analystm waterfall`.
- Migrated PR-QPI/PQPI positive/negative volume computation and QPI rotate-average symmetry into `analystm.qpi` and `analystm qpi`.
- Migrated QPI display FFT volume processing and qpi_real_phase p_LL maps into `analystm.qpi`, `analystm qpi fft-volume`, and `analystm qpi real-phase`.
- Migrated 1D-QPI K-E linecut FFT and topography/QPI FFT ROI filtering into `analystm.qpi`, `analystm.fft_filter`, `analystm qpi 1d-fft`, `analystm qpi fft-filter`, and `analystm topography fft-filter`.
- Migrated SPSTM dI/dV preprocessing, map/topography linecut profile helpers, QPI R90 anisotropy, and +/- bias spin contrast into `analystm.spstm` and `analystm spstm`.
- Completed the SJTM Ic migration by adding PySIDAM Quick/Accurate Gaussian branch fitting, retry jitter, fit-parameter payloads, and strict G(0) window behavior to `analystm.sjtm` and `analystm sjtm`.
- Migrated topography LF drift correction from `LFDriftCorrector`, including q-vector conversion, lock-in displacement fields, UX/UY convention, and image/stack warping, into `analystm.topography` and `analystm topography lf-drift`.
- Migrated topography display processing from `TopographyWindow`, including background modes, display FFT payloads, linecut sampling, and lattice readout, into `analystm.topography_display` and `analystm topography display-fft`.
- Migrated spectroscopy display processing from `SpectroscopyDisplayWindow`, including auto offset, symmetrization, smoothing, normalization, derivative generation, and Nanonis export payload construction, into `analystm.spectroscopy` and `analystm spectroscopy process`.
- Migrated useful-tools histogram and map-crop logic from `HistogramWindow` and `UsefulToolsMapCropWindow`, including background correction, histogram KDE traces, ROI sampling geometry, generated headers, SXM orientation restoration, and 3DS crop output, into `analystm.histogram`, `analystm.map_crop`, `analystm histogram`, and `analystm crop map`.
- Migrated surface survey path-viz state/table logic from `SurfaceSurveyPathVizWindow`, including pending move segments, confirmed path batches, point lists, autoscale bounds, path-log rows, and overflow redistribution, into `analystm.path_viz` and `analystm path-viz build`.
- Migrated publication payload helpers from `core.publication_editor`, including payload dataclasses, extent/limits helpers, line thinning, image downsampling, contrast modes, inset filtering, and scale-bar helpers, into `analystm.publication` and `analystm publication payload`.
- Migrated multipeak linecut fitting from `PeakFitResult` and `UniversalVortexFitterEngine`, including Gaussian/Lorentzian profiles, offset/full-trace-linear/Igor cubic backgrounds, per-row peak counts, manual initial centers, quality metrics, and debug payload export, into `analystm.multipeak` and `analystm multipeak fit`.
- Added a replacement coverage matrix under `docs/analystm_replacement_coverage.md`.
- Added public-backend boundary tests and validation so `src/analystm` does not require private PySIDAM source paths, `PYSIDAM_ROOT`, PyQt5, pyqtgraph, or dataset-specific paths.
- Updated skill routing so AnalySTM is preferred first, with the older `scripts/pysidam_agent/*` bridge kept as a compatibility fallback.
- Added reusable AI atom-recognition helpers in `pysidam_agent_core.atom_ai` and `scripts/pysidam_agent/atom_ai.py`.
- Added scale guidance for detector `resize_ratio`, including the 20 nm / 512 px / 1.5x reference scale of 0.0260417 nm per inference pixel and 13.5 inference pixels per 0.3515625 nm atom spacing.
- Added post-detection square-lattice QC so failed AI atom recognition triggers parameter tuning and rerun instead of manual review/calibration relabeling.
- Added human-marked DW/dirty/defect wipe support that marks `excluded_<label>` while preserving AI A/B labels outside the region.
- Documented that the AI atom-recognition model and weights remain an optional external dependency in v3.0, with public model release planned as the next step.
- Added reusable Domain Wall mask/stat helpers in `pysidam_agent_core.domain_wall` and `scripts/pysidam_agent/domain_wall.py`.
- Added DW policy, broad/on/near/away mask packaging, refined on-DW support, and DW/away map statistics so agents do not recreate one-off DW scripts.
- Added `scripts/pysidam_agent/phase_lockin.py` and `pysidam_agent_core.phase_lockin` as the clean PySIDAM 2D lock-in pipeline for phase analysis.
- Added a hard rule that Bragg/QPI phase extraction must record `pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction` as the lock-in engine instead of reimplementing demodulation in task-local scripts.

## v0.2.4 - 2026-07-02

- Added reusable Bragg/q-selection and lock-in bridge tooling through `scripts/pysidam_agent/bragg_phase.py`.
- Added `pysidam_agent_core.bragg_phase` for q-selection policy, ROI peak checks, topography preprocessing, and reusable Bragg phase helpers.
- Added a user-q/ROI-first rule: if the user asks for phase analysis without a q vector or ROI, agents must ask before running their own peak search.
- Updated `.3ds` bias handling so the default read contract uses divider `1.0` and treats Nanonis bias axes as already divider-corrected by experiment software.
- Added `read_file.py --quick` and machine-readable `read_parameters` for fast raw-data and symlink inspection without full evidence-package overhead.
- Added tests for divider contract and Bragg q-selection helpers.

## v0.2.3 - 2026-06-23

- Added standardized approval gates for agent-chosen `fit_window`, `q_selection`, and `peak_count` decisions.
- Added a pure-Python approval schema validator, report-link validator, and static HTML review renderer.
- Added `scripts/approval_gate.py` for validating `approval_proposal.json`, validating `approval_decision.json`, checking report linkage, and rendering review pages.
- Added fast tool routing so agents query the capability map before scanning large PySIDAM modules.

## v0.2.2 - 2026-06-17

- Added `pysidam_agent_core.gap_priority` with the `two_band_splusminus_gap_priority` profile.
- Added `fit_gap.py --profile two_band_splusminus_gap_priority --symmetry --auto-fit-window --save-overview`.
- Packaged peak/center weighting, candidate fit-window scanning, bias offset, linear/quadratic background, independent band broadening, sym/unsym comparisons, and center/peak/boundary-hit metrics.
- Made the gap-priority route save `report.json`, per-curve CSV files, per-fit PNG files, and `fit_overlay_overview.png`.
- Updated the gap-fit quick card to require diagnostic plots for quantitative fitting outputs.

## v0.2.1 - 2026-06-17

- Added a required fitting-mode gate for ambiguous superconducting and two-band gap fitting requests.
- Documented `strict-pysidam-compatible` versus `gap-priority experimental` modes so agents do not silently trade model comparability for better-looking fits.
- Updated validation to require the mode-gate language in the skill entry point, gap-fit quick card, and fitting recipes.
- Synced the installed Codex skill copy after the rule update.

## v0.2.0 - 2026-06-17

- Added bundled `pysidam_agent_core` package for headless agent-facing algorithms.
- Migrated superconducting gap fitting to `pysidam_agent_core.gap_fitting.fit_gap_model_guarded`.
- Kept gap-model definitions and parameter specs delegated to `pysidam.core.superconducting_gap_models`.
- Updated validation to reject UI-bound imports in the default gap-fitting bridge and core package.
- Updated docs and quick cards so agents call the shared core fitter instead of creating task-local fitting scripts.

## v0.1.5 - 2026-06-17

- Added `scripts/pysidam_agent/fit_gap.py` so superconducting gap fitting delegates to PySIDAM's `fit_selected_gap_dos_model_guarded`.
- Added a gap-fitting quick card that forbids agent-written optimizer fallbacks when the PySIDAM fitter is available.
- Extended validation to require the gap-fitting bridge and reject local optimizer imports inside it.
- Updated routing docs so blocked PySIDAM fitter imports are reported explicitly instead of being silently replaced.

## v0.1.4 - 2026-06-17

- Added a quick card path for common STS `.dat` reading and diagnostic plotting.
- Added `scripts/pysidam_agent/` bridge commands for compact PySIDAM-backed file summaries, spectrum plots, and capability lookup.
- Added a machine-readable PySIDAM capability index covering core IO, topography, spectroscopy fitting, linecut maps, QPI/lock-in, SJTM, SPSTM, deconvolution, and utility export.
- Added `scripts/sync_installed_skill.py` so the installed Codex skill copy is synchronized without Git metadata.
- Updated the skill entry point to use resolver-first quick routing before loading deep references.

## v0.1.3 - 2026-06-16

- Added `scripts/resolve_runtime.py` so agents reuse a cached runtime across project directories before bootstrapping.
- Documented host-local configuration through `~/.config/stm-sjtm-data-processing/host.json`.
- Updated the skill entry point to prefer `resolve_runtime.py --probe` over probing the current `python3` directly.

## v0.1.2 - 2026-06-16

- Added `scripts/bootstrap_runtime.py` for isolated user-writable dependency setup.
- Added runtime dependency groups for core analysis, Nanonis IO, IBW export, AI atom detection, and UI-wrapped helpers.
- Updated the README with bootstrap usage, offline wheelhouse mode, and safety boundaries.
- Updated runtime guidance to forbid root/global installs and to prefer per-skill virtual environments.

## v0.1.1 - 2026-06-16

- Added a default runtime bootstrap and dependency probe for PySIDAM, `nanonispy`, IBW export, Qt-wrapped modules, and AI atom detection.
- Added a file-format IO matrix for `.3ds`, `.sxm`, `.dat`, `.ibw`, `.npz`, and text-table inputs.
- Added a raw Nanonis/3DS ingest recipe using `pysidam.core.nanonis_io` and `pysidam.core.dataset_utils.prepare_3ds_dataset`.
- Updated the PySIDAM map to the package layout at `origin/main` commit `f42e433a909e4347773ac2a45067c6f112cd5709`.
- Clarified that PXP is not a current PySIDAM-backed supported format.
- Documented PySIDAM's internal `(x, y, bias)` 3DS contract and explicit conversion to report-facing `(y, x, bias)`.
- Expanded fitting recipes with concrete headless PySIDAM APIs for Dynes/NIS/SIS, deconvolution, gap maps, multipeak fitting, and intensity derivatives.

## v0.1.0 - 2026-06-16

Initial preview release.

- Added a Codex-compatible STM/SJTM data-processing skill adapter.
- Added platform-neutral references for workflow, data contracts, fitting recipes, pysidam tool mapping, quality checks, and reporting.
- Added a validation script for publishable package checks.
- Documented GitHub and non-Codex agent usage.