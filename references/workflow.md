# STM/SJTM Workflow

This reference gives the default analysis sequence for STM, STS, SJTM, QPI, and lock-in tasks. Use the smallest workflow that answers the user request, then add more stages only when the data and metadata support them.

## 1. Ingest

Identify the source format and available channels before analysis. Current PySIDAM-backed inputs include `.sxm`, `.3ds`, `.dat`, `.npz`, `.ibw`, CSV, TSV, and TXT. Other formats need a documented converter before they are treated as supported.

Run the runtime bootstrap from `references/runtime-bootstrap.md` before opening data, then use the reader map in `references/format-io-matrix.md`. For raw Nanonis `.3ds`, `.sxm`, or `.dat`, use the `nanonispy` route described in `references/nanonis-3ds-ingest.md`.

Record:

- Source files and channel names.
- Topography map availability.
- Spectroscopy cube availability.
- Bias or sweep axis.
- Scan size and pixel size.
- Header metadata used for temperature, sweep direction, units, or tip state.

If `nanonispy` is unavailable, raw Nanonis IO is blocked through the normal path. Request installation or exported intermediate data in CSV, NPZ, HDF5, IBW, or text form rather than inventing a parser.

## 2. Normalize Data Contracts

Convert all data into explicit array and metadata contracts before quantitative analysis. Use `references/data-contracts.md` for the required conventions.

## 3. Topography Processing

Typical sequence:

1. Inspect raw topography.
2. Apply plane or background correction for display and record whether the corrected map is also used quantitatively.
3. Compute FFT with a recorded window and DC treatment.
4. Identify Bragg peaks and refine peak positions when needed.
5. For drift correction, extract lock-in phases from two non-collinear lattice vectors and compute displacement fields.
6. Detect atom or lattice-site coordinates only after the topography frame is stable.
7. For AI atom recognition, run `scripts/pysidam_agent/atom_ai.py recommend-scale` before detection, record `resize_ratio` and related detector parameters, then run `lattice-qc` on the output atom table. A 20 nm, 512 px topography with `resize_ratio=1.5` has 0.0260417 nm per inference pixel and a 0.3515625 nm nearest-neighbor spacing corresponds to 13.5 inference pixels; nearby scales are the first tuning range.
8. If atom sites do not form an orderly square lattice, adjust detector parameters such as `resize_ratio`, `min_dist`, and `prob_threshold`, then rerun detection. Do not substitute a manual review/calibration relabeling pass for failed AI recognition.
9. If the user marks DW, dirty, highlighted, or defect regions, first run `scripts/pysidam_agent/domain_wall.py policy` and save reusable DW geometry or masks with `build-masks` when map comparisons are needed.
10. For atom tables, run `scripts/pysidam_agent/atom_ai.py wipe-regions` from the human-marked regions and preserve AI labels outside those excluded regions.
11. Export corrected maps, displacement fields, site coordinates, exclusion masks or labels, and diagnostics.

## 4. Spectroscopy Processing

Typical sequence:

1. Confirm bias axis unit and direction.
2. Display representative spectra and mean spectra.
3. Decide whether the task needs peak extraction or physical DOS fitting.
4. If the agent chooses a fitting interval or peak-search interval, stop at a `fit_window` approval gate before fitting.
5. Apply normalization, smoothing, symmetrization, or bias calibration only when recorded in the report.
6. Fit single spectra before batch maps.
7. For batch maps, output value maps, status maps, and representative diagnostics.

## 5. SJTM-Specific Maps

For superconducting-tip data, record tip state, temperature, voltage unit, sweep direction, and model assumptions. Analyze Josephson-current, zero-bias conductance, superfluid proxy, gap-height, Z-ratio, and deconvolution outputs as separate observables unless the model justifies combining them.

## 6. Fourier, QPI, And Lock-In

Typical sequence:

1. Mean-subtract or detrend as recorded.
2. Apply a named window function.
3. Compute FFT and apply display scaling.
4. Mask the DC component when appropriate.
5. Select or refine target q points as a proposal, with FFT evidence and uncertainty.
6. Stop at a `q_selection` approval gate before any q-vector, q-window, or filter-sigma-dependent extraction.
7. Extract complex lock-in fields after approval with `scripts/pysidam_agent/phase_lockin.py run` or `bragg_phase.py lockin-from-decision`; the report must name `pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction` as the engine.
8. Save amplitude, phase, complex field, and masks.
9. Treat `+q`, `-q`, `qx`, and `qy` separately before any merge.

## 7. Cross-Observable Analysis

Compare topography, dI/dV, gap maps, SJTM maps, atom sites, displacement, strain, and phase fields only after confirming a common coordinate frame. If alignment is uncertain, report map-level observations and avoid site-level claims.

For Domain Wall comparisons, keep the user-marked broad DW/context geometry separate from any refined `on_dw_mask` such as high-Z pixels inside the broad strip. Use `scripts/pysidam_agent/domain_wall.py build-masks` to save `domain_wall_masks.npz`, then reuse `stats` for topography, spectroscopy-derived maps, and lock-in phase/amplitude maps. The `away_mask` must exclude the full broad DW region, not only the refined high-signal pixels.

## 8. Evidence Package

Every substantial workflow should produce:

- `report.json` with inputs, contracts, parameters, quality metrics, warnings, outputs, and software provenance.
- Approval proposal and decision artifacts when a gated choice was used.
- Data outputs as NPZ or named CSV files.
- Diagnostic PNG or PDF figures.
- Notes separating measured results from interpretation when interpretation is requested.
