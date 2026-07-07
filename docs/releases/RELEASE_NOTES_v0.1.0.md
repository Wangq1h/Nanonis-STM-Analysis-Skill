# STM/SJTM Data Processing Agent Skill v0.1.0

This preview release provides a portable Markdown skill package for agents that process STM, STS, SJTM, QPI, lock-in phase, topography, spectroscopy fitting, and reproducible evidence-package tasks.

## Included

- Thin Codex adapter in `SKILL.md`.
- Platform-neutral references in `references/`.
- Fitting recipe registry for superconducting gap fitting, multipeak fitting, peak-height maps, Z-ratio maps, and bias calibration.
- pysidam tool map for common STM/SJTM analysis modules.
- Quality gates for data contracts, fitting diagnostics, Fourier/lock-in analysis, cross-observable alignment, and reporting.
- Package validator in `scripts/validate_package.py`.

## Release checklist

- Package validates with `python3 scripts/validate_package.py`.
- No private experimental data is included.
- No local machine paths are included in Markdown package content.
- Codex installation instructions are documented.
- Non-Codex agent usage is documented.
