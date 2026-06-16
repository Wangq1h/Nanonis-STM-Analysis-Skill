# Release Notes v0.1.1

This release turns PySIDAM from a loose recommendation into an explicit runtime route for STM/SJTM agents. The runtime bootstrap is now a required first step before file IO.

## Added

- `references/runtime-bootstrap.md` for default dependency probing and PySIDAM source discovery.
- `references/format-io-matrix.md` for the current supported file formats and PySIDAM reader routes.
- `references/nanonis-3ds-ingest.md` for raw `.3ds`, `.sxm`, `.dat`, divider handling, topography extraction, and target-energy maps.
- `scripts/probe_runtime.py` for portable import checks.

## Updated

- PySIDAM tool map aligned with `origin/main` commit `f42e433a909e4347773ac2a45067c6f112cd5709`.
- PXP is explicitly not claimed as supported until a PySIDAM reader or documented converter exists.
- Fitting recipes now name concrete PySIDAM helpers for superconducting DOS models, NIS/SIS Dynes fitting, SIS deconvolution, gap maps, multipeak fitting, and intensity derivatives.
- Data contracts now distinguish PySIDAM internal `(x, y, bias)` from report-facing `(y, x, bias)`.

## Verification

Run:

```bash
python3 scripts/validate_package.py
python3 scripts/probe_runtime.py
```
