# STM/SJTM Data Processing Agent Skill

This repository contains a portable agent skill for scanning tunneling microscopy and superconducting-tip STM data processing. It helps agents choose workflows, preserve data contracts, map tasks to `pysidam` when available, apply fitting recipes, enforce quality gates, and produce reproducible evidence packages.

The package is documentation-first, with small portable helper scripts for runtime probing and safe dependency bootstrapping. It does not contain private experimental data, native microscope file readers, or dataset-specific scripts.

## Supported Work

- STM topography processing, background correction, FFT inspection, Bragg peak selection, low-frequency drift correction, and atom or lattice-site detection.
- STS and grid spectroscopy workflows, including gap extraction, superconducting gap fitting, multipeak fitting, ZBP handling, and batch gap maps.
- SJTM workflows including Josephson-current maps, zero-bias conductance or superfluid proxies, gap-height maps, Z-ratio maps, and SIS/NIS deconvolution guidance.
- Fourier, QPI, and complex lock-in phase analysis with amplitude-gated statistics.
- Cross-observable comparison across topography, spectroscopy, gap maps, atom sites, strain, and phase fields.
- Reproducible reporting with machine-readable outputs and diagnostic figures.

## Quick Start

For any STM/SJTM task, an agent should:

1. Run `python3 scripts/resolve_runtime.py --probe` or perform the same cached-runtime import checks.
2. If no cached runtime is ready and local execution is allowed, run `python3 scripts/bootstrap_runtime.py --groups headless` to create an isolated user runtime.
3. Read `references/runtime-bootstrap.md`, `references/data-contracts.md`, and `references/quality-checks.md`.
4. Classify the task using `references/workflow.md`.
5. For file IO, read `references/format-io-matrix.md`; for raw Nanonis files, also read `references/nanonis-3ds-ingest.md`.
6. Read task-specific files such as `references/fitting-recipes.md`, `references/pysidam-tool-map.md`, or `references/reporting.md`.
7. Produce outputs that include inputs, data contracts, parameters, quality metrics, warnings, and reproducibility notes.

## Runtime Bootstrap

The skill ships dependency manifests under `runtime/` and a safe bootstrapper:

```bash
python3 scripts/bootstrap_runtime.py --groups headless
```

The core manifest is `runtime/requirements-core.txt`; companion manifests cover Nanonis IO, IBW export, AI atom detection, and UI-wrapped helpers.

`headless` expands to:

```text
core + nanonis + ibw
```

This installs core numerical tools, `nanonispy`, and `igorwriter` into a per-skill virtual environment under a user-writable cache directory. It never uses `sudo`, never installs into system Python, never modifies conda base, and never runs `brew`.

Optional groups are available when a task needs them:

```bash
python3 scripts/bootstrap_runtime.py --groups headless,ai
python3 scripts/bootstrap_runtime.py --groups headless,ui
python3 scripts/bootstrap_runtime.py --groups all
```

For offline or controlled installs, provide a wheelhouse:

```bash
python3 scripts/bootstrap_runtime.py --groups headless --no-network --wheelhouse /path/to/wheelhouse
```

Useful safety flags:

```bash
python3 scripts/bootstrap_runtime.py --dry-run
python3 scripts/bootstrap_runtime.py --groups headless --pysidam-root /path/to/pysidam
python3 scripts/bootstrap_runtime.py --groups headless --pysidam-mode none
```

The bootstrapper writes `runtime.json` inside the cache with the venv path, dependency groups, PySIDAM source path, and post-install probe results.

For repeated use across project directories, use the resolver:

```bash
python3 scripts/resolve_runtime.py
python3 scripts/resolve_runtime.py --probe
python3 scripts/resolve_runtime.py --print-python
python3 scripts/resolve_runtime.py --bootstrap-command
```

The resolver calls `scripts/probe_runtime.py` through the cached runtime Python when a prepared runtime exists.

Host-specific defaults, such as a local PySIDAM source checkout, belong in:

```text
~/.config/stm-sjtm-data-processing/host.json
```

The skill repository should stay portable; do not commit host paths.

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

PySIDAM is not assumed to be a standard pip package. The bootstrapper first uses an explicit `--pysidam-root`, `PYSIDAM_ROOT`, or nearby source checkout. If none is found and network is available, it can clone the PySIDAM repository into the skill cache and load it as source. It does not mutate existing user checkouts.

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

The current release line is `v0.1.3`. Release notes live in `RELEASE_NOTES_v0.1.3.md`.
