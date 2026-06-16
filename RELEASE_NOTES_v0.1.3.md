# v0.1.3

This release makes the isolated runtime persistent and easier for agents to reuse from any project directory.

## Highlights

- Added `scripts/resolve_runtime.py`.
- The skill now tells agents to run `resolve_runtime.py --probe` before bootstrapping.
- The resolver reads the cached `runtime.json` and uses its virtual environment Python.
- Host-specific defaults can be stored in `~/.config/stm-sjtm-data-processing/host.json`.

## Why

Agents should not reinstall or re-bootstrap dependencies every time they work in a new experiment directory. A successful runtime bootstrap is machine state, not project state.

## Release Checklist

- Run `python3 scripts/validate_package.py`.
- Run `python3 scripts/resolve_runtime.py --json`.
- Run `python3 scripts/resolve_runtime.py --probe` on a machine with a prepared runtime.
