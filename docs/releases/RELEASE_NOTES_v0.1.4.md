# Release Notes v0.1.4

## What Changed

- Added a quick card entry for common STS `.dat` reading and overview plotting.
- Added `scripts/pysidam_agent/` with reusable bridge commands for capability lookup, file summaries, and 1D spectrum plots.
- Added `references/pysidam-capability-index.json` and `references/pysidam-capability-map.md` so agents can route across the full indexed PySIDAM surface without loading every source file.
- Added `scripts/sync_installed_skill.py` to install or update the local Codex skill copy without carrying Git metadata into the installed directory.
- Updated the skill entry path to prefer resolver-first execution and short task cards before deeper references.

## Release checklist

- Run `python3 scripts/validate_package.py`.
- Run `python3 scripts/resolve_runtime.py --probe`.
- Run the bridge on anonymous test spectra.
- Sync the installed skill with `python3 scripts/sync_installed_skill.py`.
- Confirm the installed skill directory has no `.git` directory.
