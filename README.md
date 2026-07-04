# STM/SJTM Data Processing Agent Skill

This repository contains a portable agent skill for scanning tunneling microscopy and superconducting-tip STM data processing. It helps agents choose workflows, preserve data contracts, map tasks to `pysidam` when available, apply fitting recipes, enforce quality and approval gates, and produce reproducible evidence packages.

The package is documentation-first, with small portable helper scripts for runtime probing, safe dependency bootstrapping, installed-skill syncing, and an agent bridge over PySIDAM. It does not contain private experimental data or dataset-specific scripts.

## Supported Work

- STM topography processing, background correction, FFT inspection, Bragg peak selection, low-frequency drift correction, and atom or lattice-site detection.
- STS and grid spectroscopy workflows, including gap extraction, superconducting gap fitting, multipeak fitting, ZBP handling, and batch gap maps.
- SJTM workflows including Josephson-current maps, zero-bias conductance or superfluid proxies, gap-height maps, Z-ratio maps, and SIS/NIS deconvolution guidance.
- Fourier, QPI, and complex lock-in phase analysis with amplitude-gated statistics.
- Cross-observable comparison across topography, spectroscopy, gap maps, atom sites, strain, and phase fields.
- Standardized user approval gates for agent-selected fit windows, FFT/q-vector and filter-sigma choices, and multipeak peak counts.
- Reproducible reporting with machine-readable outputs and diagnostic figures.

## Quick Start

For any STM/SJTM task, an agent should:

1. Run `python3 scripts/resolve_runtime.py --probe` or perform the same cached-runtime import checks.
2. If no cached runtime is ready and local execution is allowed, run `python3 scripts/bootstrap_runtime.py --groups headless` to create an isolated user runtime.
3. For simple STS `.dat` reading or diagnostic plots, use the quick card `references/task-cards/sts-dat-quick.md`.
4. Use `scripts/pysidam_agent/read_file.py --quick` for compact file summaries, `scripts/pysidam_agent/plot_spectrum.py` for 1D spectrum figures, `scripts/pysidam_agent/fit_gap.py` with `references/task-cards/gap-fit-quick.md` for PySIDAM-backed superconducting gap fitting, `scripts/pysidam_agent/bragg_phase.py` for Bragg q selection or lock-in phase runs, and `scripts/pysidam_agent/atom_ai.py` for AI atom-detection scale checks, lattice QC, and human-marked region exclusion.
5. For deeper tasks, classify the request using `references/workflow.md` and query `references/pysidam-capability-index.json` with `scripts/pysidam_agent/capabilities.py`.
6. Before quantitative fitting, map extraction, phase claims, or scientific conclusions, read `references/runtime-bootstrap.md`, `references/data-contracts.md`, and `references/quality-checks.md`.
7. If the agent chooses a fitting interval, q vector/q window/filter sigma, or multipeak peak count, use `references/approval-gates.md` and stop for user approval before formal execution.
8. Produce outputs that include inputs, data contracts, parameters, approval decisions when gated, quality metrics, warnings, and reproducibility notes.

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

## PySIDAM Agent Bridge

The bridge scripts under `scripts/pysidam_agent/` are thin, reusable adapters. They auto-reexec into the cached runtime from `runtime.json` when possible, add the host PySIDAM source root from `host.json` or `runtime.json`, and emit compact JSON or PNG outputs.

```bash
python3 scripts/pysidam_agent/capabilities.py --domain core_io
python3 scripts/pysidam_agent/read_file.py --quick data/example.dat --output-json outputs/read_summary.json
python3 scripts/pysidam_agent/plot_spectrum.py data/example.dat --output outputs/spectrum.png --summary-json outputs/spectrum.json
python3 scripts/pysidam_agent/fit_gap.py data/example.dat --model "Two Band s-wave" --output-dir outputs/gap_fit
python3 scripts/pysidam_agent/bragg_phase.py policy
python3 scripts/pysidam_agent/bragg_phase.py inspect-roi data/topo.sxm --roi -0.5 0.5 2.0 3.0 --output-json outputs/q_roi.json
python3 scripts/pysidam_agent/phase_lockin.py run data/topo.npy --scan-size-nm 20 20 --q q1=1.5,0.0 --output-dir outputs/phase_lockin
python3 scripts/pysidam_agent/bragg_phase.py lockin-from-decision --decision approvals/approval_decision.json --raw-root raw_data --output-dir outputs/bragg_phase
python3 scripts/pysidam_agent/atom_ai.py recommend-scale --shape-yx 512 512 --scan-size-nm 20 20 --resize-ratio 1.5 --expected-spacing-nm 0.3515625
python3 scripts/pysidam_agent/atom_ai.py lattice-qc outputs/atoms.csv --expected-spacing-nm 0.3515625 --scan-size-nm 20 20
python3 scripts/pysidam_agent/atom_ai.py wipe-regions outputs/atoms.csv --regions-json regions.json --output-csv outputs/atoms_wiped.csv
```

