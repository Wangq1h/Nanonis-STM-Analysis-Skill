# Release Notes: v3.0.1

## Summary

This patch release tightens the AnalySTM runtime boundary so a fresh skill install no longer reports PySIDAM or UI packages as missing default dependencies. PySIDAM remains available only for explicit legacy regression/source-mapping work, while AI atom detection stays a planned external integration.

## Changes

- The default runtime probe now checks `analystm`, numerical/core dependencies, `nanonispy`, and `igorwriter`.
- `probe_runtime.py` reports `ai_atom_detection: planned` by default and only probes legacy PySIDAM or external AI when explicitly requested.
- `bootstrap_runtime.py` defaults to `--pysidam-mode none`, removes the active UI dependency group, and keeps `all` equivalent to `headless`.
- `resolve_runtime.py` ignores host `pysidam_root` unless legacy probing is explicitly enabled.
- Removed `runtime/requirements-ui.txt` from the current runtime.
- Updated README, SKILL, and runtime-bootstrap docs to make PySIDAM/Qt non-default and AI a planned integration.
- Added `tests/test_runtime_defaults.py` regression coverage.

## Compatibility

- Supported AnalySTM commands and legacy bridge scripts remain present.
- Explicit legacy PySIDAM checks can still be run with `--include-legacy-pysidam` or `--pysidam-mode auto --pysidam-root ...`.
- Existing raw Nanonis support still depends on `nanonispy`; IBW export still depends on `igorwriter`.

## Verification

- `python3 scripts/validate_package.py`
- `PYTHONPATH=src <runtime-python> -m unittest discover -s tests`
- `<runtime-python> scripts/probe_runtime.py`
