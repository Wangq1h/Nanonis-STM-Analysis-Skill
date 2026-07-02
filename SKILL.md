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

## Fast Tool Routing

Before reading PySIDAM source modules or scanning the skill tree, route by intent:

| User intent | First route | Read next only if needed |
| --- | --- | --- |
| Identify or summarize `.dat`, `.3ds`, `.sxm`, `.ibw`, `.csv`, `.tsv`, or `.txt` files | `scripts/pysidam_agent/read_file.py --quick` for structural checks; omit `--quick` for full inventory | `references/format-io-matrix.md`; for raw Nanonis also `references/nanonis-3ds-ingest.md` |
| Plot routine STS `.dat` spectra or channel summaries | `references/task-cards/sts-dat-quick.md`, then `scripts/pysidam_agent/plot_spectrum.py` | `references/data-contracts.md` for quantitative follow-up |
| Fit superconducting gaps or DOS models | `references/task-cards/gap-fit-quick.md`, then `scripts/pysidam_agent/fit_gap.py` | `references/fitting-recipes.md`; ask for mode when ambiguous |
| Extract peak-based gap maps or fit peak windows | `references/fitting-recipes.md` and `scripts/pysidam_agent/capabilities.py --query gap_map` | `references/approval-gates.md` when the agent chooses fit windows |
| Run multipeak fitting or choose peak count | `references/fitting-recipes.md` and `scripts/pysidam_agent/capabilities.py --query multipeak` | `references/approval-gates.md` before formal batch fitting |
| Do Bragg FFT peak checks, q-vector selection, or lock-in phase | `scripts/pysidam_agent/bragg_phase.py policy`, then `inspect-roi` or `lockin-from-decision` as appropriate | `references/approval-gates.md`; `references/pysidam-tool-map.md` only if the bridge is insufficient |
| Do broader QPI, p_LL, PR-QPI/PQPI, or symmetry analysis | `scripts/pysidam_agent/capabilities.py --query lockin` or `--domain qpi_lockin` | `references/pysidam-tool-map.md`; `references/approval-gates.md` before q/sigma-dependent execution |
| Process topography, drift correction, atom/site registration | `scripts/pysidam_agent/capabilities.py --domain topography` | `references/workflow.md`, `references/quality-checks.md` |
| Compute SJTM Josephson, superfluid, Z-ratio, intensity, or deconvolution outputs | `scripts/pysidam_agent/capabilities.py --domain sjtm` or `--query deconvolution` | relevant workflow/fitting references and reporting gates |
| Build a reproducible evidence package or review outputs | `references/reporting.md` and `references/quality-checks.md` | domain reference only for fields under review |

If no route matches, query `references/pysidam-capability-index.json` through `scripts/pysidam_agent/capabilities.py --query KEYWORD` before opening large PySIDAM modules. Do not build a fresh source index unless the capability map and targeted text search are insufficient.

For routine file identification, symlink checks, `.dat` spectroscopy summaries, or diagnostic plots, prefer a quick card and the bridge scripts before deep references:

- Raw file or symlink inspection: use shell `readlink`/`find -L` plus `scripts/pysidam_agent/read_file.py --quick`; do not generate full reports or plots unless the user asks for formal analysis.
- `.dat` STS inspection: read `references/task-cards/sts-dat-quick.md`, then use `scripts/pysidam_agent/read_file.py --quick` or `scripts/pysidam_agent/plot_spectrum.py`.
- Superconducting gap fitting: read `references/task-cards/gap-fit-quick.md`, then use `scripts/pysidam_agent/fit_gap.py`, which calls `pysidam_agent_core.gap_fitting.fit_gap_model_guarded`. Ask the user to choose a fitting mode when strict model compatibility versus gap-priority experimental fitting is ambiguous. Do not write a new optimizer when the headless core fitter is importable.
- Bragg phase analysis: if the user did not provide an exact q vector or ROI, first ask whether they want to specify the peak/ROI or allow agent search. If they provide q/ROI, use it first and record `user_preapproved` or user-preferred ROI. Use `scripts/pysidam_agent/bragg_phase.py inspect-roi` for user ROI peak checks and `lockin-from-decision` for approved phase extraction.
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
- For user approval of agent-chosen fit windows, q vectors, filter sigma, or peak counts, read `references/approval-gates.md`.
- For quality gates and verification requirements, read `references/quality-checks.md`.
- For output schemas, provenance, and evidence packages, read `references/reporting.md`.

Read only the relevant references for the current task after the required first step.

## Mandatory Rules

- Confirm array shape, axis order, bias unit, coordinate frame, and scan size before quantitative analysis.
- Keep report-facing 2D maps as `(y, x)` and report-facing spectroscopy cubes as `(y, x, bias)`. When calling PySIDAM core, respect its internal 3DS order `(x, y, bias)` and record any explicit transpose.
- For raw Nanonis `.3ds`, treat the stored bias axis as already corrected by the experimental software. Use divider `1.0` by default; do not apply extra scaling from header comments such as `divider=1/100` unless the user explicitly requests extra scaling.
- Record all unit conversions, bias dividers, background corrections, smoothing, interpolation, window functions, q selections, and masks.
- For raw Nanonis `.3ds`, `.sxm`, or `.dat`, use `nanonispy` through `pysidam.core.nanonis_io` when available. Do not hand-roll a binary parser unless all documented readers are unavailable and the user explicitly approves that fallback.
- Prefer PySIDAM headless/core functions and bundled `pysidam_agent_core` adapters. Do not instantiate Qt windows or `QApplication` for data analysis unless the user explicitly asks for the GUI.
- Do not make phase conclusions from real-IFFT images alone.
- For lock-in or QPI phase claims, save or request complex fields, amplitudes, phases, masks, and threshold sweeps.
- For Bragg/lock-in phase requests with no exact q vector or ROI, ask before running agent peak search. Human-specified q vectors or ROIs take priority over agent search. Use `scripts/pysidam_agent/bragg_phase.py policy` to enforce this decision point.
- Use an approval gate before executing agent-chosen `fit_window`, `q_selection` including q vectors/windows/filter sigma, or `peak_count` decisions. Create `approval_proposal.json`, show the user the recommendation and evidence, then continue only after `approval_decision.json` or explicit `user_preapproved` parameters are recorded.
- Other routine preprocessing and display parameters do not need a separate approval gate, but they must still be recorded in provenance.
- For fitting claims, report fit status, residuals, boundary hits, parameter bounds, and failure modes.
- For superconducting gap fitting, call the PySIDAM-backed `scripts/pysidam_agent/fit_gap.py` bridge first. If `pysidam_agent_core` or PySIDAM core model imports are blocked, report that blocker and do not silently fall back to an agent-written optimizer.
- When a superconducting/two-band fit request does not clearly specify strict PySIDAM-compatible fitting or gap-priority experimental fitting, ask before fitting. Ask again for each later ambiguous request; do not reuse a previous choice unless the user explicitly says to.
- Treat `pysidam` as a preferred tool source, not a mandatory dependency.
- Use only isolated user-writable Python runtimes for missing dependencies; do not use `sudo`, root installs, global `pip`, `brew`, or conda base modifications.
- Do not introduce dataset-specific paths or private experimental data into reusable skill files.
