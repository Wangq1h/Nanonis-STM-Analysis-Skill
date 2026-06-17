# Changelog

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
