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

Run `scripts/resolve_runtime.py --probe` first when local execution is available so an existing cached runtime is reused across directories. If no cached runtime is ready, inspect `scripts/resolve_runtime.py --bootstrap-command` and use `scripts/bootstrap_runtime.py` only in an isolated user runtime.

For routine file identification, `.dat` spectroscopy summaries, or diagnostic plots, prefer a quick card and the bridge scripts before deep references:

- `.dat` STS inspection: read `references/task-cards/sts-dat-quick.md`, then use `scripts/pysidam_agent/read_file.py` or `scripts/pysidam_agent/plot_spectrum.py`.
- PySIDAM routing: read `references/pysidam-capability-map.md` or query `references/pysidam-capability-index.json` through `scripts/pysidam_agent/capabilities.py`.

Before quantitative analysis, fitting, map extraction, phase claims, or scientific conclusions, also read `references/runtime-bootstrap.md`, `references/data-contracts.md`, and `references/quality-checks.md`. For file IO beyond a quick card, read `references/format-io-matrix.md`. For raw Nanonis `.3ds`, `.sxm`, or `.dat` beyond basic inspection, also read `references/nanonis-3ds-ingest.md`.

## Reference Routing

- For overall workflow, read `references/workflow.md`.
- For runtime dependency checks, persistent cached runtimes, host-specific `pysidam` discovery, and default imports, read `references/runtime-bootstrap.md`.
- For fast task entry, read the relevant quick card in `references/task-cards/`.
- For PySIDAM capability lookup and agent bridge entry points, read `references/pysidam-capability-map.md` and query `references/pysidam-capability-index.json`.
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
- Use only isolated user-writable Python runtimes for missing dependencies; do not use `sudo`, root installs, global `pip`, `brew`, or conda base modifications.
- Do not introduce dataset-specific paths or private experimental data into reusable skill files.
