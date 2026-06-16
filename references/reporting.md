# Reporting

Use a machine-readable report for every substantial STM/SJTM analysis. The report should let another agent reproduce the workflow from source files, parameters, and saved outputs.

## Default report.json Schema

Use these top-level keys:

```text
inputs
data_contract
preprocessing
analysis
parameters
quality
warnings
outputs
software
interpretation
```

## Key Meanings

- `inputs`: source files, channel names, metadata sources, and user-provided assumptions.
- `data_contract`: shape, axis order, units, coordinate frame, scan size, pixel size, and transforms.
- `preprocessing`: background correction, smoothing, normalization, bias calibration, interpolation, window functions, and masks.
- `analysis`: selected workflow, model family, fitting method, q selection, lock-in method, or comparison method.
- `parameters`: numerical settings with units.
- `quality`: fit statuses, residuals, boundary hits, mask coverage, threshold sweeps, and diagnostic summaries.
- `warnings`: missing metadata, weak assumptions, failed fits, coordinate uncertainty, or model non-uniqueness.
- `outputs`: relative paths to NPZ, CSV, PNG, PDF, and auxiliary files.
- `software`: package names, versions, source paths, and commit hashes when available.
- `interpretation`: optional measured-result summary and scientific interpretation kept as separate statements.

## Evidence Package Layout

Use this layout when the user has not specified another one:

```text
analysis-output/
  report.json
  data.npz
  tables/
  figures/
  notes.md
```

## Interpretation Rules

Separate measured outputs from claims:

- Measured result: a fitted value, map statistic, q peak, phase distribution, or quality metric.
- Interpretation: a physical explanation or hypothesis based on measured results.

If a quality gate fails, state the limitation in `warnings` and weaken the interpretation.
