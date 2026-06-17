# Gap Fit Quick Card

Use this quick card for superconducting gap model fitting on spectra. The default route is PySIDAM's existing fitter, not an agent-written optimizer.

## Required Route

1. Run `python3 scripts/resolve_runtime.py --probe`.
2. Probe the fitter with `python3 scripts/pysidam_agent/fit_gap.py --probe-fitter --summary-json outputs/fit_gap_probe.json`.
3. If ready, fit with `python3 scripts/pysidam_agent/fit_gap.py INPUT.dat --model "Two Band s-wave" --fit-strategy multistart_weighted --fit-max-starts 16 --output-dir outputs/gap_fit`.
4. If PySIDAM fitter import is blocked, report the blocked dependency and use only the safe bootstrap path `python3 scripts/bootstrap_runtime.py --groups headless,ui`.

## Rules

- Do not write a new optimizer for gap fitting.
- The bridge must call `fit_selected_gap_dos_model_guarded`.
- Initial-value tests should pass `--initial-params` or `--fit-max-starts` into the PySIDAM fitter.
- If PySIDAM cannot import the fitter, stop with a blocked report instead of using a local `least_squares` fallback.
