# Release Notes: v3.0

## Summary

This release introduces AnalySTM 3.0, the public installable headless backend for the STM/SJTM agent skill. The package lives under `src/analystm`, imports as `analystm`, and exposes the `analystm` CLI so supported workflows can run without a private PySIDAM source checkout.

## Highlights

- Added package metadata in `pyproject.toml` with a console entry point named `analystm`.
- Added public CLI commands for `read`, `plot-spectrum`, `spectroscopy`, `fit-gap`, `gap-map`, `multipeak`, `intensity`, `waterfall`, `qpi`, `topography`, `histogram`, `crop`, `path-viz`, `publication`, `export`, `bragg`, `phase-lockin`, `atom`, `domain-wall`, `sjtm`, and `deconvolve`.
- Added true headless migrations for PySIDAM Nanonis `.dat`/`.3ds` export, publication payload helpers, spectroscopy display processing, useful-tools histogram/map-crop/path-viz algorithms, gap-map peak fitting, UniversalVortexFitterEngine multipeak fitting, waterfall linecut-map fitting and peak-align-zero calibration, topography display/LF drift correction, topography/QPI FFT ROI filtering, linecut intensity processing, Z-ratio maps, peak-align-zero bias calibration, QPI display FFT volumes, 1D-QPI K-E FFT, PR-QPI/PQPI volumes, QPI symmetry, qpi_real_phase p_LL maps, SPSTM contrast helpers, SJTM Quick/Accurate Ic and superfluid metrics, and SIS dI/dV deconvolution.
- Standardized replacement-backend provenance: AnalySTM reports name `analystm.*` as the execution engine and record PySIDAM routines as `pysidam_source_mapping`.
- Brought SIS dI/dV forward modeling and DOS display normalization in line with the migrated source algorithms rather than the earlier simplified public surface.
- Added public grid deconvolution helper APIs for linear resampling, weighted pseudo-inverse operators, R2 scoring, and masked cube means.
- Added a replacement coverage matrix to document completed replacement surfaces and their PySIDAM source mappings.
- Migrated reusable approval, atom QC/wipe, Domain Wall mask/stat, Bragg/q policy, IO/export, gap-model, gap-fitting, gap-map, multipeak, topography LF drift/filtering, useful-tools histogram/map-crop, intensity/Z-ratio/bias-calibration, QPI display/1D-QPI/filter/PR-QPI/symmetry/real-phase, SPSTM contrast, SJTM Quick/Accurate Ic, deconvolution, and lock-in helpers into `src/analystm`.
- Copied the required headless raw-IO and model utilities into AnalySTM so supported imports do not depend on private PySIDAM runtime paths.
- Updated the skill entry point and README to prefer AnalySTM first and keep `scripts/pysidam_agent/*` as a legacy compatibility bridge.
- Added tests and validation for clean `import analystm`, CLI command discovery, atom/domain-wall smoke workflows, and public-backend forbidden-boundary scanning.
- AI atom-recognition scale selection, post-detection QC, and human wipe/report tooling are public in this release. The detector model and weights remain optional external dependencies; publishing the AI model openly is the next roadmap step.

## Public Boundary

The public backend must not require `PYSIDAM_ROOT`, private PySIDAM source paths, PyQt5, pyqtgraph, or dataset-specific local paths. Optional raw Nanonis support still depends on `nanonispy`; missing optional dependencies should be reported clearly instead of replaced with unverified parsers.

## Release Checklist

- Run `python3 scripts/validate_package.py`.
- Run the unit test suite.
- Install in a fresh virtual environment and confirm `python -c "import analystm"` succeeds.
- Confirm `python -m analystm --help` lists the public commands.
