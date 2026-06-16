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

Always read `references/data-contracts.md` and `references/quality-checks.md` before processing data or proposing scientific conclusions.

## Reference Routing

- For overall workflow, read `references/workflow.md`.
- For spectroscopy fitting, superconducting gap fitting, multipeak fitting, gap maps, Z-ratio, or bias calibration, read `references/fitting-recipes.md`.
- For `pysidam` module selection, read `references/pysidam-tool-map.md`.
- For output schemas, provenance, and evidence packages, read `references/reporting.md`.

Read only the relevant references for the current task after the required first step.

## Mandatory Rules

- Confirm array shape, axis order, bias unit, coordinate frame, and scan size before quantitative analysis.
- Keep 2D maps as `(y, x)` and spectroscopy cubes as `(y, x, bias)` unless a specific algorithm requires an explicit transpose to `(bias, y, x)`.
- Record all unit conversions, bias dividers, background corrections, smoothing, interpolation, window functions, q selections, and masks.
- Do not make phase conclusions from real-IFFT images alone.
- For lock-in or QPI phase claims, save or request complex fields, amplitudes, phases, masks, and threshold sweeps.
- For fitting claims, report fit status, residuals, boundary hits, parameter bounds, and failure modes.
- Treat `pysidam` as a preferred tool source, not a mandatory dependency.
- Do not introduce dataset-specific paths or private experimental data into reusable skill files.
