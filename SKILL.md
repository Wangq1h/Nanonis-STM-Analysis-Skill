---
name: stm-sjtm-data-processing
description: Use when processing STM, STS, SJTM, SPSTM, QPI, topography, spectroscopy, superconducting gap fitting, multipeak fitting, lock-in phase, atom/site detection, Josephson-current maps, Z-ratio maps, deconvolution, or reproducible STM/SJTM reports.
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

Run `analystm --help`, or `PYTHONPATH=src python -m analystm --help` from a source checkout with dependencies installed, when local execution is available so the public AnalySTM backend is used by default. Run `scripts/resolve_runtime.py --probe` when optional raw-data dependencies or legacy bridge commands are needed; if no cached runtime is ready, inspect `scripts/resolve_runtime.py --bootstrap-command` and use `scripts/bootstrap_runtime.py` only in an isolated user runtime.

## Minimal Analysis And Clarification Gate

Default to the smallest analysis that answers the user's explicit request. For a first pass, prefer quick reads, existing AnalySTM CLI commands/APIs, short one-off shell/Python snippets, and direct diagnostic figures/tables. Do not create a new task-local long script, framework, reusable pipeline, or broad evidence package for a single data-viewing or exploratory request unless the user asks for reproducibility, batch processing, or a formal report. If an existing AnalySTM command cannot do the task, report the gap and ask before writing substantial custom code.

Respect the user's named observable and channel. If the user says topography, morphology, or `形貌`, analyze `Z`/topography only unless they explicitly request Current, LI/demod, dI/dV, spectroscopy, gap, or another channel. If the request does not specify the channel, observable, geometry, or meaning of "phase" clearly enough to choose the analysis surface, stop after file/channel inspection and ask a concise question before running quantitative analysis. Do not silently reinterpret a topography request as spectroscopy, dI/dV, LI-demod, or cross-observable analysis.

## Fast Tool Routing

Before reading legacy PySIDAM source modules or scanning the skill tree, route by intent through AnalySTM:

