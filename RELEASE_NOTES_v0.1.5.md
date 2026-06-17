# Release Notes v0.1.5

## What Changed

- Added `scripts/pysidam_agent/fit_gap.py`, a gap-fitting bridge that delegates to PySIDAM's `fit_selected_gap_dos_model_guarded`.
- Added `references/task-cards/gap-fit-quick.md` to make fitting tasks use the PySIDAM bridge instead of writing new optimizers.
- Added package validation that rejects local optimizer imports inside the gap-fitting bridge.
- Updated skill routing so superconducting gap fitting must use the bridge or report a blocked PySIDAM fitter import.

## Release checklist

- Run `python3 scripts/validate_package.py`.
- Probe `python3 scripts/pysidam_agent/fit_gap.py --probe-fitter`.
- Verify the bridge either calls PySIDAM's fitter or exits with `pysidam_fitter_import_failed`. Do not write a new optimizer.
