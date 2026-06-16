---
name: stm-sjtm-data-processing
description: Use when processing STM, STS, SJTM, QPI, topography, spectroscopy, superconducting gap fitting, multipeak fitting, lock-in phase, atom/site detection, Josephson-current maps, Z-ratio maps, deconvolution, or reproducible STM/SJTM reports.
---

# STM/SJTM Data Processing

Use this skill when a task involves scanning tunneling microscopy or superconducting-tip STM data processing, fitting, Fourier analysis, lock-in analysis, cross-observable comparison, or evidence-package reporting.

## Required First Step

Before acting, classify the user request:

1. Data ingestion and normalization.
2. Topography processing.
3. Spectroscopy display, fitting, or gap extraction.
4. SJTM-specific map extraction.
5. Fourier, QPI, or complex lock-in analysis.
6. Cross-observable comparison.
7. Reporting and evidence packaging.

Always read `references/runtime-bootstrap.md`, `references/data-contracts.md`, and `references/quality-checks.md` before processing data or proposing scientific conclusions. For file IO, also read `references/format-io-matrix.md`. For raw Nanonis `.3ds`, `.sxm`, or `.dat`, also read `references/nanonis-3ds-ingest.md` before attempting file IO.

## Reference Routing

- For overall workflow, read `references/workflow.md`.
- For runtime dependency checks, local `pysidam` discovery, and default imports, read `references/runtime-bootstrap.md`.
- For supported file formats, reader entry points, object contracts, and unsupported formats, read `references/format-io-matrix.md`.
- For raw Nanonis `.3ds`, `.sxm`, `.dat`, topography extraction, bias divider handling, or target-energy slices, read `references/nanonis-3ds-ingest.md`.
- For spectroscopy fitting, superconducting gap fitting, multipeak fitting, gap maps, Z-ratio, or bias calibration, read `references/fitting-recipes.md`.
- For `pysidam` module selection, read `references/pysidam-tool-map.md`.
- For quality gates and verification requirements, read `references/quality-checks.md`.
- For output schemas, provenance, and evidence packages, read `references/reporting.md`.

Read only the relevant references for the current task after the required first step.

## Mandatory Rules

- Confirm array shape, axis order, bias unit, coordinate frame, and scan size before quantitative analysis.
- Keep report-facing 2D maps as `(y, x)` and report-facing spectroscopy cubes as `(y, x, bias)`. When calling PySIDAM core, respect its internal 3DS order `(x, y, bias)` and record any explicit transpose.
- Record all unit conversions, bias dividers, background corrections, smoothing, interpolation, window functions, q selections, and masks.
- For raw Nanonis `.3ds`, `.sxm`, or `.dat`, use `nanonispy` through `pysidam.core.nanonis_io` when available. Do not hand-roll a binary parser unless all documented readers are unavailable and the user explicitly approves that fallback.
- Prefer PySIDAM headless/core functions. Do not instantiate Qt windows or `QApplication` for data analysis unless the user explicitly asks for the GUI.
- Do not make phase conclusions from real-IFFT images alone.
- For lock-in or QPI phase claims, save or request complex fields, amplitudes, phases, masks, and threshold sweeps.
- For fitting claims, report fit status, residuals, boundary hits, parameter bounds, and failure modes.
- Treat `pysidam` as a preferred tool source, not a mandatory dependency.
- Do not introduce dataset-specific paths or private experimental data into reusable skill files.
