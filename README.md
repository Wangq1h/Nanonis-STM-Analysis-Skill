# STM/SJTM Data Processing Agent Skill

This repository contains a portable agent skill for scanning tunneling microscopy and superconducting-tip STM data processing. It helps agents choose workflows, preserve data contracts, map tasks to `pysidam` when available, apply fitting recipes, enforce quality gates, and produce reproducible evidence packages.

The package is documentation-first. It does not contain private experimental data, native microscope file readers, or dataset-specific scripts.

## Supported Work

- STM topography processing, background correction, FFT inspection, Bragg peak selection, low-frequency drift correction, and atom or lattice-site detection.
- STS and grid spectroscopy workflows, including gap extraction, superconducting gap fitting, multipeak fitting, ZBP handling, and batch gap maps.
- SJTM workflows including Josephson-current maps, zero-bias conductance or superfluid proxies, gap-height maps, Z-ratio maps, and SIS/NIS deconvolution guidance.
- Fourier, QPI, and complex lock-in phase analysis with amplitude-gated statistics.
- Cross-observable comparison across topography, spectroscopy, gap maps, atom sites, strain, and phase fields.
- Reproducible reporting with machine-readable outputs and diagnostic figures.

## Quick Start

For any STM/SJTM task, an agent should:

1. Run `python3 scripts/probe_runtime.py` or perform the same import checks.
2. Read `references/runtime-bootstrap.md`, `references/data-contracts.md`, and `references/quality-checks.md`.
3. Classify the task using `references/workflow.md`.
4. For file IO, read `references/format-io-matrix.md`; for raw Nanonis files, also read `references/nanonis-3ds-ingest.md`.
5. Read task-specific files such as `references/fitting-recipes.md`, `references/pysidam-tool-map.md`, or `references/reporting.md`.
6. Produce outputs that include inputs, data contracts, parameters, quality metrics, warnings, and reproducibility notes.

## Codex Installation

Copy or synchronize this repository root to:

```text
~/.codex/skills/stm-sjtm-data-processing/
```

The Codex entry point is `SKILL.md`. The portable references remain under `references/`.

## Non-Codex Agent Usage

Agents that do not support Codex skills can read this repository directly:

1. Start with this `README.md`.
2. Load `references/workflow.md` and `references/data-contracts.md`.
3. Load the domain reference needed for the user request.
4. Treat `SKILL.md` as optional adapter text.

## pysidam Relationship

`pysidam` is treated as the preferred implementation source. When it is available, agents should use `references/pysidam-tool-map.md` to select headless modules and functions. Raw Nanonis `.3ds`, `.sxm`, and `.dat` require `nanonispy` through the normal PySIDAM route; missing `nanonispy` should be reported as a dependency gap, not worked around with an unverified binary parser. PXP is not claimed as supported by the current PySIDAM-backed skill.

The default PySIDAM dependency set is documented in `references/runtime-bootstrap.md`. The probe distinguishes "package can be found" from "module can actually be imported", which matters for Qt-wrapped modules.

## Validation

Run:

```bash
python3 scripts/validate_package.py
```

Expected:

```text
PASS: stm-sjtm-data-processing package is structurally valid
```

## GitHub Release

The initial GitHub Release is `v0.1.0`. It should include the repository source archive and the text from `RELEASE_NOTES_v0.1.0.md`.
