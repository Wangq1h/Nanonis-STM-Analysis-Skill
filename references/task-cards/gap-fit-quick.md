# Gap Fit Quick Card

Use this quick card for superconducting gap model fitting on spectra. The default route is the bundled headless `pysidam_agent_core` fitter, not an agent-written optimizer.

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
- If PySIDAM core model imports are unavailable, stop with a blocked report instead of using a local `least_squares` fallback.
- The core package may use SciPy optimizers internally; task-local scripts must not.
