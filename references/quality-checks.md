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
- q selection and refinement.
- Complex lock-in field.
- Amplitude field.
- Phase field.
- Amplitude masks.
- Threshold sweeps.

Do not make phase conclusions from real-IFFT images alone. Treat `+q`, `-q`, `qx`, and `qy` separately before merging.

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
