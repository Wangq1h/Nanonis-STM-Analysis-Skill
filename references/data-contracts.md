# Data Contracts

Use this reference before quantitative STM/SJTM analysis. Do not infer axis order, units, or coordinate frames silently.

## Array Shapes

- 2D map: `(y, x)`.
- Spectroscopy cube: `(y, x, bias)`.
- Fit cube view: `(bias, y, x)`, created only by an explicit transpose when a fitting function expects spectra as the first axis.
- Linecut stack: document whether it is `(position, bias)` or `(bias, position)`.
- PySIDAM core 3DS cube: `(x, y, bias)`. When using `pysidam.core.dataset_utils.prepare_3ds_dataset`, preserve this internal order until a downstream report or plotting step explicitly needs row-major `(y, x, bias)`.

## Bias Axis

Record:

- Unit: mV or meV.
- Divider or scale factor.
- Sweep direction.
- Whether the axis is measured, calibrated globally, or calibrated pixelwise.
- Interpolation method used to sample spectra at target energies.

When the bias unit or divider cannot be determined, stop and request metadata or exported axis information.

## Coordinate Frame

Record:

- Pixel origin.
- Whether image display uses `origin="lower"` or another convention.
- Scan size and pixel size.
- Any crop, transpose, flip, drift correction, affine transform, or interpolation.
- Whether topography, spectroscopy, and derived maps share the same frame.

## Units

Common units:

- Topography: m, nm, pm, or arbitrary display units.
- Current: A, pA, nA.
- Conductance: A/V, pA/mV, arbitrary lock-in units.
- Energy or voltage: meV, mV, uV.
- q vectors: pixel inverse units, nm^-1, or reciprocal lattice units.

Never combine q vectors or phase fields from different unit systems without an explicit conversion.

## NaN And Inf Handling

Record how invalid values are handled:

- Preserve as invalid for fitting status maps.
- Replace with mean only for FFT display.
- Interpolate only when the method and affected pixels are reported.

## Required Contract Summary

Every report should include:

```text
data_contract:
  map_shape_yx
  cube_shape_yxbias
  pysidam_internal_shape_xybias
  bias_unit
  bias_axis_source
  coordinate_frame
  scan_size
  pixel_size
  transforms
```
