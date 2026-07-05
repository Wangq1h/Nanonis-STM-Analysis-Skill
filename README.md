<div align="center">
  <img src="assets/stm-agent-icon.png" alt="STM Analysis Agent icon" width="132">

  <h1>STM/SJTM Data Processing Agent Skill</h1>

  <p><strong>From raw Nanonis files to paper-ready STM figures, with data contracts, approval gates, and reproducible evidence built in.</strong></p>

  <p>
    <a href="README.md"><img alt="Language: English" src="https://img.shields.io/badge/lang-English-2563eb"></a>
    <a href="README.zh-CN.md"><img alt="Language: Simplified Chinese" src="https://img.shields.io/badge/lang-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-c2410c"></a>
    <img alt="Release v0.2.4" src="https://img.shields.io/badge/release-v0.2.4-64748b">
    <img alt="STM STS SJTM" src="https://img.shields.io/badge/domain-STM%20%2F%20STS%20%2F%20SJTM-0f766e">
    <img alt="PySIDAM backed" src="https://img.shields.io/badge/PySIDAM-backed-7c3aed">
    <img alt="Evidence package" src="https://img.shields.io/badge/output-evidence%20package-0369a1">
  </p>

  <p>
    <a href="docs/tutorials/agent-guided-stm-data-analysis.md">Tutorial</a>
    · <a href="https://github.com/Wangq1h/Nanonis-STM-Analysis-Skill/wiki">Wiki</a>
    · <a href="references/workflow.md">Workflow</a>
    · <a href="references/data-contracts.md">Data Contracts</a>
    · <a href="references/approval-gates.md">Approval Gates</a>
  </p>
</div>

---

![STS figure extraction chat demo](assets/sts-agent-chat-demo.png)

This repository contains a portable agent skill for scanning tunneling microscopy (STM), scanning tunneling spectroscopy (STS), and superconducting-tip STM (SJTM) data processing. It helps agents route work to PySIDAM where available, confirm units and axes, enforce approval gates for scientifically sensitive choices, and package results as figures, tables, scripts, and machine-readable provenance.

## Why This Skill Exists

STM data analysis is full of small choices that matter: channel names, bias units, sweep direction, gap windows, q vectors, masks, and normalization ranges. This skill gives an agent a disciplined working mode: first establish the data contract, then propose sensitive parameters, then return figures and evidence that another researcher can rerun.

## STS Figure Extraction in Action

> **Researcher:**
> “Look at `raw_data/`. The files `001-005.dat` are superconducting spectra taken at different temperatures. The temperatures should be in the headers. Use the STM skill, read the data, and make a clean figure that can go into a paper.”

Seven minutes later, the agent comes back with a compact, auditable result:

- read the temperatures from each file header: `4.2 K`, `1.35 K`, `1.1 K`, `0.92 K`, `0.35 K`;
- selected `LI Demod 1 X (A)`, aligned forward/backward sweeps, converted bias to `mV` and signal to `pA`;
- normalized the main plot by the average signal in `|V| = 8-10 mV`;
- made a vertically offset stacked spectrum figure without smoothing;
- exported paper-facing `PDF`, `SVG`, `PNG`, and `TIFF`;
- saved `processed_spectra.csv`, `paper_figure_provenance.json`, and the rerunnable script;
- reran the script from scratch and verified all outputs were nonempty.

That is the intended feel of this skill: not a black box that says “done”, but a careful lab assistant that shows what it read, what it changed, which choices stayed auditable, and where every output lives.

## Approval Gates in Action

The same pattern matters even more for Bragg/QPI work. A vague request such as “the red-box qB peak looks more like a Bragg peak” is not treated as permission to run a phase analysis. The agent first turns it into a `q_selection` gate: propose the ROI-derived q vector, show the FFT evidence, list the risks, and wait for the user to approve or modify the scientific parameters.

<p align="center">
  <img src="assets/scenario-qb-red-peak-correction.png" alt="q-vector approval workflow for Bragg lock-in" width="920">
</p>

In this example, the user can confirm the choice in several natural ways: accept the red-ROI local maximum, type an explicit q vector, or adjust the lock-in filter. Only after that does the agent write `approval_decision.json` and continue with the qB lock-in outputs.

## Phase Hygiene in Action

Phase maps have their own traps. When a continuous display profile appears to jump by nearly `2π`, the skill pushes the agent to separate display artifacts from physical interpretation: branch-cut bins can be omitted from the plotted profile, while the underlying phase data and left/right domain statistics remain auditable.

<p align="center">
  <img src="assets/scenario-phase-branch-cut.png" alt="Branch-cut-aware Bragg phase display" width="920">
</p>

That distinction is deliberate. The agent may improve the figure so it does not imply a false spike, but it should not turn a wrapped-phase branch cut into a physical phase-jump claim.

