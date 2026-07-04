# Quality Checks

Quality checks are required before reporting quantitative STM/SJTM results. A diagnostic plot is not a substitute for machine-readable provenance.

## Data-Contract Gates

Confirm and record:

- Array shape and axis order.
- Bias unit and divider.
- Scan size and pixel size when physical distances or q vectors are used.
- Coordinate frame and origin convention.
- NaN and Inf handling.
- Any transpose, flip, crop, drift correction, interpolation, or affine transform.

Stop and request metadata when the bias unit, coordinate frame, or scan size is required but unknown.

## Fitting Gates

For single-spectrum and batch fits, record:

- Fit model.
- Fit window.
- Initial values and bounds.
- Residual statistics.
- Fit status.
- Parameter bound hits.
- Boundary hits for peak search windows.
- Representative successful, failed, and ambiguous spectra.
- Status maps for batch fitting.

Weaken the conclusion when many fits hit bounds, peak assignments swap, or multiple models fit equally well.

## FFT And Lock-In Gates

Record:

- Detrending or mean subtraction.
- Window function.
- DC mask.
- Lock-in engine, normally `pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction`.
- q selection and refinement.
- Complex lock-in field.
- Amplitude field.
- Phase field.
- Amplitude masks.
- Threshold sweeps.

Do not make phase conclusions from real-IFFT images alone. Treat `+q`, `-q`, `qx`, and `qy` separately before merging. For formal 2D lock-in outputs, use `scripts/pysidam_agent/phase_lockin.py run` or `bragg_phase.py lockin-from-decision`, then make downstream strain, phase-jump, or correlation analyses consume the resulting `phase_lockin_maps.npz` rather than recomputing lock-in locally.

## AI Atom Detection Gates

For AI atom/site recognition, record:

- Detector source, preferably `Atom_Identificator_core.AtomDetector`.
- Input topography channel, scan size, native pixel size, and inference pixel size.
- Detector parameters including `resize_ratio`, `min_dist`, `prob_threshold`, `patch_size`, `stride`, `gaussian_blur_ksize`, and `clip_percentile`.
- Scale check from `scripts/pysidam_agent/atom_ai.py recommend-scale`; for a 20 nm, 512 px map, `resize_ratio=1.5` gives 0.0260417 nm per inference pixel and a 0.3515625 nm spacing gives 13.5 inference pixels.
- `scripts/pysidam_agent/atom_ai.py lattice-qc` output: nearest-neighbor median, spread, duplicate-like fraction, vacancy-like fraction, fourfold order, and neighbor-count fraction.
- Human-requested wipe regions from `wipe-regions`, including region geometry, label, excluded count, and the output class column.

Report AI atom sites only when the post-detection lattice is an orderly square lattice with few missing or duplicate sites. If QC fails, tune detector parameters and rerun AI detection. Human-marked DW, dirty, highlighted, or defect regions should be excluded with `excluded_<label>` while preserving AI A/B labels outside those regions.

## Approval Gates

Use an approval gate when the agent must choose a scientifically sensitive parameter before execution:

- `fit_window`: superconducting coherence-peak fit ranges, peak-search windows, or other fitting intervals.
- `q_selection`: FFT-derived q vectors, q windows, and filter sigma for lock-in, QPI, p_LL, or symmetry analysis.
- `peak_count`: the number of peaks in multipeak fitting.

Other steps can proceed without a separate approval gate when they are routine and fully recorded. Gated runs must keep `approval_proposal.json`, `approval_decision.json` or a recorded `user_preapproved` choice, the review figure or HTML, and a report link to the decision.

## Cross-Observable Gates

Before comparing observables, confirm:

- Same coordinate frame.
- Same crop and pixel grid, or documented resampling.
- Drift-correction field if used.
- Site-coordinate frame if atom or lattice sites are used.

Avoid site-level or phase-level claims when frame alignment is uncertain.

## Reporting Gates

A complete evidence package includes:

- Machine-readable report.
- Data outputs.
- Diagnostic figures.
- Warnings.
- Failure modes.
- Software provenance.
- Separation between measured results and interpretation.
