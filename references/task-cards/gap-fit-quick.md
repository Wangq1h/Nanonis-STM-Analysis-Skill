# Gap Fit Quick Card

Use this quick card for superconducting gap model fitting on spectra. The default route is the bundled headless `pysidam_agent_core` fitter, not an agent-written optimizer.

## Mode Gate

Ask before fitting when the prompt does not explicitly choose one of these modes:

- `strict-pysidam-compatible`: keep the PySIDAM-compatible two-band model contract, shared broadening when that is the selected PySIDAM model, no unrequested polynomial background, and fit parameters comparable to the default bridge.
- `gap-priority experimental`: allow recorded nuisance terms such as bias offset, independent band broadening, fit-window selection, and peak/zero-bias weighting to prioritize gap-region quality. Report that this is an extended observation model, not the strict PySIDAM default.

Ask again for later ambiguous superconducting/two-band fitting requests. Do not carry over a previous mode silently.

For the gap-priority experimental route, use the packaged profile instead of writing a task-local script:

```bash
python3 scripts/pysidam_agent/fit_gap.py INPUT1.dat INPUT2.dat \
  --profile two_band_splusminus_gap_priority \
  --average-bwd \
  --symmetry both \
  --auto-fit-window \
  --save-overview \
  --output-dir outputs/gap_priority_fit
```

This profile runs peak/center weights, candidate fit window scanning, bias offset, linear/quadratic background, independent gamma per band, sym/unsym comparisons, center RMSE / peak RMSE / boundary-hit metrics, and writes `report.json`, per-curve CSV, per-fit PNG, and `fit_overlay_overview.png`.

## Required Route

1. Run `python3 scripts/resolve_runtime.py --probe`.
2. Probe the fitter with `python3 scripts/pysidam_agent/fit_gap.py --probe-fitter --summary-json outputs/fit_gap_probe.json`.
3. If ready, fit with `python3 scripts/pysidam_agent/fit_gap.py INPUT.dat --model "Two Band s-wave" --fit-strategy multistart_weighted --fit-max-starts 16 --output-dir outputs/gap_fit`.
4. The bridge must report `fit_engine="pysidam_agent_core.gap_fitting.fit_gap_model_guarded"`.
5. If PySIDAM UI fitter import is blocked, do not route through the UI module; use the headless bridge and only bootstrap `python3 scripts/bootstrap_runtime.py --groups headless,nanonis,ibw` unless the user explicitly requests GUI tools.

## Rules

- Do not write a new optimizer for gap fitting.
- The bridge must call `pysidam_agent_core.gap_fitting.fit_gap_model_guarded`.
- Initial-value tests should pass `--initial-params` or `--fit-max-starts` into the headless core fitter.
- If a gap-priority experimental workflow needs behavior not yet exposed by the bridge, report the mode choice and scientific differences before any task-local script.
- quantitative fitting must produce diagnostic plots; final answers must link or display the PNG outputs when plots are generated.
- If PySIDAM core model imports are unavailable, stop with a blocked report instead of using a local `least_squares` fallback.
- The core package may use SciPy optimizers internally; task-local scripts must not.
