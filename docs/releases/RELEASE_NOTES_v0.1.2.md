# v0.1.2

This release adds a safe dependency bootstrap layer for the STM/SJTM skill.

## Highlights

- Added `scripts/bootstrap_runtime.py`.
- Added grouped dependency manifests under `runtime/`.
- Default bootstrap group is `headless`, which expands to `core,nanonis,ibw`.
- Added optional `ai` and `ui` groups for heavier task-specific dependencies.
- Added offline install support through `--no-network --wheelhouse`.
- Added `runtime.json` output with venv, dependency group, PySIDAM source, and probe provenance.

## Safety Boundaries

The bootstrapper creates an isolated virtual environment in a user-writable cache. It refuses root execution and system runtime paths. It does not use `sudo`, global `pip`, `brew`, or conda base modifications.

PySIDAM is loaded as an installed package or source checkout. If no source is found, auto mode can clone PySIDAM into the skill cache. Existing user checkouts are not mutated.

## Release Checklist

- Run `python3 scripts/bootstrap_runtime.py --dry-run --no-network --groups headless`.
- Run `python3 scripts/validate_package.py`.
- Sync the repository contents into the installed Codex skill directory.
