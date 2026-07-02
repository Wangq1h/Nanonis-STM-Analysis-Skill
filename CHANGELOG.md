# Changelog

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
