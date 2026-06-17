# Fitting Recipes

Use this reference for spectroscopy fitting, superconducting gap fitting, multipeak fitting, gap-map extraction, peak-height maps, Z-ratio maps, and bias calibration.

## Recipe Template

Each fitting workflow should record:

- Applicable question.
- Input contract.
- Preprocessing.
- Model choice.
- Initial values and bounds.
- Execution mode.
- Quality control.
- Outputs.
- Failure handling.
- pysidam mapping.

## Model Selection Rule

Choose the least complex model that answers the question:

- Use peak extraction when the requested output is a peak position, peak height, or gap map and the physical DOS parameters are not needed.
- Use a physical superconducting model when the requested output is a gap parameter, broadening parameter, band weight, anisotropy parameter, tip/sample DOS, or physical comparison across spectra.
- Use multipeak fitting when spectra contain overlapping peaks, shoulders, ZBP plus side peaks, vortex linecut peaks, or peak assignments that cannot be handled by a single local maximum.

## Superconducting Gap Fitting

Applicable questions:

- Estimate superconducting gap values from STS or SJTM spectra.
- Fit Dynes broadening.
- Compare one-band, two-band, or anisotropic gap models.
- Separate tip and sample DOS in NIS or SIS data.

Input contract:

- Bias axis unit and direction are known.
- Temperature is known for thermal convolution.
- Tip state and tip gap are recorded for SJTM, SIS, or NIS interpretation.
- Spectrum has documented normalization and background treatment.

Preprocessing:

- Remove or fit offsets only when recorded.
- Select a fit window that contains the coherence peaks and enough normal-state tail.
- Avoid smoothing unless the smoothing method and parameter are reported.
- For symmetrization, report the grid and zero-bias reference.

Model choices:

- Dynes DOS for single-gap phenomenology.
- Thermally broadened Dynes when temperature is needed.
- NIS model when a normal tip probes a superconducting sample.
- SIS model when a superconducting tip probes a superconducting sample.
- Two-band model when two resolvable gap scales are required.
- Anisotropic model when angular gap variation is part of the question.

Mode choices:

- `strict-pysidam-compatible`: preserve the PySIDAM model contract so parameters are comparable to the default bridge output. Do not add unrequested bias offsets, polynomial backgrounds, independent broadening, or custom weighting.
- `gap-priority experimental`: use recorded nuisance terms and weights to prioritize zero-bias platforms and coherence peaks. This may include bias offset, independent band broadening, fit-window selection, and background terms; report it as an extended observation model.

If the user request is ambiguous between these modes, ask before fitting. Ask again for future ambiguous superconducting/two-band fits instead of assuming the last choice.

Quality control:

- Residual curve and residual statistics.
- Parameter bounds and bound-hit flags.
- Fit-window sensitivity check.
- Initial-guess sensitivity check for multi-parameter fits.
- Statement of non-uniqueness when multiple models fit similarly.

Outputs:

- Fit parameters and units.
- Residual metrics.
- Fit status.
- Diagnostic plot.
- Machine-readable table or JSON entry.

pysidam mapping:

- Default agent route: `scripts/pysidam_agent/fit_gap.py`, which delegates fitting to `pysidam_agent_core.gap_fitting.fit_gap_model_guarded`.
- `pysidam_agent_core.gap_fitting` contains the headless multistart, feature-weight, fit-window, and affine-normalization implementation used by agents.
- `pysidam.core.superconducting_gap_models.evaluate_gap_dos_model` for model evaluation and parameter defaults.
- `pysidam.useful_tools.usefultools_deconvolution_point.fit_nis_dynes_didv` and `fit_sis_dynes_didv` for fixed-temperature Dynes-style dI/dV fitting.
- `pysidam.useful_tools.usefultools_deconvolution_point.fit_selected_gap_dos_model_guarded` is the historical GUI-wrapped source behavior; do not import it in the default agent path.
- `pysidam.useful_tools.usefultools_deconvolution_point.run_sis_didv_deconvolution` for SIS deconvolution when tip DOS, sample DOS assumptions, temperature, and normalization are known.
- `pysidam.useful_tools.usefultools_deconvolution_grid` for grid-based resampling, pseudo-inverse deconvolution, and R2/statistics helpers.

If a fitting helper lives in a GUI-heavy module and Qt import fails, use the documented headless bridge when available and report the blocked import. Do not replace the shared core fitter with a newly written task-local optimizer unless the user explicitly approves that fallback for exploratory work.

## Multipeak Fitting

Applicable questions:

- Track multiple spectral peaks across a linecut or map.
- Separate ZBP, shoulders, coherence peaks, and side peaks.
- Extract batch gap maps from left and right peak locations.

Input contract:

- Bias axis is known.
- Spectrum or cube shape is documented.
- Peak assignment rule is stated before batch fitting.

Preprocessing:

- Define search windows per peak.
- Define background model.
- Define smoothing only when justified.
- Exclude ZBP when fitting side peaks if the ZBP dominates the local maximum.

Quality control:

- Fit status per spectrum.
- Peak center, width, amplitude, and background per peak.
- Boundary-hit flags.
- Peak overlap flags.
- Assignment ambiguity flags.
- Representative spectra for successful, failed, and ambiguous pixels.

Outputs:

- Peak parameter tables.
- Status maps.
- Left peak, right peak, and gap-size maps for gap extraction.
- Diagnostic plots.

pysidam mapping:

- `pysidam.linecutmap.linecutmap_gap_map_extraction.PeakFitter.fit_single_pixel` for Gaussian peak extraction inside left/right search windows.
- Gap map contract: fit the left and right peak per pixel and compute `(right_peak - left_peak) / 2`; save left, right, gap, status, and NaN/failure-fraction maps.
- `pysidam.linecutmap.linecutmap_multipeak_fitting.UniversalVortexFitterEngine` for robust multipeak linecut/map fitting.
- Use `run_fit`, then save `fit_results`, `quality`, `extracted_peaks`, and `collect_debug_state_payload` for auditability.

## Peak Height, Z-Ratio, And Bias Calibration

Applicable questions:

- Extract coherence-peak height maps.
- Build Z-ratio maps.
- Correct spectra using global or pixelwise bias offsets.
- Compare intensity at selected bias energies.

Input contract:

- Measured bias axis is recorded.
- Calibrated axis is recorded when used.
- Offset map and fitting method are recorded for pixelwise correction.

Preprocessing:

- Fit or estimate zero-bias centers.
- Interpolate spectra to target energies after choosing the calibrated axis.
- Keep energy extraction separate from intensity extraction.

Quality control:

- Offset fit status.
- Offset map diagnostic.
- Interpolation bounds.
- Target-energy sampling policy.
- Ratio denominator floor or invalid-pixel policy.

Outputs:

- Calibrated bias axis.
- Offset map.
- Peak-height or ratio maps.
- Per-pixel status maps.
- Report entry with target energies and interpolation method.

pysidam mapping:

- `pysidam.linecutmap.linecutmap_intensity` implements intensity modes `dI/dV`, `d2`, and `neg_d3`.
- Use `d2` for the numerical first derivative of dI/dV, and `neg_d3` for the negative second derivative of dI/dV.
- Record derivative order, smoothing, interpolation, baseline removal, integration windows, and denominator floors.
