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

- `spectroscopy_dynes_fitting.py` for Dynes-style interactive fitting.
- `superconducting_gap_models.py` for reusable gap model helpers.
- `usefultools_deconvolution_point.py` for NIS/SIS point-spectrum fitting and deconvolution.
- `usefultools_deconvolution_grid.py` for grid-based deconvolution workflows.

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

- `linecutmap_gap_map_extraction.py` and `PeakFitter` for Gaussian peak extraction and gap maps.
- `linecutmap_multipeak_fitting.py` for universal multipeak fitting and linecut workflows.

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