| User intent | First route | Read next only if needed |
| --- | --- | --- |
| Identify or summarize `.dat`, `.3ds`, `.sxm`, `.ibw`, `.csv`, `.tsv`, or `.txt` files | `analystm read --quick` for structural checks; legacy fallback: `scripts/pysidam_agent/read_file.py --quick` | `references/format-io-matrix.md`; for raw Nanonis also `references/nanonis-3ds-ingest.md` |
| Export reportable spectra, grid cubes, or Igor waves | `analystm export spec-dat`, `analystm export grid-3ds`, or `analystm export ibw` | `references/format-io-matrix.md`; record column/channel mappings and units |
| Plot routine STS `.dat` spectra or channel summaries | `references/task-cards/sts-dat-quick.md`, then `analystm plot-spectrum` | `references/data-contracts.md` for quantitative follow-up |
| Run spectroscopy display processing, auto offset, smoothing, normalization, derivative, or export payloads | `analystm spectroscopy process` | `references/data-contracts.md`; record x scale, offset, symmetrization, smoothing, normalization, derivative order, and export kind |
| Fit superconducting gaps or DOS models | `references/task-cards/gap-fit-quick.md`, then `analystm fit-gap`; legacy fallback: `scripts/pysidam_agent/fit_gap.py` | `references/fitting-recipes.md`; ask for mode when ambiguous |
| Extract peak-based gap maps or fit peak windows | `references/fitting-recipes.md` and `analystm gap-map`; legacy capability lookup only if AnalySTM is insufficient | `references/approval-gates.md` when the agent chooses fit windows |
| Run multipeak fitting or choose peak count | `references/fitting-recipes.md` and `analystm multipeak fit`; legacy capability lookup only if AnalySTM is insufficient | `references/approval-gates.md` before formal batch fitting |
| Build waterfall linecuts, waterfall peak tables, or peak-align-zero corrected grids | `analystm waterfall fit` or `analystm waterfall peak-align-zero` | `references/pysidam-tool-map.md`; record linecut/indices, fit windows, offset, bias scaling, smoothing, and baseline choices |
| Do Bragg FFT peak checks, q-vector selection, or 2D lock-in phase extraction | `analystm bragg policy`, then `analystm phase-lockin`; legacy fallback: `scripts/pysidam_agent/phase_lockin.py run` or `bragg_phase.py lockin-from-decision` | `references/approval-gates.md`; `references/pysidam-tool-map.md` only if AnalySTM is insufficient |
| Do broader QPI, 1D-QPI, display FFT, FFT ROI filtering, PR-QPI/PQPI, symmetry, or real-phase p_LL analysis | `analystm qpi 1d-fft`, `analystm qpi fft-filter`, `analystm qpi fft-volume`, `analystm qpi symmetry`, `analystm qpi pr-qpi`, or `analystm qpi real-phase` | `references/pysidam-tool-map.md`; `references/approval-gates.md` before q/sigma-dependent execution |
| Process SPSTM dI/dV, topography/map linecut, QPI R90, or spin contrast | `analystm spstm didv`, `analystm spstm qpi-r90`, or `analystm spstm qpi-spin` | `references/pysidam-tool-map.md`; record normalization and background choices |
| Compute map histograms, histogram KDE traces, or crop 2D/SXM/3DS maps | `analystm histogram` or `analystm crop map` | `references/pysidam-tool-map.md`; record background mode, crop center/side/angle, scan size, and output header |
| Build surface survey path logs or path point payloads | `analystm path-viz build` | `references/pysidam-tool-map.md`; record move batches, +Z steps, marks, and autoscale bounds |
| Build publication payload summaries, contrast ranges, payload limits, or scale-bar metadata | `analystm publication payload` | `references/pysidam-tool-map.md`; Qt/Matplotlib widget capture and interactive editing are UI-only |
| Run AI atom/site detection, tune detector scale, QC lattice sites, or wipe human-marked DW/defect regions | `analystm atom recommend-scale`, then AI detection, then `analystm atom lattice-qc` or `analystm atom wipe-regions` | `references/runtime-bootstrap.md`; `references/quality-checks.md`; `references/pysidam-tool-map.md` only if detector routing is insufficient |
| Compare Domain Wall, near-DW, away-region topography/spectroscopy/phase maps, or build DW masks | `analystm domain-wall policy`, then `analystm domain-wall build-masks` or `analystm domain-wall stats`; legacy fallback: `scripts/pysidam_agent/domain_wall.py` | `references/workflow.md`; `references/quality-checks.md`; only use atom `wipe-regions` after DW regions are defined |
| Process topography display FFT, LF drift correction, FFT ROI filtering, atom/site registration, or other topography workflows | `analystm topography display-fft`, `analystm topography lf-drift`, `analystm topography fft-filter`, and `analystm atom`; use `scripts/pysidam_agent/capabilities.py --domain topography` only for explicit PySIDAM source audit or legacy comparison | `references/workflow.md`, `references/quality-checks.md` |
| Compute SJTM Josephson, superfluid, Z-ratio, intensity, bias calibration, or deconvolution outputs | `analystm sjtm`, `analystm intensity`, or `analystm deconvolve`; use `scripts/pysidam_agent/capabilities.py --domain sjtm` or `--query deconvolution` only when AnalySTM is insufficient | relevant workflow/fitting references and reporting gates |
| Build a reproducible evidence package or review outputs | `references/reporting.md` and `references/quality-checks.md` | domain reference only for fields under review |

If no route matches, inspect `analystm --help`, the relevant `analystm <domain> --help`, and `src/analystm` source before opening legacy PySIDAM modules. Query `references/pysidam-capability-index.json` through `scripts/pysidam_agent/capabilities.py --query KEYWORD` only for explicit legacy source mapping, regression comparison, or an approved AnalySTM capability gap.

For routine file identification, symlink checks, `.dat` spectroscopy summaries, or diagnostic plots, prefer a quick card and AnalySTM before deep references:

