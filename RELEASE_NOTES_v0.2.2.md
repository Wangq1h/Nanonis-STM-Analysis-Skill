# v0.2.2

This release packages the gap-priority two-band STS strategy that had previously lived in task-local scripts.

Highlights:

- Adds `pysidam_agent_core.gap_priority`.
- Adds `--profile two_band_splusminus_gap_priority` to `scripts/pysidam_agent/fit_gap.py`.
- Adds `--symmetry`, `--auto-fit-window`, `--candidate-fit-abs-mV`, `--random-starts`, and `--save-overview`.
- Implements peak/center weighting, candidate fit window scanning, bias offset, linear/quadratic background, independent gamma per band, sym/unsym comparisons, center RMSE / peak RMSE / boundary-hit metrics.
- Writes `report.json`, per-curve CSV, per-fit PNG, and `fit_overlay_overview.png`.
- Keeps the physical DOS evaluator delegated to PySIDAM's `evaluate_gap_dos_model`; the new profile is an extended observation model for gap-region fitting.

Release checklist:

- Run `python3 scripts/validate_package.py`.
- Run `python3 scripts/pysidam_agent/fit_gap.py --probe-fitter`.
- Run a two-file `.dat` profile fit with `--profile two_band_splusminus_gap_priority --symmetry both --auto-fit-window --save-overview`.
- Verify `report.json`, CSV tables, individual PNGs, and `fit_overlay_overview.png`.
