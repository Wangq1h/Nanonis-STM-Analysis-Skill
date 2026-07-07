# STM/SJTM Data Processing v0.2.4

## Bragg Phase Bridge

- Adds `scripts/pysidam_agent/bragg_phase.py` with `policy`, `inspect-roi`, and `lockin-from-decision` commands.
- Adds `pysidam_agent_core.bragg_phase` so agents reuse q-axis, ROI peak, preprocessing, and Bragg phase helpers instead of writing task-local scripts.
- Requires user-specified q vectors or ROIs to take priority. If no q/ROI is provided for phase analysis, agents must ask before running their own peak search.

## Data Ingest Contract

- Adds `read_file.py --quick` for fast file and symlink inspection.
- Records `read_parameters` in file summaries.
- Defaults `.3ds` reads to divider `1.0`; Nanonis bias axes are treated as already divider-corrected by the experiment software unless the user explicitly requests extra scaling.

## Verification

- Run `python3 scripts/validate_package.py`.
- Run `python3 -m unittest discover -s tests`.
- Smoke-test `bragg_phase.py policy`, `inspect-roi`, and `lockin-from-decision`.
