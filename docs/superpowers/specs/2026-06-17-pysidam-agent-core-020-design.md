# PySIDAM Agent Core 0.2.0 Design

## Goal

Version 0.2.0 separates the agent-facing algorithms from PySIDAM's GUI-wrapped modules. The skill repository will include a small Python package, `pysidam_agent_core`, so installing the skill also installs the headless algorithm layer required by agent bridge scripts.

The first 0.2.0 scope is superconducting gap fitting. It must work in the default headless runtime without `PyQt5`, `pyqtgraph`, `QApplication`, or PySIDAM window modules.

## Non-Goals

- Do not rewrite the full PySIDAM application.
- Do not migrate QPI, SJTM, SPSTM, deconvolution grids, or atom detection in 0.2.0.
- Do not make `PyQt5` or `pyqtgraph` part of the default fitting path.
- Do not commit experiment-specific data paths or private test data.

## Package Layout

```text
pysidam_agent_core/
  __init__.py
  io.py
  models.py
  numerics.py
  gap_fitting.py
scripts/pysidam_agent/
  fit_gap.py
```

`pysidam_agent_core` lives at the skill repository root. Bridge scripts add the skill root to `sys.path`, so the package is available from both the source repository and the installed skill directory.

## Dependencies

Allowed for default headless fitting:

- `numpy`
- `scipy`
- `matplotlib` only for bridge-side plot output
- `nanonispy` through `pysidam.core.nanonis_io`
- pure PySIDAM core modules such as `pysidam.core.superconducting_gap_models`

Forbidden for default headless fitting:

- `PyQt5`
- `pyqtgraph`
- `QApplication`
- PySIDAM GUI/window modules such as `pysidam.useful_tools.usefultools_deconvolution_point`

## Gap Fitting API

`pysidam_agent_core.gap_fitting` exposes:

```python
fit_gap_model_guarded(
    bias_mV,
    signal,
    model_name="Two Band s-wave",
    initial_params=None,
    fit_strategy="multistart_weighted",
    fit_max_starts=16,
    max_nfev=20000,
    time_budget_s=30.0,
    fit_abs_max=None,
)
```

The return value is a JSON-serializable dict with:

- fit status and status message
- model name, parameter order, parameter values, and bounds
- initial parameters and multistart count
- fit window, feature-weight policy, and affine scale/offset metadata
- display arrays for bias, data, model, and residual
- metrics including R2 and weighted RSS

## Algorithm Source

The implementation should preserve the PySIDAM algorithmic contract from the indexed source commit:

- model definitions and parameter specs come from `pysidam.core.superconducting_gap_models`
- multistart generation follows the PySIDAM gap-fit helper behavior
- feature weighting follows the PySIDAM gap-fit helper behavior
- model fitting uses SciPy optimizers inside `pysidam_agent_core`, not inside ad hoc test scripts
- affine scale/offset remains part of the fit-window model normalization

The bridge is allowed to use an optimizer because it is now the shared, tested headless core. Agent-generated one-off optimizers remain forbidden.

## Bridge Behavior

`scripts/pysidam_agent/fit_gap.py` will:

1. resolve/re-exec into the cached skill runtime
2. read `.dat`, `.txt`, `.csv`, `.tsv`, or 1D `.ibw` spectra
3. call `pysidam_agent_core.gap_fitting.fit_gap_model_guarded`
4. save summary JSON, curve CSV, and optional diagnostic PNG
5. record `fit_engine="pysidam_agent_core.gap_fitting.fit_gap_model_guarded"`

It will not import `pysidam.useful_tools.usefultools_deconvolution_point`.

## Validation

`scripts/validate_package.py` must verify:

- `pysidam_agent_core` files exist
- default gap fitting does not import `PyQt5`, `pyqtgraph`, `QApplication`, or PySIDAM GUI modules
- `scripts/pysidam_agent/fit_gap.py` imports `pysidam_agent_core.gap_fitting`
- `runtime/requirements-ui.txt` is not required for gap fitting
- release notes and docs identify this as version 0.2.0

Runtime verification must include:

```bash
python3 scripts/resolve_runtime.py --probe
python3 scripts/pysidam_agent/fit_gap.py --probe-fitter
python3 scripts/pysidam_agent/fit_gap.py data/sample_001.dat --no-plots
```

The fitting probe must pass in a headless runtime without `PyQt5` or `pyqtgraph`.

## Migration Plan

0.2.0 ships only the gap-fitting core. Future versions can migrate QPI, SJTM, and deconvolution helpers one domain at a time, each with a dedicated headless module and validation rule.