- Raw file or symlink inspection: use shell `readlink`/`find -L` plus `analystm read --quick`; do not generate full reports or plots unless the user asks for formal analysis.
- `.dat` STS inspection: read `references/task-cards/sts-dat-quick.md`, then use `analystm read --quick` or `analystm plot-spectrum`.
- Superconducting gap fitting: read `references/task-cards/gap-fit-quick.md`, then use `analystm fit-gap`. Ask the user to choose a fitting mode when strict model compatibility versus gap-priority experimental fitting is ambiguous. Do not write a new optimizer when the AnalySTM fitter is importable.
- Bragg phase analysis: first confirm the observable/channel if not explicit. If the user asks for topography/morphology phase, use the topography map only. If the user did not provide an exact q vector or ROI, first ask whether they want to specify the peak/ROI or allow agent search. If they provide q/ROI, use it first and record `user_preapproved` or user-preferred ROI. Use `analystm bragg policy` and `analystm phase-lockin` for approved runs.
- Bragg phase analysis can also use `analystm bragg policy` and `analystm phase-lockin` directly when the q vector is approved.
- AI atom detection: prefer `Atom_Identificator_core.AtomDetector` only for optional detection; use `analystm atom` for scale choice, lattice QC, and human wipe regions. For a 20 nm, 512 px topography, `resize_ratio=1.5` gives 0.0260417 nm per inference pixel and a 0.3515625 nm atom spacing spans 13.5 inference pixels; nearby scales are the first tuning range.
- Domain Wall analysis: first confirm the target observable/channel if not explicit. If the user asks for topography/morphology DW, use `Z`/topography only. If the user did not provide DW geometry, first ask whether they will mark DW regions or allow an agent proposal. Human-marked DW, dirty, highlighted, or defect regions take priority. Use `analystm domain-wall build-masks` to save broad/on/near/away masks, and `stats` for reusable DW/away map statistics.
- Legacy PySIDAM source mapping: read `references/pysidam-capability-map.md` or query `references/pysidam-capability-index.json` only when the user explicitly asks for legacy comparison or approves an AnalySTM gap fallback.

Before quantitative analysis, fitting, map extraction, phase claims, or scientific conclusions, also read `references/runtime-bootstrap.md`, `references/data-contracts.md`, and `references/quality-checks.md`. For file IO beyond a quick card, read `references/format-io-matrix.md`. For raw Nanonis `.3ds`, `.sxm`, or `.dat` beyond basic inspection, also read `references/nanonis-3ds-ingest.md`.

## Reference Routing

- For overall workflow, read `references/workflow.md`.
- For AnalySTM availability, runtime dependency checks, persistent cached runtimes, optional legacy PySIDAM discovery, and default imports, read `references/runtime-bootstrap.md`.
- For fast task entry, read the relevant quick card in `references/task-cards/`.
- For legacy PySIDAM capability lookup and agent bridge entry points, read `references/pysidam-capability-map.md` and query `references/pysidam-capability-index.json` only after the backend rule permits it.
- For supported file formats, reader entry points, object contracts, and unsupported formats, read `references/format-io-matrix.md`.
- For raw Nanonis `.3ds`, `.sxm`, `.dat`, topography extraction, bias divider handling, or target-energy slices, read `references/nanonis-3ds-ingest.md`.
- For spectroscopy fitting, superconducting gap fitting, multipeak fitting, gap maps, Z-ratio, or bias calibration, read `references/fitting-recipes.md`.
- For legacy `pysidam` module selection or source mapping, read `references/pysidam-tool-map.md`.
- For user approval of agent-chosen fit windows, q vectors, filter sigma, or peak counts, read `references/approval-gates.md`.
- For quality gates and verification requirements, read `references/quality-checks.md`.
- For output schemas, provenance, and evidence packages, read `references/reporting.md`.

Read only the relevant references for the current task after the required first step.

## Mandatory Rules