## What It Helps Agents Do

- **Read raw files safely**: inspect `.3ds`, `.sxm`, `.dat`, `.ibw`, `.csv`, `.tsv`, and text spectra without copying private data into the skill repository.
- **Preserve data contracts**: record shape, axis order, bias units, divider, scan size, coordinate frame, selected channels, flips, transposes, and masks.
- **Use PySIDAM where possible**: route Nanonis IO, gap fitting, Bragg/QPI lock-in, atom detection, and domain-wall masks through existing headless tools or thin bridge scripts.
- **Stop for approval when it matters**: require user approval for agent-selected fit windows, q vectors/filter sigma, and multipeak peak counts.
- **Package evidence**: save `report.json`, NPZ arrays, CSV tables, figures, approval records, warnings, and rerunnable commands.
- **Keep interpretation cautious**: separate measured results from physical claims such as YSR states, topological modes, strain correlations, or phase jumps.

## Quick Start

For a new STM/SJTM analysis thread, start with a prompt like:

```text
Use the stm-sjtm-data-processing skill.

Workspace:
/path/to/stm-workspace

Read:
/path/to/stm-workspace/data_manifest.json
/path/to/stm-workspace/outputs/initial_file_inventory.json

Raw data are referenced through raw_data. Do not copy raw data into the skill repo.

First confirm file shapes, axis order, bias unit/divider, channels, scan size,
pixel size, coordinate frame, and origin convention.

If you need to choose a fit window, q vector/filter sigma, or peak count,
write approval_proposal.json first and wait for my approval before execution.
```

For local runtime checks:

```bash
python3 scripts/resolve_runtime.py --probe
```

If no cached runtime is ready:

```bash
python3 scripts/bootstrap_runtime.py --groups headless
```

Common bridge commands:

```bash
python3 scripts/pysidam_agent/read_file.py --quick data/example.dat --output-json outputs/read_summary.json
python3 scripts/pysidam_agent/plot_spectrum.py data/example.dat --output outputs/spectrum.png --summary-json outputs/spectrum.json
python3 scripts/pysidam_agent/fit_gap.py data/example.dat --model "Two Band s-wave" --output-dir outputs/gap_fit
python3 scripts/pysidam_agent/bragg_phase.py policy
python3 scripts/pysidam_agent/bragg_phase.py inspect-roi data/topo.sxm --roi -0.5 0.5 2.0 3.0 --output-json outputs/q_roi.json
python3 scripts/pysidam_agent/phase_lockin.py run data/topo.npy --scan-size-nm 20 20 --q q1=1.5,0.0 --output-dir outputs/phase_lockin
python3 scripts/pysidam_agent/atom_ai.py recommend-scale --shape-yx 512 512 --scan-size-nm 20 20 --resize-ratio 1.5 --expected-spacing-nm 0.3515625
python3 scripts/pysidam_agent/domain_wall.py build-masks --shape-yx 128 128 --scan-size-nm 30 30 --regions-json dw_regions.json --near-width-nm 1.0 --output-dir outputs/domain_wall
```

## Skill Installation

Copy or synchronize this repository root into the skill directory used by your agent runtime.

For local development, prefer:

```bash
python3 scripts/sync_installed_skill.py
```

## Validation

```bash
python3 scripts/validate_package.py
```

Expected:

```text
PASS: stm-sjtm-data-processing package is structurally valid
```

## References

- [Agent-guided STM Data Analysis](docs/tutorials/agent-guided-stm-data-analysis.md)
- [GitHub Wiki](https://github.com/Wangq1h/Nanonis-STM-Analysis-Skill/wiki)
- [Workflow reference](references/workflow.md)
- [Data contracts](references/data-contracts.md)
- [Quality checks](references/quality-checks.md)
- [Approval gates](references/approval-gates.md)
- [PySIDAM capability map](references/pysidam-capability-map.md)

## Developer Reference

- Runtime manifest: `runtime/requirements-core.txt`
- Runtime probe script: `scripts/probe_runtime.py`
- Quick task cards: `references/task-cards/sts-dat-quick.md`, `references/task-cards/gap-fit-quick.md`
- Capability index: `references/pysidam-capability-index.json`
- Other Agent Runtimes: read this README first, then load the workflow, data-contract, and domain references needed for the task.
- GitHub Release: release notes live in `RELEASE_NOTES_v*.md`; the current release line follows the latest versioned release note.

## Relationship to PySIDAM

`pysidam` is treated as the preferred implementation source. This repository adds agent-facing workflow rules, approval gates, runtime probing, bridge scripts, and reporting conventions around it. The goal is to help an agent use the right scientific tool and preserve enough evidence for another researcher to audit the result.
