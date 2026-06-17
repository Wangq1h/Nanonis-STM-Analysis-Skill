# v0.2.0

This release adds a bundled `pysidam_agent_core` package for headless PySIDAM-derived fitting workflows.

Highlights:

- `scripts/pysidam_agent/fit_gap.py` now routes superconducting-gap fitting through `pysidam_agent_core.gap_fitting.fit_gap_model_guarded`.
- The default gap-fitting path works without `PyQt5`, `pyqtgraph`, `QApplication`, or PySIDAM window modules.
- Model definitions and parameter specifications still come from `pysidam.core.superconducting_gap_models`.
- Package validation now rejects UI-bound imports in the default fitting bridge and core package.

Release checklist:

- Run `python3 scripts/validate_package.py`.
- Run `python3 scripts/pysidam_agent/fit_gap.py --probe-fitter`.
- Run one `.dat` gap fit in a headless-only environment without UI dependencies.
