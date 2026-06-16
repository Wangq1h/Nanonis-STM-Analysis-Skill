# STM/SJTM Workflow

This reference gives the default analysis sequence for STM, STS, SJTM, QPI, and lock-in tasks. Use the smallest workflow that answers the user request, then add more stages only when the data and metadata support them.

## 1. Ingest

Identify the source format and available channels before analysis. Common inputs include `.sxm`, `.3ds`, `.dat`, `.pxp`, `.ibw`, CSV, TXT, NPZ, NPY, HDF5, and exported image files.

Record:

- Source files and channel names.
- Topography map availability.
- Spectroscopy cube availability.
- Bias or sweep axis.
- Scan size and pixel size.
- Header metadata used for temperature, sweep direction, units, or tip state.

If a native reader is unavailable, request exported intermediate data in CSV, NPZ, HDF5, or text form.

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
7. Export corrected maps, displacement fields, site coordinates, and diagnostics.

## 4. Spectroscopy Processing

Typical sequence:

1. Confirm bias axis unit and direction.
2. Display representative spectra and mean spectra.
3. Decide whether the task needs peak extraction or physical DOS fitting.
4. Apply normalization, smoothing, symmetrization, or bias calibration only when recorded in the report.
5. Fit single spectra before batch maps.
6. For batch maps, output value maps, status maps, and representative diagnostics.

## 5. SJTM-Specific Maps

For superconducting-tip data, record tip state, temperature, voltage unit, sweep direction, and model assumptions. Analyze Josephson-current, zero-bias conductance, superfluid proxy, gap-height, Z-ratio, and deconvolution outputs as separate observables unless the model justifies combining them.

## 6. Fourier, QPI, And Lock-In

Typical sequence:

1. Mean-subtract or detrend as recorded.
2. Apply a named window function.
3. Compute FFT and apply display scaling.
4. Mask the DC component when appropriate.
5. Select or refine target q points.
6. Extract complex lock-in fields.
7. Save amplitude, phase, complex field, and masks.
8. Treat `+q`, `-q`, `qx`, and `qy` separately before any merge.

## 7. Cross-Observable Analysis

Compare topography, dI/dV, gap maps, SJTM maps, atom sites, displacement, strain, and phase fields only after confirming a common coordinate frame. If alignment is uncertain, report map-level observations and avoid site-level claims.

## 8. Evidence Package

Every substantial workflow should produce:

- `report.json` with inputs, contracts, parameters, quality metrics, warnings, outputs, and software provenance.
- Data outputs as NPZ or named CSV files.
- Diagnostic PNG or PDF figures.
- Notes separating measured results from interpretation when interpretation is requested.