The bridge is intentionally outside PySIDAM. It does not modify PySIDAM source, avoids Qt windows by default, and keeps full headers and raw arrays out of JSON summaries unless explicitly requested. For `.3ds` files, `read_file.py` defaults to divider `1.0` because Nanonis bias axes are treated as already divider-corrected by the experiment software; apply extra scaling only when the user explicitly requests it. For gap fitting, the bridge delegates to the bundled headless `pysidam_agent_core.gap_fitting.fit_gap_model_guarded`, which uses PySIDAM core model definitions without importing UI-wrapped fitter modules. For Bragg phase work, `bragg_phase.py policy` enforces the user-q/ROI-first decision point, `inspect-roi` handles user-marked peak regions, and `phase_lockin.py run` is the clean 2D lock-in tool for `.sxm`, `.3ds`, `.npy`, `.npz`, or table maps. It writes `report.json`, `phase_lockin_maps.npz`, and `phase_lockin_stats.csv`, and records `pysidam.qpi_analysis.qpi_phase_analysis.lockin_phase_extraction` as the lock-in engine. Downstream strain, phase-jump, or spectroscopy-correlation scripts should consume that package instead of reimplementing lock-in. For AI atom recognition, `atom_ai.py` records detector scale choices such as `resize_ratio`, checks the resulting square-lattice site quality, and applies human-requested DW or defect-region wipes without relabeling atoms outside those regions.

## Approval Gates

Version `v0.2.3` adds a standard approval workflow for scientifically sensitive agent choices:

- `fit_window`: fitting intervals, superconducting coherence-peak windows, and peak-search windows.
- `q_selection`: FFT-derived q vectors, q windows, and filter sigma for QPI, lock-in, p_LL, or phase analysis.
- `peak_count`: number of peaks in multipeak fitting.

Agents create `approval_proposal.json`, optionally render a static review page with `scripts/approval_gate.py render-html`, wait for approval or modification, then continue only from `approval_decision.json`. Routine IO, previews, crop QC, summaries, and exports remain provenance-only and do not require separate approval.

Useful commands:

```bash
python3 scripts/approval_gate.py validate-proposal --proposal approval_proposal.json
python3 scripts/approval_gate.py render-html --proposal approval_proposal.json --output approval_review.html
python3 scripts/approval_gate.py validate-decision --decision approval_decision.json
python3 scripts/approval_gate.py validate-report --report report.json --decision-path approval_decision.json
```

## Codex Installation

Copy or synchronize this repository root to:

```text
~/.codex/skills/stm-sjtm-data-processing/
```

The Codex entry point is `SKILL.md`. The portable references remain under `references/`.

For local development, prefer:

```bash
python3 scripts/sync_installed_skill.py
```

This updates `~/.codex/skills/stm-sjtm-data-processing/` and removes installed `.git` metadata, so installed skills behave like plain packages while this source repository remains the Git working copy.

## Non-Codex Agent Usage

Agents that do not support Codex skills can read this repository directly:

1. Start with this `README.md`.
2. Load `references/workflow.md` and `references/data-contracts.md`.
3. Load the domain reference needed for the user request.
4. Treat `SKILL.md` as optional adapter text.

## pysidam Relationship

`pysidam` is treated as the preferred implementation source. When it is available, agents should use `references/pysidam-capability-index.json`, `references/pysidam-capability-map.md`, and `references/pysidam-tool-map.md` to select headless modules and functions. The repository also ships `pysidam_agent_core/`, a small headless package that extracts repeated agent-facing algorithms while continuing to use PySIDAM core model definitions. Raw Nanonis `.3ds`, `.sxm`, and `.dat` require `nanonispy` through the normal PySIDAM route; missing `nanonispy` should be reported as a dependency gap, not worked around with an unverified binary parser. PXP is not claimed as supported by the current PySIDAM-backed skill.

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

The current release line is `v0.2.4`. Release notes live in `RELEASE_NOTES_v0.2.4.md`.