- Start with the minimal viable analysis. Do not expand a request into extra channels, cross-observable comparisons, fitting, phase extraction, or report packaging unless the user asked for those outputs or approved that expansion.
- Do not infer missing scientific intent. When channel, observable, DW geometry, q/ROI, fit window, peak count, or the meaning of phase is ambiguous, inspect only enough to present available choices, then ask before quantitative analysis.
- Do not write long task-local scripts for one-off exploration. Prefer existing AnalySTM commands/APIs and compact snippets; ask before creating substantial custom code or a reusable pipeline.
- Confirm array shape, axis order, bias unit, coordinate frame, and scan size before quantitative analysis.
- Keep report-facing 2D maps as `(y, x)` and report-facing spectroscopy cubes as `(y, x, bias)`. When calling AnalySTM or an approved legacy source-mapping fallback, respect the documented internal order and record any explicit transpose.
- For raw Nanonis `.3ds`, treat the stored bias axis as already corrected by the experimental software. Use divider `1.0` by default; do not apply extra scaling from header comments such as `divider=1/100` unless the user explicitly requests extra scaling.
- Record all unit conversions, bias dividers, background corrections, smoothing, interpolation, window functions, q selections, and masks.
- For raw Nanonis `.3ds`, `.sxm`, or `.dat`, use `analystm read` and the optional `nanonispy` reader path when available. Do not hand-roll a binary parser unless all documented readers are unavailable and the user explicitly approves that fallback.
- Prefer AnalySTM public backend functions and bundled headless adapters. Do not instantiate Qt windows or `QApplication` for data analysis unless the user explicitly asks for the GUI.
- Reportable analysis MUST use the AnalySTM public backend (`analystm ...` CLI or `import analystm`) as the execution surface. Do not directly import `pysidam`, call `scripts/pysidam_agent/*`, or report a PySIDAM engine unless the user explicitly asks for a legacy/regression comparison or AnalySTM is missing the capability and the user approves that fallback in the current turn.
- Do not write task-local replacements for AnalySTM commands or APIs. For gap maps, FFT/QPI display, peak detection, smoothing, detrending/background removal, lock-in, fitting, intensity, crop, histogram, export, or deconvolution, first route to the matching `analystm` command/module. If the command cannot produce the requested artifact, stop and report the exact gap instead of silently reimplementing the algorithm.
- Every reportable output must name an AnalySTM execution engine such as `analystm.gap_map`, `analystm.fft_windowing`, or `analystm.phase_lockin`; keep PySIDAM names only in an explicit `legacy_source_mapping` or `pysidam_source_mapping` field.
- Do not make phase conclusions from real-IFFT images alone.
- For lock-in or QPI phase claims, save or request complex fields, amplitudes, phases, masks, and threshold sweeps.
- For Bragg/QPI 2D lock-in extraction, use `analystm phase-lockin`; the report must record `lockin_engine = analystm.phase_lockin.lockin_phase_extraction`. Legacy bridge reports may record the PySIDAM engine string only when the legacy command is explicitly used. Do not write task-local lock-in demodulation such as custom `exp(-i q r)` plus Gaussian smoothing unless AnalySTM is unavailable and the user explicitly approves the fallback.
- For Bragg/lock-in phase requests with no exact q vector or ROI, ask before running agent peak search. Human-specified q vectors or ROIs take priority over agent search. Use `analystm bragg policy` to enforce this decision point.
- For AI atom recognition, record detector parameters including `resize_ratio`, `min_dist`, `prob_threshold`, `patch_size`, `stride`, and preprocessing. After detection, run `analystm atom lattice-qc`; the sites should form an orderly square lattice with few duplicate-like close pairs or vacancy-like gaps. If QC fails, adjust detector parameters and rerun instead of adding a manual review/calibration relabeling workflow.
- For user-marked DW, dirty, highlighted, or defect regions, use `analystm atom wipe-regions` with x/y bands, rectangles, circles, or polygons. Preserve AI A/B labels outside the wiped region and mark excluded atoms as `excluded_<label>`.
- For Domain Wall map comparisons, keep broad DW/context regions separate from refined `on_dw_mask`, and compute `away_mask` outside the full broad region. Save the DW geometry, masks, counts, near-DW width, edge exclusion, refinement percentile, and DW/away ratios before claiming DW-enhanced gap filling, phase jumps, or topography correlations.
- Use an approval gate before executing agent-chosen `fit_window`, `q_selection` including q vectors/windows/filter sigma, or `peak_count` decisions. Create `approval_proposal.json`, show the user the recommendation and evidence, then continue only after `approval_decision.json` or explicit `user_preapproved` parameters are recorded.
- Other routine preprocessing and display parameters do not need a separate approval gate, but they must still be recorded in provenance.
- For fitting claims, report fit status, residuals, boundary hits, parameter bounds, and failure modes.
- For superconducting gap fitting, call `analystm fit-gap` first. If the public fitter or legacy bridge imports are blocked, report that blocker and do not silently fall back to an agent-written optimizer.
- When a superconducting/two-band fit request does not clearly specify strict PySIDAM-compatible fitting or gap-priority experimental fitting, ask before fitting. Ask again for each later ambiguous request; do not reuse a previous choice unless the user explicitly says to.
- Treat `pysidam` as a development reference and legacy fallback, not a mandatory public runtime dependency.
- Use only isolated user-writable Python runtimes for missing dependencies; do not use `sudo`, root installs, global `pip`, `brew`, or conda base modifications.
- Do not introduce dataset-specific paths or private experimental data into reusable skill files.
